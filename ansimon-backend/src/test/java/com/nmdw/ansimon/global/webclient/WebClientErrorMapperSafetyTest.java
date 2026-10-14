package com.nmdw.ansimon.global.webclient;

import com.nmdw.ansimon.global.error.ExternalServiceException;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class WebClientErrorMapperSafetyTest {

    @Test
    void doesNotRetainThePotentiallySensitiveClientFailure() {
        IllegalStateException rawFailure = new IllegalStateException(
                "https://provider.example.test/forecast?phone=01012345678&token=secret");

        ExternalServiceException exception = new WebClientErrorMapper().forFailure(rawFailure);

        assertThat(exception.getCause()).isNull();
    }
}
