package com.nmdw.ansimon.global.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * 안심온 외부 API의 OpenAPI 문서 기본 정보를 설정합니다.
 * springdoc이 생성하는 명세와 Swagger UI에 서비스 이름, 버전, 설명을 공통으로 제공합니다.
 */
@Configuration
public class OpenApiConfig {

    @Bean
    public OpenAPI ansimonOpenApi() {
        return new OpenAPI().info(new Info()
                .title("안심온 API")
                .version("v1")
                .description("폭염 취약 노인 관리와 예방 지원을 위한 안심온 REST API"));
    }
}
