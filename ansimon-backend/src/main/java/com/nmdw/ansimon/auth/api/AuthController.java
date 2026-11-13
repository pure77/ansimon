package com.nmdw.ansimon.auth.api;

import com.nmdw.ansimon.auth.application.AuthService;
import com.nmdw.ansimon.auth.dto.LoginRequest;
import com.nmdw.ansimon.auth.dto.LoginResponse;
import com.nmdw.ansimon.global.response.ApiResponse;
import io.swagger.v3.oas.annotations.Operation;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 관리자 콘솔 로그인 API입니다. 토큰 없이 호출할 수 있는 유일한 {@code /api/**} 엔드포인트입니다.
 */
@RestController
@RequestMapping("/api/v1/auth")
public class AuthController {

    private final AuthService authService;

    public AuthController(AuthService authService) {
        this.authService = authService;
    }

    @Operation(summary = "관리자 로그인", description = "아이디·비밀번호를 확인하고 Bearer 액세스 토큰을 발급합니다.")
    @PostMapping("/login")
    public ApiResponse<LoginResponse> login(@Valid @RequestBody LoginRequest request) {
        return ApiResponse.success(authService.login(request));
    }
}
