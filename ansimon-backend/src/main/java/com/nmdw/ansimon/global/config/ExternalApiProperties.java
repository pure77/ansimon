package com.nmdw.ansimon.global.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * 기상청·쉼터·TMAP·ML·안심온 커넥션에 접속하기 위한 외부 API 설정을 한 곳에서 바인딩합니다.
 * 각 도메인의 WebClient 설정은 이 타입이 제공하는 서비스별 엔드포인트를 사용하므로, 코드에 URL이나 인증 정보를 직접 두지 않습니다.
 * 실제 비밀 값은 환경별 설정 또는 secret으로 주입되며, 이 타입은 설정 계약만 표현합니다.
 */
@ConfigurationProperties(prefix = "ansimon.external")
public record ExternalApiProperties(
        Endpoint kma,
        Endpoint shelter,
        Endpoint tmap,
        Endpoint ml,
        Endpoint connection
) {

    /**
     * 하나의 외부 서비스에 필요한 기본 주소와 인증 키를 묶어 표현합니다.
     * 상위 {@link ExternalApiProperties}의 서비스별 필드가 이 값을 소유하고, WebClient 생성 시 해당 서비스의 연결 정보로 사용됩니다.
     */
    public record Endpoint(
            String baseUrl,
            String apiKey
    ) {
    }
}
