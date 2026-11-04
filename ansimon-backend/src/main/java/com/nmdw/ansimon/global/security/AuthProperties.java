package com.nmdw.ansimon.global.security;

import java.nio.charset.StandardCharsets;
import java.time.Duration;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.util.StringUtils;

/**
 * 관리자 콘솔 JWT의 서명 비밀키, 유효기간, 발급자를 설정에서 바인딩합니다.
 * HS256은 키 길이가 곧 강도이므로 32바이트 미만이면 생성 시점에 실패시켜, 약한 키로 서버가 뜨는 일을 막습니다.
 */
@ConfigurationProperties(prefix = "ansimon.auth")
public record AuthProperties(
        String jwtSecret,
        Duration accessTokenTtl,
        String issuer
) {

    private static final int MIN_SECRET_BYTES = 32;
    private static final Duration DEFAULT_TTL = Duration.ofHours(1);
    private static final String DEFAULT_ISSUER = "ansimon-backend";

    public AuthProperties {
        if (!StringUtils.hasText(jwtSecret)) {
            throw new IllegalStateException("ansimon.auth.jwt-secret must be set");
        }
        jwtSecret = jwtSecret.trim();
        if (jwtSecret.getBytes(StandardCharsets.UTF_8).length < MIN_SECRET_BYTES) {
            throw new IllegalStateException("ansimon.auth.jwt-secret must be at least 32 bytes");
        }
        accessTokenTtl = accessTokenTtl == null ? DEFAULT_TTL : accessTokenTtl;
        if (accessTokenTtl.isZero() || accessTokenTtl.isNegative()) {
            throw new IllegalStateException("ansimon.auth.access-token-ttl must be positive");
        }
        issuer = StringUtils.hasText(issuer) ? issuer.trim() : DEFAULT_ISSUER;
    }
}
