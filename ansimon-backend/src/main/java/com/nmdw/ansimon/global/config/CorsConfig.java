package com.nmdw.ansimon.global.config;

import java.util.List;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

/**
 * 관리자 프론트엔드가 다른 출처에서 관리자 API({@code /api/**})를 호출할 수 있도록 CORS 정책을 한곳에서 정의합니다.
 * 허용 출처는 {@link CorsProperties}가 설정에서 읽어오며, 이 소스는 관리자 보안 체인에만 연결됩니다.
 * {@code /internal/**}은 브라우저가 부를 경로가 아니므로 CORS를 열지 않습니다. CORS는 브라우저가 응답을 읽는 것만 제한하므로
 * 내부 API의 실제 차단은 {@code InternalApiKeyFilter}의 API 키 검사가 맡습니다.
 * 인증 쿠키를 쓰지 않으므로 자격 증명 전송은 허용하지 않습니다.
 */
@Configuration
@EnableConfigurationProperties(CorsProperties.class)
public class CorsConfig {

    @Bean
    public CorsConfigurationSource corsConfigurationSource(CorsProperties corsProperties) {
        CorsConfiguration configuration = new CorsConfiguration();
        configuration.setAllowedOrigins(List.copyOf(corsProperties.getAllowedOrigins()));
        configuration.setAllowedMethods(List.of("GET", "POST", "PATCH", "DELETE", "OPTIONS"));
        configuration.setAllowedHeaders(List.of("*"));
        configuration.setAllowCredentials(false);
        configuration.setMaxAge(3600L);

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/api/**", configuration);
        return source;
    }
}
