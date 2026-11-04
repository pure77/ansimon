package com.nmdw.ansimon.auth.dto;

/**
 * 로그인 성공 시 돌려주는 액세스 토큰과 토큰 종류, 남은 유효시간(초)입니다.
 */
public record LoginResponse(
        String accessToken,
        String tokenType,
        long expiresIn
) {
}
