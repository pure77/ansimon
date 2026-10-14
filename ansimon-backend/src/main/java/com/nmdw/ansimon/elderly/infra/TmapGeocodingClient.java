package com.nmdw.ansimon.elderly.infra;

import com.nmdw.ansimon.elderly.application.GeocodingClient;
import com.nmdw.ansimon.elderly.application.GeocodingResult;
import com.nmdw.ansimon.global.config.ExternalApiProperties;
import com.nmdw.ansimon.global.error.ErrorCode;
import com.nmdw.ansimon.global.error.ExternalServiceException;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.reactive.function.client.WebClient;

import java.math.BigDecimal;
import java.math.RoundingMode;

/**
 * {@link GeocodingClient}를 TMAP 전체 주소 지오코딩 API로 구현한 외부 연동 어댑터입니다.
 * 응답 좌표를 데이터베이스 정밀도에 맞추고 법정동 코드에서 서비스용 행정구역 코드를 추출합니다.
 */
@Component
public class TmapGeocodingClient implements GeocodingClient {

    private static final int REGION_CODE_LENGTH = 5;

    private final WebClient tmapWebClient;
    private final String apiKey;

    public TmapGeocodingClient(@Qualifier("tmapWebClient") WebClient tmapWebClient,
                               ExternalApiProperties properties) {
        this.tmapWebClient = tmapWebClient;
        this.apiKey = properties.tmap().apiKey();
    }

    @Override
    public GeocodingResult geocode(String address) {
        TmapFullAddrGeoResponse.Coordinate coordinate = firstCoordinate(fetchFullAddrGeo(address));
        String lat = firstNonBlank(coordinate.lat(), coordinate.newLat());
        String lon = firstNonBlank(coordinate.lon(), coordinate.newLon());
        if (!StringUtils.hasText(lat) || !StringUtils.hasText(lon)) {
            throw invalidResponse(null);
        }

        // 도로명 주소로만 매칭되면 fullAddrGeo가 legalDongCode를 비워두므로, 좌표로 리버스 지오코딩해 보완한다.
        String legalDongCode = StringUtils.hasText(coordinate.legalDongCode())
                ? coordinate.legalDongCode()
                : fetchLegalDongCode(lat, lon);
        if (!StringUtils.hasText(legalDongCode) || legalDongCode.length() < REGION_CODE_LENGTH) {
            throw invalidResponse(null);
        }

        try {
            return new GeocodingResult(
                    new BigDecimal(lat).setScale(7, RoundingMode.HALF_UP),
                    new BigDecimal(lon).setScale(7, RoundingMode.HALF_UP),
                    legalDongCode.substring(0, REGION_CODE_LENGTH)
            );
        } catch (NumberFormatException exception) {
            throw invalidResponse(exception);
        }
    }

    private TmapFullAddrGeoResponse fetchFullAddrGeo(String address) {
        return tmapWebClient.get()
                .uri(builder -> builder.path("/tmap/geo/fullAddrGeo")
                        .queryParam("version", 1)
                        .queryParam("format", "json")
                        .queryParam("coordType", "WGS84GEO")
                        .queryParam("addressFlag", "F00")
                        .queryParam("fullAddr", address)
                        .build())
                .header("appKey", apiKey)
                .retrieve()
                .bodyToMono(TmapFullAddrGeoResponse.class)
                .block();
    }

    private String fetchLegalDongCode(String lat, String lon) {
        TmapReverseGeocodingResponse response = tmapWebClient.get()
                .uri(builder -> builder.path("/tmap/geo/reversegeocoding")
                        .queryParam("version", 1)
                        .queryParam("format", "json")
                        .queryParam("coordType", "WGS84GEO")
                        .queryParam("addressType", "A00")
                        .queryParam("lat", lat)
                        .queryParam("lon", lon)
                        .build())
                .header("appKey", apiKey)
                .retrieve()
                .bodyToMono(TmapReverseGeocodingResponse.class)
                .block();
        if (response == null || response.addressInfo() == null) {
            throw invalidResponse(null);
        }
        return response.addressInfo().legalDongCode();
    }

    private String firstNonBlank(String primary, String fallback) {
        return StringUtils.hasText(primary) ? primary : fallback;
    }

    private TmapFullAddrGeoResponse.Coordinate firstCoordinate(TmapFullAddrGeoResponse response) {
        if (response == null || response.coordinateInfo() == null
                || response.coordinateInfo().coordinate() == null
                || response.coordinateInfo().coordinate().isEmpty()
                || response.coordinateInfo().coordinate().getFirst() == null) {
            throw invalidResponse(null);
        }
        return response.coordinateInfo().coordinate().getFirst();
    }

    private ExternalServiceException invalidResponse(Throwable cause) {
        return new ExternalServiceException(ErrorCode.EXTERNAL_SERVICE_SERVER_ERROR, cause);
    }
}
