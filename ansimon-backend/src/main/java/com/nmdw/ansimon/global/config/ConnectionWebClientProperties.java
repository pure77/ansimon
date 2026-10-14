package com.nmdw.ansimon.global.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.time.Duration;

/**
 * 대응계획 생성부터 전화·요약까지 동기로 기다리는 안심온 커넥션 전용 타임아웃입니다.
 */
@ConfigurationProperties(prefix = "ansimon.connection.web-client")
public class ConnectionWebClientProperties {

    private Duration connectionTimeout = Duration.ofSeconds(2);
    private Duration responseTimeout = Duration.ofSeconds(120);

    public Duration getConnectionTimeout() {
        return connectionTimeout;
    }

    public void setConnectionTimeout(Duration connectionTimeout) {
        this.connectionTimeout = connectionTimeout;
    }

    public Duration getResponseTimeout() {
        return responseTimeout;
    }

    public void setResponseTimeout(Duration responseTimeout) {
        this.responseTimeout = responseTimeout;
    }
}
