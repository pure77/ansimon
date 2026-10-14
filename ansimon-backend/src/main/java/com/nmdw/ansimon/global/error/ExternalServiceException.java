package com.nmdw.ansimon.global.error;

import org.springframework.web.reactive.function.client.WebClientException;

import java.util.Objects;

/**
 * 외부 API 호출 실패를 서비스 내부의 표준 {@link ErrorCode}로 표현하는 WebClient 예외입니다.
 * {@code WebClientErrorMapper}가 HTTP 오류와 네트워크 실패를 이 타입으로 정규화하고, {@link GlobalExceptionHandler}가 API 응답으로 변환합니다.
 * 호출한 서비스의 원본 오류 내용을 그대로 노출하지 않아 외부 연동 정보와 민감한 실패 세부 사항을 보호합니다.
 */
public class ExternalServiceException extends WebClientException {

    private final ErrorCode errorCode;

    public ExternalServiceException(ErrorCode errorCode) {
        this(errorCode, null);
    }

    public ExternalServiceException(ErrorCode errorCode, Throwable cause) {
        super(Objects.requireNonNull(errorCode, "errorCode must not be null").message(), cause);
        this.errorCode = errorCode;
    }

    public ErrorCode errorCode() {
        return errorCode;
    }
}
