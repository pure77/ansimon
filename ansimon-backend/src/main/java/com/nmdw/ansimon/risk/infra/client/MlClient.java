package com.nmdw.ansimon.risk.infra.client;

import com.nmdw.ansimon.risk.dto.MlForecastResponse;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;

/**
 * 위험도예측 ML API(GET /v1/forecast)를 호출하는 어댑터입니다.
 */
@Component
public class MlClient {

    private final WebClient mlWebClient;

    public MlClient(@Qualifier("mlWebClient") WebClient mlWebClient) {
        this.mlWebClient = mlWebClient;
    }

    public MlForecastResponse forecast(String region) {
        return mlWebClient.get()
                .uri(uriBuilder -> uriBuilder.path("/v1/forecast").queryParam("region", region).build())
                .retrieve()
                .bodyToMono(MlForecastResponse.class)
                .block();
    }
}
