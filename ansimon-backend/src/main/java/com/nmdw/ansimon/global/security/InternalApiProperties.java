package com.nmdw.ansimon.global.security;

import java.util.List;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.util.StringUtils;

/**
 * 서버끼리만 호출하는 {@code /internal/**} API가 받아들일 Bearer 키 목록을 설정에서 바인딩합니다.
 * 키를 목록으로 받아 새 키와 이전 키를 잠시 함께 허용하므로, 호출하는 서버의 키를 무중단으로 교체할 수 있습니다.
 * 키가 하나도 없거나 32자보다 짧으면 생성 시점에 실패시켜, 인증이 빠진 채 서버가 뜨는 일을 막습니다.
 */
@ConfigurationProperties(prefix = "ansimon.internal")
public record InternalApiProperties(
        List<String> apiKeys
) {

    private static final int MIN_KEY_LENGTH = 32;

    public InternalApiProperties {
        List<String> keys = apiKeys == null ? List.of() : apiKeys.stream()
                .filter(StringUtils::hasText)
                .map(String::trim)
                .toList();
        if (keys.isEmpty()) {
            throw new IllegalStateException("ansimon.internal.api-keys must contain at least one key");
        }
        if (keys.stream().anyMatch(key -> key.length() < MIN_KEY_LENGTH)) {
            throw new IllegalStateException("ansimon.internal.api-keys entries must be at least 32 characters");
        }
        apiKeys = keys;
    }
}
