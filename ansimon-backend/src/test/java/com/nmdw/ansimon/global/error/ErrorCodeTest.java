package com.nmdw.ansimon.global.error;

import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;

import static org.assertj.core.api.Assertions.assertThat;

class ErrorCodeTest {

    @Test
    void exposesStableNamespacedCodesWithTheirPublicHttpStatuses() {
        assertThat(ErrorCode.VALIDATION_ERROR.code()).isEqualTo("GLOBAL_VALIDATION_ERROR");
        assertThat(ErrorCode.VALIDATION_ERROR.status()).isEqualTo(HttpStatus.BAD_REQUEST);
        assertThat(ErrorCode.MALFORMED_REQUEST.code()).isEqualTo("GLOBAL_MALFORMED_REQUEST");
        assertThat(ErrorCode.MALFORMED_REQUEST.status()).isEqualTo(HttpStatus.BAD_REQUEST);
        assertThat(ErrorCode.UNSUPPORTED_MEDIA_TYPE.code()).isEqualTo("GLOBAL_UNSUPPORTED_MEDIA_TYPE");
        assertThat(ErrorCode.UNSUPPORTED_MEDIA_TYPE.status()).isEqualTo(HttpStatus.UNSUPPORTED_MEDIA_TYPE);
        assertThat(ErrorCode.METHOD_NOT_ALLOWED.code()).isEqualTo("GLOBAL_METHOD_NOT_ALLOWED");
        assertThat(ErrorCode.METHOD_NOT_ALLOWED.status()).isEqualTo(HttpStatus.METHOD_NOT_ALLOWED);
        assertThat(ErrorCode.RESOURCE_NOT_FOUND.code()).isEqualTo("GLOBAL_RESOURCE_NOT_FOUND");
        assertThat(ErrorCode.RESOURCE_NOT_FOUND.status()).isEqualTo(HttpStatus.NOT_FOUND);
        assertThat(ErrorCode.CONFLICT.code()).isEqualTo("GLOBAL_CONFLICT");
        assertThat(ErrorCode.CONFLICT.status()).isEqualTo(HttpStatus.CONFLICT);
        assertThat(ErrorCode.INTERNAL_ERROR.code()).isEqualTo("GLOBAL_INTERNAL_ERROR");
        assertThat(ErrorCode.INTERNAL_ERROR.status()).isEqualTo(HttpStatus.INTERNAL_SERVER_ERROR);
        assertThat(ErrorCode.EXTERNAL_SERVICE_TIMEOUT.code()).isEqualTo("GLOBAL_EXTERNAL_SERVICE_TIMEOUT");
        assertThat(ErrorCode.EXTERNAL_SERVICE_TIMEOUT.status()).isEqualTo(HttpStatus.GATEWAY_TIMEOUT);
        assertThat(ErrorCode.EXTERNAL_SERVICE_CLIENT_ERROR.code()).isEqualTo("GLOBAL_EXTERNAL_SERVICE_CLIENT_ERROR");
        assertThat(ErrorCode.EXTERNAL_SERVICE_CLIENT_ERROR.status()).isEqualTo(HttpStatus.BAD_GATEWAY);
        assertThat(ErrorCode.EXTERNAL_SERVICE_SERVER_ERROR.code()).isEqualTo("GLOBAL_EXTERNAL_SERVICE_SERVER_ERROR");
        assertThat(ErrorCode.EXTERNAL_SERVICE_SERVER_ERROR.status()).isEqualTo(HttpStatus.BAD_GATEWAY);
    }

    @Test
    void businessExceptionUsesTheErrorCodeForItsPublicPayload() {
        IllegalStateException cause = new IllegalStateException("provider diagnostic");

        BusinessException exception = new BusinessException(ErrorCode.RESOURCE_NOT_FOUND, cause);

        assertThat(exception.errorCode()).isEqualTo(ErrorCode.RESOURCE_NOT_FOUND);
        assertThat(exception.getMessage()).isEqualTo("The requested resource was not found.");
        assertThat(exception.getCause()).isSameAs(cause);
    }

    @Test
    void externalServiceExceptionUsesTheExternalErrorCodeForItsPublicPayload() {
        ExternalServiceException exception = new ExternalServiceException(ErrorCode.EXTERNAL_SERVICE_TIMEOUT);

        assertThat(exception.errorCode()).isEqualTo(ErrorCode.EXTERNAL_SERVICE_TIMEOUT);
        assertThat(exception.getMessage()).isEqualTo("An external service timed out.");
        assertThat(exception.getCause()).isNull();
    }
}
