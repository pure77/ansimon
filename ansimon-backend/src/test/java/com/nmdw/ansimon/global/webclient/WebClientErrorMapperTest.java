package com.nmdw.ansimon.global.webclient;

import com.nmdw.ansimon.global.error.ErrorCode;
import com.nmdw.ansimon.global.error.ExternalServiceException;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;

import java.net.ConnectException;
import java.util.concurrent.TimeoutException;

import static org.assertj.core.api.Assertions.assertThat;

class WebClientErrorMapperTest {

    private final WebClientErrorMapper mapper = new WebClientErrorMapper();

    @Test
    void mapsUpstream4xxToSafeClientError() {
        assertThat(mapper.forStatus(HttpStatus.BAD_REQUEST).errorCode())
                .isEqualTo(ErrorCode.EXTERNAL_SERVICE_CLIENT_ERROR);
    }

    @Test
    void mapsUpstream5xxToSafeServerError() {
        assertThat(mapper.forStatus(HttpStatus.BAD_GATEWAY).errorCode())
                .isEqualTo(ErrorCode.EXTERNAL_SERVICE_SERVER_ERROR);
    }

    @Test
    void mapsResponseTimeoutToSafeTimeoutError() {
        assertThat(mapper.forFailure(new TimeoutException()).errorCode())
                .isEqualTo(ErrorCode.EXTERNAL_SERVICE_TIMEOUT);
    }

    @Test
    void mapsConnectionFailureToSafeServerError() {
        assertThat(mapper.forFailure(new ConnectException()).errorCode())
                .isEqualTo(ErrorCode.EXTERNAL_SERVICE_SERVER_ERROR);
    }

    @Test
    void mapsUnknownClientFailureToSafeServerError() {
        ExternalServiceException exception = mapper.forFailure(new IllegalStateException("provider response with private data"));

        assertThat(exception.errorCode()).isEqualTo(ErrorCode.EXTERNAL_SERVICE_SERVER_ERROR);
        assertThat(exception.getMessage()).isEqualTo("An external service is unavailable.");
    }
}
