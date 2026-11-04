package com.nmdw.ansimon.global.security;

import com.nimbusds.jose.jwk.source.ImmutableSecret;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.crypto.factory.PasswordEncoderFactories;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.JwtValidators;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.oauth2.jwt.NimbusJwtEncoder;

import javax.crypto.SecretKey;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;

/**
 * 관리자 JWT를 서명·검증하는 HS256 인코더/디코더와 비밀번호 해시 인코더를 등록합니다.
 * 디코더는 서명과 만료뿐 아니라 발급자도 검사해, 같은 키를 쓰는 다른 시스템의 토큰을 받아들이지 않습니다.
 */
@Configuration
@EnableConfigurationProperties({AuthProperties.class, AdminBootstrapProperties.class})
public class JwtConfig {

    @Bean
    public JwtEncoder jwtEncoder(AuthProperties authProperties) {
        return new NimbusJwtEncoder(new ImmutableSecret<>(signingKey(authProperties)));
    }

    @Bean
    public JwtDecoder jwtDecoder(AuthProperties authProperties) {
        NimbusJwtDecoder decoder = NimbusJwtDecoder.withSecretKey(signingKey(authProperties))
                .macAlgorithm(MacAlgorithm.HS256)
                .build();
        decoder.setJwtValidator(JwtValidators.createDefaultWithIssuer(authProperties.issuer()));
        return decoder;
    }

    @Bean
    public PasswordEncoder passwordEncoder() {
        return PasswordEncoderFactories.createDelegatingPasswordEncoder();
    }

    private static SecretKey signingKey(AuthProperties authProperties) {
        return new SecretKeySpec(authProperties.jwtSecret().getBytes(StandardCharsets.UTF_8), "HmacSHA256");
    }
}
