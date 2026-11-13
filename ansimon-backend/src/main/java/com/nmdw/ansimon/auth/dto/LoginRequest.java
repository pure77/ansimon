package com.nmdw.ansimon.auth.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * 관리자 로그인 요청입니다. 비밀번호가 로그·예외 메시지로 새지 않도록 문자열 표현에서 가립니다.
 */
public record LoginRequest(
        @NotBlank @Size(max = 50) String loginId,
        @NotBlank @Size(max = 128) String password
) {

    @Override
    public String toString() {
        return "LoginRequest[loginId=" + loginId + ", password=****]";
    }
}
