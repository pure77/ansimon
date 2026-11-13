package com.nmdw.ansimon.auth.application;

import com.nmdw.ansimon.global.security.AuthProperties;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.JwsHeader;
import org.springframework.security.oauth2.jwt.JwtClaimsSet;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.JwtEncoderParameters;
import org.springframework.stereotype.Component;

import java.time.Instant;

/**
 * 로그인한 관리자에게 HS256 액세스 토큰을 발급합니다.
 * 토큰에는 발급자, 주체(로그인 아이디), 만료 시각, {@code scope=admin}만 담고 개인정보는 넣지 않습니다.
 */
@Component
public class AccessTokenIssuer {

    private final JwtEncoder jwtEncoder;
    private final AuthProperties authProperties;

    public AccessTokenIssuer(JwtEncoder jwtEncoder, AuthProperties authProperties) {
        this.jwtEncoder = jwtEncoder;
        this.authProperties = authProperties;
    }

    public IssuedToken issue(String subject) {
        Instant now = Instant.now();
        JwtClaimsSet claims = JwtClaimsSet.builder()
                .issuer(authProperties.issuer())
                .subject(subject)
                .issuedAt(now)
                .expiresAt(now.plus(authProperties.accessTokenTtl()))
                .claim("scope", "admin")
                .build();
        String value = jwtEncoder.encode(JwtEncoderParameters.from(JwsHeader.with(MacAlgorithm.HS256).build(), claims))
                .getTokenValue();
        return new IssuedToken(value, authProperties.accessTokenTtl().toSeconds());
    }

    public record IssuedToken(String value, long expiresInSeconds) {
    }
}
