package com.nmdw.ansimon.global.config;

import com.nmdw.ansimon.global.error.ExternalServiceException;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.buffer.DefaultDataBufferFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.web.reactive.function.client.ClientResponse;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import java.nio.charset.StandardCharsets;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class WebClientConfigTest {

    @Test
    void releasesErrorResponseBodyBeforeMappingExchangeFailure() {
        ClientResponse response = mock(ClientResponse.class);
        when(response.statusCode()).thenReturn(HttpStatus.BAD_GATEWAY);
        when(response.releaseBody()).thenReturn(Mono.empty());
        WebClient client = configuredClient(response);

        assertThatThrownBy(() -> client.get().uri("/forecast?token=secret")
                .exchangeToMono(ignored -> Mono.just("unexpected")).block())
                .isInstanceOf(ExternalServiceException.class);

        verify(response).releaseBody();
    }

    @Test
    void mapsDecoderFailureWithoutRetainingRawResponseDetails() {
        ClientResponse response = ClientResponse.create(HttpStatus.OK)
                .header("Content-Type", MediaType.APPLICATION_JSON_VALUE)
                .body("{\"value\":")
                .build();

        Throwable thrown = catchFailure(() -> configuredClient(response).get().uri("/forecast")
                .retrieve().bodyToMono(TestPayload.class).block());

        assertThat(thrown).isInstanceOf(ExternalServiceException.class);
        assertThat(thrown.getCause()).isNull();
        assertThat(thrown.getMessage()).doesNotContain("value");
    }

    @Test
    void mapsResponseBodyStreamFailureWithoutRetainingRawCause() {
        IllegalStateException rawFailure = new IllegalStateException("private provider body");
        ClientResponse response = ClientResponse.create(HttpStatus.OK)
                .body(Flux.concat(
                        Mono.just(DefaultDataBufferFactory.sharedInstance.wrap("partial".getBytes(StandardCharsets.UTF_8))),
                        Mono.error(rawFailure)))
                .build();

        Throwable thrown = catchFailure(() -> configuredClient(response).get().uri("/forecast")
                .retrieve().bodyToMono(String.class).block());

        assertThat(thrown).isInstanceOf(ExternalServiceException.class);
        assertThat(thrown.getCause()).isNull();
        assertThat(thrown.getMessage()).doesNotContain("private provider body");
    }

    private WebClient configuredClient(ClientResponse response) {
        return new WebClientConfig().kmaWebClient(
                WebClient.builder().exchangeFunction(request -> Mono.just(response)),
                endpoints(), new WebClientTimeoutProperties());
    }

    private Throwable catchFailure(Runnable request) {
        try {
            request.run();
            throw new AssertionError("Expected request to fail");
        } catch (Throwable failure) {
            return failure;
        }
    }

    private ExternalApiProperties endpoints() {
        ExternalApiProperties.Endpoint endpoint = new ExternalApiProperties.Endpoint("https://provider.example.test", "");
        return new ExternalApiProperties(endpoint, endpoint, endpoint, endpoint, endpoint);
    }

    private record TestPayload(String value) { }
}
