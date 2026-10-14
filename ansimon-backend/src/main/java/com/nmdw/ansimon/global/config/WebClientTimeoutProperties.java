package com.nmdw.ansimon.global.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.time.Duration;

/**
 * 모든 외부 API WebClient가 공유하는 연결 및 응답 대기 시간을 설정에서 바인딩합니다.
 * {@link WebClientConfig}가 이 값을 Reactor Netty 클라이언트에 적용하므로, 서비스별 어댑터는 타임아웃 정책을 직접 결정하지 않습니다.
 * 기본값은 연결 2초와 응답 5초이며 환경 설정으로 조정할 수 있습니다.
 */
@ConfigurationProperties(prefix = "ansimon.web-client")
public class WebClientTimeoutProperties {

    private Duration connectionTimeout = Duration.ofSeconds(2);
    private Duration responseTimeout = Duration.ofSeconds(5);

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
