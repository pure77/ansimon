package com.nmdw.ansimon.global.response;

import java.util.Map;
import java.util.Objects;

/**
 * API 클라이언트에 전달할 안전한 오류 코드, 기본 메시지, 검증 관련 부가 정보를 표현합니다.
 * {@code GlobalExceptionHandler}가 {@code ErrorCode}를 바탕으로 만들고 {@link ApiResponse}의 실패 본문에 포함합니다.
 * 상세 정보는 불변 복사해 생성 뒤 변경을 막으며, 내부 예외 원인이나 민감한 요청값을 담지 않는 공개 계약입니다.
 */
public record ErrorResponse(
        String code,
        String message,
        Map<String, Object> details
) {

    public ErrorResponse {
        details = Map.copyOf(Objects.requireNonNull(details, "details must not be null"));
    }
}
