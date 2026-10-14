package com.nmdw.ansimon.global.config;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * 관리자 프론트엔드가 다른 출처에서 API를 호출할 수 있도록 CORS 정책을 한곳에서 정의합니다.
 * 허용 출처는 {@link CorsProperties}가 설정에서 읽어오며, 브라우저가 사용하는 조회·등록·수정·삭제 메서드만 허용합니다.
 * 인증 쿠키를 쓰지 않으므로 자격 증명 전송은 허용하지 않습니다.
 */
@Configuration
@EnableConfigurationProperties(CorsProperties.class)
public class CorsConfig implements WebMvcConfigurer {

    private final CorsProperties corsProperties;

    public CorsConfig(CorsProperties corsProperties) {
        this.corsProperties = corsProperties;
    }

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/**")
                .allowedOrigins(corsProperties.getAllowedOrigins().toArray(String[]::new))
                .allowedMethods("GET", "POST", "PATCH", "DELETE", "OPTIONS")
                .allowedHeaders("*")
                .allowCredentials(false)
                .maxAge(3600);
    }
}
