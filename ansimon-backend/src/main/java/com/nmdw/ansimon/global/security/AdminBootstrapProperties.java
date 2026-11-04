package com.nmdw.ansimon.global.security;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * 관리자 계정이 하나도 없을 때 한 번만 만들 첫 계정의 아이디와 비밀번호를 바인딩합니다.
 * 가입 API를 두지 않으므로 운영자는 배포 환경변수로만 첫 계정을 만들 수 있습니다.
 */
@ConfigurationProperties(prefix = "ansimon.auth.bootstrap-admin")
public record AdminBootstrapProperties(
        String loginId,
        String password
) {

    @Override
    public String toString() {
        return "AdminBootstrapProperties[loginId=" + loginId + ", password=****]";
    }
}
