package com.nmdw.ansimon.global.webclient;

import com.nmdw.ansimon.global.error.ErrorCode;
import com.nmdw.ansimon.global.error.ExternalServiceException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatusCode;

import java.util.UUID;
import java.util.concurrent.TimeoutException;

/**
 * 외부 HTTP 응답 상태와 전송 실패를 애플리케이션의 {@link ExternalServiceException} 및 {@link ErrorCode}로 정규화합니다.
 * {@code WebClientConfig}의 공통 필터가 이 매퍼를 사용해 도메인 어댑터에 일관된 실패 계약을 제공하고, 진단에 필요한 서비스·메서드·상관관계 ID만 로그에 남깁니다.
 * 원본 응답 본문이나 인증 정보는 기록·전달하지 않아 외부 연동 실패를 안전하게 처리합니다.
 */
public class WebClientErrorMapper {

    private static final Logger log = LoggerFactory.getLogger(WebClientErrorMapper.class);

    public ExternalServiceException forStatus(HttpStatusCode statusCode) {
        return forStatus(statusCode, ExternalRequestContext.unknown());
    }

    public ExternalServiceException forStatus(HttpStatusCode statusCode, ExternalRequestContext context) {
        ErrorCode errorCode = statusCode.is4xxClientError()
                ? ErrorCode.EXTERNAL_SERVICE_CLIENT_ERROR
                : ErrorCode.EXTERNAL_SERVICE_SERVER_ERROR;
        log.warn("External service response failed: service={}, method={}, endpoint={}, status={}, correlationId={}",
                context.serviceId(), context.method(), context.endpoint(), statusCode.value(), context.correlationId());
        return new ExternalServiceException(errorCode);
    }

    public ExternalServiceException forFailure(Throwable failure) {
        return forFailure(failure, ExternalRequestContext.unknown());
    }

    public ExternalServiceException forFailure(Throwable failure, ExternalRequestContext context) {
        ErrorCode errorCode = hasTimeoutCause(failure)
                ? ErrorCode.EXTERNAL_SERVICE_TIMEOUT
                : ErrorCode.EXTERNAL_SERVICE_SERVER_ERROR;
        log.warn("External service request failed: service={}, method={}, endpoint={}, status={}, correlationId={}",
                context.serviceId(), context.method(), context.endpoint(), "unavailable", context.correlationId());
        return new ExternalServiceException(errorCode);
    }

    private boolean hasTimeoutCause(Throwable failure) {
        Throwable current = failure;
        while (current != null) {
            if (current instanceof TimeoutException || current instanceof io.netty.handler.timeout.TimeoutException) {
                return true;
            }
            current = current.getCause();
        }
        return false;
    }

    /**
     * 외부 요청 실패를 분류·로깅할 때 필요한 최소한의 서비스 식별 정보를 보관합니다.
     * 서비스별 WebClient 필터가 요청 시 생성하며, 실제 URL이나 API 키 대신 안전한 서비스 ID와 고정 엔드포인트 표기를 사용합니다.
     */
    public record ExternalRequestContext(String serviceId, HttpMethod method, String endpoint, String correlationId) {

        public static ExternalRequestContext forService(String serviceId, HttpMethod method) {
            return new ExternalRequestContext(serviceId, method, "configured-service", UUID.randomUUID().toString());
        }

        private static ExternalRequestContext unknown() {
            return new ExternalRequestContext("unknown", null, "configured-service", "unavailable");
        }
    }
}