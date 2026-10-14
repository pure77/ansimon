package com.nmdw.ansimon.global.config;

import java.util.List;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * 브라우저에서 직접 호출하는 관리자 프론트엔드의 허용 출처를 설정에서 바인딩합니다.
 * {@link CorsConfig}가 이 값을 Spring MVC의 CORS 정책에 적용하므로, 개별 컨트롤러는 출처 허용을 직접 선언하지 않습니다.
 * 기본값은 로컬 개발용 정적 서버 주소이며 배포 환경에서는 실제 프론트엔드 도메인으로 교체합니다.
 */
@ConfigurationProperties(prefix = "ansimon.cors")
public class CorsProperties {

    private List<String> allowedOrigins = List.of(
            "http://localhost:5500",
            "http://127.0.0.1:5500"
    );

    public List<String> getAllowedOrigins() {
        return allowedOrigins;
    }

    public void setAllowedOrigins(List<String> allowedOrigins) {
        this.allowedOrigins = allowedOrigins;
    }
}
