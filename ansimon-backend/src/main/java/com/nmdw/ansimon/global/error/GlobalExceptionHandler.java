package com.nmdw.ansimon.global.error;

import com.nmdw.ansimon.global.response.ApiResponse;
import com.nmdw.ansimon.global.response.ErrorResponse;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.validation.BindException;
import org.springframework.validation.FieldError;
import org.springframework.web.HttpMediaTypeNotAcceptableException;
import org.springframework.web.HttpMediaTypeNotSupportedException;
import org.springframework.web.HttpRequestMethodNotSupportedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.ServletRequestBindingException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.HandlerMethodValidationException;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.servlet.resource.NoResourceFoundException;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.Map;

/**
 * 컨트롤러와 요청 바인딩 과정에서 발생한 예외를 표준 {@link ApiResponse} 실패 형식으로 변환하는 전역 MVC 예외 처리기입니다.
 * {@link BusinessException}과 {@link ExternalServiceException}은 각자의 {@link ErrorCode}를 유지하고, 검증·역직렬화·프레임워크 예외는 안전한 공통 코드로 분류합니다.
 * 필드 오류를 포함한 응답에서도 원본 입력값이나 내부 예외 메시지를 노출하지 않아 API 오류 응답의 보안 정책을 지킵니다.
 */
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(BusinessException.class)
    public ResponseEntity<ApiResponse<Void>> handleBusinessException(BusinessException exception) {
        return failure(exception.errorCode(), Map.of());
    }
    @ExceptionHandler(ExternalServiceException.class)
    public ResponseEntity<ApiResponse<Void>> handleExternalServiceException(ExternalServiceException exception) {
        return failure(exception.errorCode(), Map.of());
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ApiResponse<Void>> handleValidationException(MethodArgumentNotValidException exception) {
        List<Map<String, String>> fields = exception.getBindingResult().getFieldErrors().stream()
                .map(this::safeFieldDetail)
                .toList();
        return failure(ErrorCode.VALIDATION_ERROR, Map.of("fields", fields));
    }

    @ExceptionHandler({BindException.class, HandlerMethodValidationException.class, ServletRequestBindingException.class})
    public ResponseEntity<ApiResponse<Void>> handleRequestBinding(Exception exception) {
        return failure(ErrorCode.VALIDATION_ERROR, Map.of());
    }

    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    public ResponseEntity<ApiResponse<Void>> handleTypeMismatch(MethodArgumentTypeMismatchException exception) {
        return failure(ErrorCode.VALIDATION_ERROR, Map.of());
    }

    @ExceptionHandler(HttpMessageNotReadableException.class)
    public ResponseEntity<ApiResponse<Void>> handleUnreadableRequest(HttpMessageNotReadableException exception) {
        return failure(ErrorCode.MALFORMED_REQUEST, Map.of());
    }

    @ExceptionHandler(HttpMediaTypeNotSupportedException.class)
    public ResponseEntity<ApiResponse<Void>> handleUnsupportedMediaType(HttpMediaTypeNotSupportedException exception) {
        return failure(ErrorCode.UNSUPPORTED_MEDIA_TYPE, Map.of());
    }

    @ExceptionHandler(HttpRequestMethodNotSupportedException.class)
    public ResponseEntity<ApiResponse<Void>> handleUnsupportedMethod(HttpRequestMethodNotSupportedException exception) {
        return failure(ErrorCode.METHOD_NOT_ALLOWED, Map.of());
    }

    @ExceptionHandler(HttpMediaTypeNotAcceptableException.class)
    public ResponseEntity<ApiResponse<Void>> handleNotAcceptable(HttpMediaTypeNotAcceptableException exception) {
        return failure(ErrorCode.NOT_ACCEPTABLE, Map.of());
    }

    @ExceptionHandler(ResponseStatusException.class)
    public ResponseEntity<ApiResponse<Void>> handleResponseStatus(ResponseStatusException exception) {
        HttpStatusCode status = exception.getStatusCode();
        return status.is4xxClientError()
                ? failure(status, ErrorCode.VALIDATION_ERROR, Map.of())
                : failure(ErrorCode.INTERNAL_ERROR, Map.of());
    }

    @ExceptionHandler(NoResourceFoundException.class)
    public ResponseEntity<ApiResponse<Void>> handleMissingResource(NoResourceFoundException exception) {
        return failure(ErrorCode.RESOURCE_NOT_FOUND, Map.of());
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiResponse<Void>> handleUnexpectedException(Exception exception) {
        return failure(ErrorCode.INTERNAL_ERROR, Map.of());
    }

    private Map<String, String> safeFieldDetail(FieldError fieldError) {
        return Map.of("field", fieldError.getField(), "message", "Invalid value.");
    }

    private ResponseEntity<ApiResponse<Void>> failure(ErrorCode errorCode, Map<String, Object> details) {
        return failure(errorCode.status(), errorCode, details);
    }

    private ResponseEntity<ApiResponse<Void>> failure(HttpStatusCode status, ErrorCode errorCode,
                                                       Map<String, Object> details) {
        ErrorResponse error = new ErrorResponse(errorCode.code(), errorCode.message(), details);
        return ResponseEntity.status(status).body(ApiResponse.failure(error));
    }
}
