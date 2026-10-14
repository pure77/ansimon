package com.nmdw.ansimon.global.response;

import java.util.Objects;

/**
 * 모든 외부 API 응답을 동일한 성공 여부·데이터·오류 구조로 감싸는 공통 응답 봉투입니다.
 * 컨트롤러와 {@code GlobalExceptionHandler}는 이 타입을 사용해 성공과 실패를 같은 최상위 JSON 계약으로 반환합니다.
 * 성공 시에는 {@code data}만, 실패 시에는 {@link ErrorResponse}만 채워 두 값이 함께 사용되지 않도록 합니다.
 */
public record ApiResponse<T>(
        boolean success,
        T data,
        ErrorResponse error
) {

    public static <T> ApiResponse<T> success(T data) {
        return new ApiResponse<>(true, data, null);
    }

    public static <T> ApiResponse<T> failure(ErrorResponse error) {
        return new ApiResponse<>(false, null, Objects.requireNonNull(error, "error must not be null"));
    }
}
