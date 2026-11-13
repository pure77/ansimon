package com.nmdw.ansimon.auth.application;

import com.nmdw.ansimon.global.security.AuthProperties;
import com.nmdw.ansimon.global.security.JwtConfig;
import org.junit.jupiter.api.Test;
import org.springframework.security.oauth2.jwt.Jwt;

import java.time.Duration;

import static org.assertj.core.api.Assertions.assertThat;

class AccessTokenIssuerTest {

    private static final String SECRET = "test-jwt-secret-0000000000000000000000";

    @Test
    void issuesDecodableHs256TokenWithAdminClaimsAndDefaultTtl() {
        AuthProperties props = new AuthProperties(SECRET, null, null);
        AccessTokenIssuer issuer = new AccessTokenIssuer(new JwtConfig().jwtEncoder(props), props);

        AccessTokenIssuer.IssuedToken token = issuer.issue("admin");
        Jwt jwt = new JwtConfig().jwtDecoder(props).decode(token.value());

        assertThat(jwt.getClaimAsString("iss")).isEqualTo("ansimon-backend");
        assertThat(jwt.getSubject()).isEqualTo("admin");
        assertThat(jwt.getClaimAsString("scope")).isEqualTo("admin");
        assertThat(jwt.getHeaders().get("alg")).isEqualTo("HS256");
        assertThat(Duration.between(jwt.getIssuedAt(), jwt.getExpiresAt())).isEqualTo(Duration.ofHours(1));
        assertThat(token.expiresInSeconds()).isEqualTo(3600);
    }

    @Test
    void honoursConfiguredTtl() {
        AuthProperties props = new AuthProperties(SECRET, Duration.ofMinutes(5), null);
        AccessTokenIssuer issuer = new AccessTokenIssuer(new JwtConfig().jwtEncoder(props), props);

        AccessTokenIssuer.IssuedToken token = issuer.issue("admin");
        Jwt jwt = new JwtConfig().jwtDecoder(props).decode(token.value());

        assertThat(token.expiresInSeconds()).isEqualTo(300);
        assertThat(Duration.between(jwt.getIssuedAt(), jwt.getExpiresAt())).isEqualTo(Duration.ofMinutes(5));
    }
}
