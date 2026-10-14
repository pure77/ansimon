package com.nmdw.ansimon.global.error;

import org.springframework.http.HttpStatus;

/**
 * 애플리케이션 전반에서 재사용하는 공개 오류 코드, 대응 HTTP 상태, 안전한 기본 메시지를 정의합니다.
 * 비즈니스 예외와 외부 서비스 예외, 프레임워크 예외 처리기가 이 enum을 공유해 클라이언트 응답 형식을 일관되게 유지합니다.
 * 내부 구현·외부 서비스의 상세 원인은 이 값에 포함하지 않아 민감한 실패 정보가 API로 새지 않게 합니다.
 */
public enum ErrorCode {
    VALIDATION_ERROR("GLOBAL_VALIDATION_ERROR", HttpStatus.BAD_REQUEST, "The request is invalid."),
    MALFORMED_REQUEST("GLOBAL_MALFORMED_REQUEST", HttpStatus.BAD_REQUEST, "The request could not be read."),
    UNSUPPORTED_MEDIA_TYPE("GLOBAL_UNSUPPORTED_MEDIA_TYPE", HttpStatus.UNSUPPORTED_MEDIA_TYPE, "The request media type is not supported."),
    NOT_ACCEPTABLE("GLOBAL_NOT_ACCEPTABLE", HttpStatus.NOT_ACCEPTABLE, "The requested response media type is not supported."),
    METHOD_NOT_ALLOWED("GLOBAL_METHOD_NOT_ALLOWED", HttpStatus.METHOD_NOT_ALLOWED, "The request method is not supported."),
    RESOURCE_NOT_FOUND("GLOBAL_RESOURCE_NOT_FOUND", HttpStatus.NOT_FOUND, "The requested resource was not found."),
    CONFLICT("GLOBAL_CONFLICT", HttpStatus.CONFLICT, "The request conflicts with the current state."),
    CONSENT_REQUIRED("GLOBAL_CONSENT_REQUIRED", HttpStatus.FORBIDDEN, "The elderly has not consented to automated calls."),
    GUIDANCE_GENERATION_BLOCKED("GLOBAL_GUIDANCE_GENERATION_BLOCKED", HttpStatus.UNPROCESSABLE_ENTITY, "Guidance generation was blocked by evidence verification."),
    INTERNAL_ERROR("GLOBAL_INTERNAL_ERROR", HttpStatus.INTERNAL_SERVER_ERROR, "An unexpected error occurred."),
    EXTERNAL_SERVICE_TIMEOUT("GLOBAL_EXTERNAL_SERVICE_TIMEOUT", HttpStatus.GATEWAY_TIMEOUT, "An external service timed out."),
    EXTERNAL_SERVICE_CLIENT_ERROR("GLOBAL_EXTERNAL_SERVICE_CLIENT_ERROR", HttpStatus.BAD_GATEWAY, "An external service rejected the request."),
    EXTERNAL_SERVICE_SERVER_ERROR("GLOBAL_EXTERNAL_SERVICE_SERVER_ERROR", HttpStatus.BAD_GATEWAY, "An external service is unavailable.");

    private final String code;
    private final HttpStatus status;
    private final String message;

    ErrorCode(String code, HttpStatus status, String message) {
        this.code = code;
        this.status = status;
        this.message = message;
    }

    public String code() { return code; }
    public HttpStatus status() { return status; }
    public String message() { return message; }
}
