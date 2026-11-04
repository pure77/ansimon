package com.nmdw.ansimon.global.security;

import com.nmdw.ansimon.global.error.ErrorCode;
import com.nmdw.ansimon.global.response.ApiResponse;
import com.nmdw.ansimon.global.response.ErrorResponse;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.MediaType;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.web.AuthenticationEntryPoint;
import tools.jackson.databind.json.JsonMapper;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Map;

/**
 * 인증되지 않은 내부 API 요청에 401을 공통 {@link ApiResponse} 실패 형식으로 응답합니다.
 * 보안 필터는 컨트롤러 밖에서 동작해 {@code GlobalExceptionHandler}가 처리하지 못하므로, 같은 오류 계약을 여기서 직접 씁니다.
 * 키가 없는지 틀렸는지는 구분하지 않아, 호출자가 거절 사유로 키를 추측하지 못하게 합니다.
 */
public class JsonAuthenticationEntryPoint implements AuthenticationEntryPoint {

    private final JsonMapper jsonMapper;

    public JsonAuthenticationEntryPoint(JsonMapper jsonMapper) {
        this.jsonMapper = jsonMapper;
    }

    @Override
    public void commence(HttpServletRequest request, HttpServletResponse response, AuthenticationException exception)
            throws IOException {
        ErrorCode errorCode = ErrorCode.UNAUTHORIZED;
        response.setStatus(errorCode.status().value());
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        jsonMapper.writeValue(response.getOutputStream(), ApiResponse.failure(
                new ErrorResponse(errorCode.code(), errorCode.message(), Map.of())));
    }
}
