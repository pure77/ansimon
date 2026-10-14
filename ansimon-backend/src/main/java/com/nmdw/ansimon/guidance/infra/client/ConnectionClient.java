package com.nmdw.ansimon.guidance.infra.client;

import com.nmdw.ansimon.global.error.ErrorCode;
import com.nmdw.ansimon.global.error.ExternalServiceException;
import com.nmdw.ansimon.guidance.dto.CareRunAck;
import com.nmdw.ansimon.guidance.dto.CareRunRequest;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpStatusCode;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.ClientResponse;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.util.Map;

/** 대응계획 생성, 전화, 요약을 안심온 커넥션에 한 번에 요청합니다. */
@Component
public class ConnectionClient {

    private static final ParameterizedTypeReference<Map<String, Object>> JSON_MAP =
            new ParameterizedTypeReference<>() { };

    private final WebClient connectionWebClient;

    public ConnectionClient(@Qualifier("connectionWebClient") WebClient connectionWebClient) {
        this.connectionWebClient = connectionWebClient;
    }

    public CareRunAck requestCareRun(CareRunRequest request) {
        return connectionWebClient.post()
                .uri("/v1/care-runs")
                .bodyValue(request)
                .exchangeToMono(this::handleResponse)
                .block();
    }

    private Mono<CareRunAck> handleResponse(ClientResponse response) {
        if (response.statusCode().is2xxSuccessful()) {
            return response.bodyToMono(JSON_MAP).map(CareRunAck::from);
        }
        return response.releaseBody().then(Mono.error(mapError(response.statusCode())));
    }

    private ExternalServiceException mapError(HttpStatusCode status) {
        ErrorCode errorCode = switch (status.value()) {
            case 400 -> ErrorCode.VALIDATION_ERROR;
            case 403 -> ErrorCode.CONSENT_REQUIRED;
            case 422 -> ErrorCode.GUIDANCE_GENERATION_BLOCKED;
            default -> status.is5xxServerError()
                    ? ErrorCode.EXTERNAL_SERVICE_SERVER_ERROR
                    : ErrorCode.EXTERNAL_SERVICE_CLIENT_ERROR;
        };
        return new ExternalServiceException(errorCode);
    }
}
