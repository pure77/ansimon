package com.nmdw.ansimon.global.security;

import org.junit.jupiter.api.Test;

import java.time.Duration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class AuthPropertiesTest {

    private static final String SECRET = "test-jwt-secret-0000000000000000000000";

    @Test
    void rejectsMissingOrShortSecret() {
        assertThatThrownBy(() -> new AuthProperties(null, null, null))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("jwt-secret");
        assertThatThrownBy(() -> new AuthProperties("short-secret", null, null))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("32 bytes");
    }

    @Test
    void appliesDefaultsForTtlAndIssuer() {
        AuthProperties properties = new AuthProperties("  " + SECRET + "  ", null, " ");

        assertThat(properties.jwtSecret()).isEqualTo(SECRET);
        assertThat(properties.accessTokenTtl()).isEqualTo(Duration.ofHours(1));
        assertThat(properties.issuer()).isEqualTo("ansimon-backend");
    }

    @Test
    void rejectsNonPositiveTtl() {
        assertThatThrownBy(() -> new AuthProperties(SECRET, Duration.ZERO, null))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("access-token-ttl");
    }
}
