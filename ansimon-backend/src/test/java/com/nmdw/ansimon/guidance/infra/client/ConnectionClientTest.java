package com.nmdw.ansimon.guidance.infra.client;

import com.nmdw.ansimon.elderly.domain.ConsentStatus;
import com.nmdw.ansimon.global.error.ErrorCode;
import com.nmdw.ansimon.global.error.ExternalServiceException;
import com.nmdw.ansimon.guidance.dto.CareRunRequest;
import com.nmdw.ansimon.risk.domain.RiskLevel;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.web.reactive.function.client.ClientResponse;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class ConnectionClientTest {

    @Test
    void postsToCareRunsAndReturnsAnAck() {
        WebClient webClient = WebClient.builder().exchangeFunction(request -> {
            assertThat(request.url().getPath()).isEqualTo("/v1/care-runs");
            return Mono.just(response(HttpStatus.OK, """
                    {"success":true,"data":{"result":{"externalCallId":"CA_1",
                     "call":{"answered":true}}},"error":null}
                    """));
        }).build();
        ConnectionClient client = new ConnectionClient(webClient);

        var ack = client.requestCareRun(sampleRequest());

        assertThat(ack.externalCallId()).isEqualTo("CA_1");
        assertThat(ack.answered()).isTrue();
    }

    @Test
    void mapsConsentRequiredTo403() {
        ConnectionClient client = new ConnectionClient(stubResponse(HttpStatus.FORBIDDEN,
                "{\"success\":false,\"error\":{\"code\":\"CONSENT_REQUIRED\"}}"));

        assertThatThrownBy(() -> client.requestCareRun(sampleRequest()))
                .isInstanceOfSatisfying(ExternalServiceException.class,
                        exception -> assertThat(exception.errorCode()).isEqualTo(ErrorCode.CONSENT_REQUIRED));
    }

    @Test
    void mapsGuidanceGenerationBlockedTo422() {
        ConnectionClient client = new ConnectionClient(stubResponse(HttpStatus.UNPROCESSABLE_ENTITY,
                "{\"success\":false,\"error\":{\"code\":\"GUIDANCE_GENERATION_BLOCKED\"}}"));

        assertThatThrownBy(() -> client.requestCareRun(sampleRequest()))
                .isInstanceOfSatisfying(ExternalServiceException.class,
                        exception -> assertThat(exception.errorCode())
                                .isEqualTo(ErrorCode.GUIDANCE_GENERATION_BLOCKED));
    }

    private WebClient stubResponse(HttpStatus status, String body) {
        return WebClient.builder().exchangeFunction(request -> Mono.just(response(status, body))).build();
    }

    private ClientResponse response(HttpStatus status, String body) {
        return ClientResponse.create(status)
                .header(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                .body(body)
                .build();
    }

    private CareRunRequest sampleRequest() {
        Instant now = Instant.now();
        return new CareRunRequest(
                new CareRunRequest.Elderly(1L, "010-1234-5678", 78, "고혈압",
                        "1114000000", ConsentStatus.CONSENTED),
                new CareRunRequest.Location(new BigDecimal("37.5665000"), new BigDecimal("126.9780000")),
                new CareRunRequest.Risk(7L, new BigDecimal("0.8238"), RiskLevel.HIGH,
                        now, now.plusSeconds(3600), null, null, List.of(),
                        "heatwave-xgb-v1+illness-xgb-v1"));
    }
}
