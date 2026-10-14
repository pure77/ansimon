package com.nmdw.ansimon.elderly.infra;

import com.nmdw.ansimon.elderly.application.GeocodingResult;
import com.nmdw.ansimon.global.config.ExternalApiProperties;
import com.nmdw.ansimon.global.error.ErrorCode;
import com.nmdw.ansimon.global.error.ExternalServiceException;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.web.reactive.function.client.ClientResponse;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class TmapGeocodingClientTest {

    @Test
    void geocodesALotNumberStyleAddressUsingLegacyCoordinateFields() {
        WebClient webClient = WebClient.builder().exchangeFunction(request -> {
            assertThat(request.headers().getFirst("appKey")).isEqualTo("test-key");
            if (request.url().getPath().equals("/tmap/geo/fullAddrGeo")) {
                return Mono.just(ClientResponse.create(HttpStatus.OK)
                        .header(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                        .body("""
                        {"coordinateInfo":{"coordinate":[
                          {"lat":"37.57300001","lon":"126.97940001","legalDongCode":"1111010100","newLat":"","newLon":""}
                        ]}}
                        """).build());
            }
            throw new AssertionError("예상치 못한 경로 호출: " + request.url());
        }).build();
        TmapGeocodingClient client = new TmapGeocodingClient(webClient, propertiesWithTmapKey("test-key"));

        GeocodingResult result = client.geocode("서울시 종로구 1-1");

        assertThat(result.latitude()).isEqualByComparingTo("37.5730000");
        assertThat(result.longitude()).isEqualByComparingTo("126.9794000");
        assertThat(result.regionCode()).isEqualTo("11110");
    }

    @Test
    void geocodesARoadNameStyleAddressByFallingBackToReverseGeocoding() {
        WebClient webClient = WebClient.builder().exchangeFunction(request -> {
            assertThat(request.headers().getFirst("appKey")).isEqualTo("test-key");
            if (request.url().getPath().equals("/tmap/geo/fullAddrGeo")) {
                return Mono.just(ClientResponse.create(HttpStatus.OK)
                        .header(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                        .body("""
                        {"coordinateInfo":{"coordinate":[
                          {"lat":"","lon":"","legalDongCode":"","newLat":"37.5715170","newLon":"126.9762330"}
                        ]}}
                        """).build());
            }
            if (request.url().getPath().equals("/tmap/geo/reversegeocoding")) {
                assertThat(request.url().getQuery()).contains("lat=37.5715170").contains("lon=126.9762330");
                return Mono.just(ClientResponse.create(HttpStatus.OK)
                        .header(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                        .body("{\"addressInfo\":{\"legalDongCode\":\"1111011900\"}}")
                        .build());
            }
            throw new AssertionError("예상치 못한 경로 호출: " + request.url());
        }).build();
        TmapGeocodingClient client = new TmapGeocodingClient(webClient, propertiesWithTmapKey("test-key"));

        GeocodingResult result = client.geocode("서울특별시 종로구 세종대로 1");

        assertThat(result.latitude()).isEqualByComparingTo("37.5715170");
        assertThat(result.longitude()).isEqualByComparingTo("126.9762330");
        assertThat(result.regionCode()).isEqualTo("11110");
    }

    @Test
    void rejectsAnEmptyCoordinateResultAsAnExternalServiceFailure() {
        WebClient webClient = WebClient.builder().exchangeFunction(request -> Mono.just(
                ClientResponse.create(HttpStatus.OK)
                        .header(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                        .body("{\"coordinateInfo\":{\"coordinate\":[]}}")
                        .build()
        )).build();
        TmapGeocodingClient client = new TmapGeocodingClient(webClient, propertiesWithTmapKey("test-key"));

        assertThatThrownBy(() -> client.geocode("검색 결과가 없는 주소"))
                .isInstanceOfSatisfying(ExternalServiceException.class,
                        exception -> assertThat(exception.errorCode())
                                .isEqualTo(ErrorCode.EXTERNAL_SERVICE_SERVER_ERROR));
    }

    private ExternalApiProperties propertiesWithTmapKey(String apiKey) {
        ExternalApiProperties.Endpoint other = new ExternalApiProperties.Endpoint("https://example.test", "");
        ExternalApiProperties.Endpoint tmap = new ExternalApiProperties.Endpoint("https://example.test", apiKey);
        return new ExternalApiProperties(other, other, tmap, other, other);
    }
}
