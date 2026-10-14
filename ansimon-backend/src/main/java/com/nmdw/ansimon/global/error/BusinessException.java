package com.nmdw.ansimon.global.error;

import java.util.Objects;

/**
 * 도메인 또는 애플리케이션 규칙 위반을 공통 {@link ErrorCode}와 함께 전달하는 런타임 예외입니다.
 * 서비스 계층은 HTTP 세부 사항을 알 필요 없이 이 예외를 던지고, {@link GlobalExceptionHandler}가 안전한 API 오류 응답으로 변환합니다.
 * 원인 예외를 보존해 내부 진단 경로를 유지하면서도 클라이언트에는 표준화된 코드와 메시지만 노출합니다.
 */
public class BusinessException extends RuntimeException {

    private final ErrorCode errorCode;

    public BusinessException(ErrorCode errorCode) {
        this(errorCode, null);
    }

    public BusinessException(ErrorCode errorCode, Throwable cause) {
        super(Objects.requireNonNull(errorCode, "errorCode must not be null").message(), cause);
        this.errorCode = errorCode;
    }

    public ErrorCode errorCode() {
        return errorCode;
    }
}
