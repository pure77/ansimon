package com.nmdw.ansimon.auth.application;

import com.nmdw.ansimon.auth.domain.AdminAccount;
import com.nmdw.ansimon.auth.dto.LoginRequest;
import com.nmdw.ansimon.auth.dto.LoginResponse;
import com.nmdw.ansimon.auth.infra.AdminAccountRepository;
import com.nmdw.ansimon.global.error.BusinessException;
import com.nmdw.ansimon.global.error.ErrorCode;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.security.crypto.factory.PasswordEncoderFactories;
import org.springframework.security.crypto.password.PasswordEncoder;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.spy;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class AuthServiceTest {

    private final AdminAccountRepository repository = mock(AdminAccountRepository.class);
    private final AccessTokenIssuer tokenIssuer = mock(AccessTokenIssuer.class);
    private final PasswordEncoder passwordEncoder = spy(PasswordEncoderFactories.createDelegatingPasswordEncoder());
    private AuthService authService;
    private AdminAccount admin;

    @BeforeEach
    void setUp() {
        authService = new AuthService(repository, tokenIssuer, passwordEncoder);
        admin = AdminAccount.create("admin", passwordEncoder.encode("correct-horse-battery"));
    }

    @Test
    void issuesBearerTokenAndRecordsLoginOnValidCredentials() {
        when(repository.findByLoginId("admin")).thenReturn(Optional.of(admin));
        when(tokenIssuer.issue("admin")).thenReturn(new AccessTokenIssuer.IssuedToken("jwt-value", 3600));

        LoginResponse response = authService.login(new LoginRequest("admin", "correct-horse-battery"));

        assertThat(response.accessToken()).isEqualTo("jwt-value");
        assertThat(response.tokenType()).isEqualTo("Bearer");
        assertThat(response.expiresIn()).isEqualTo(3600);
        assertThat(admin.getLastLoginAt()).isNotNull();
    }

    @Test
    void rejectsWrongPasswordWithoutIssuingToken() {
        when(repository.findByLoginId("admin")).thenReturn(Optional.of(admin));

        assertThatThrownBy(() -> authService.login(new LoginRequest("admin", "wrong-password")))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).errorCode())
                .isEqualTo(ErrorCode.INVALID_CREDENTIALS);
        verify(tokenIssuer, never()).issue(anyString());
        assertThat(admin.getLastLoginAt()).isNull();
    }

    @Test
    void rejectsUnknownLoginIdTheSameWayAndStillComparesAHash() {
        when(repository.findByLoginId("ghost")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> authService.login(new LoginRequest("ghost", "whatever-password")))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).errorCode())
                .isEqualTo(ErrorCode.INVALID_CREDENTIALS);
        // 응답 시간으로 계정 존재 여부가 드러나지 않도록 해시 비교는 항상 한 번 수행한다
        verify(passwordEncoder).matches(eq("whatever-password"), anyString());
        verify(tokenIssuer, never()).issue(anyString());
    }

    @Test
    void rejectsPasswordLongerThan72BytesAsInvalidCredentialsWithoutRawCompare() {
        when(repository.findByLoginId("admin")).thenReturn(Optional.of(admin));
        String longPassword = "가".repeat(30); // UTF-8 90바이트: bcrypt 한도(72바이트) 초과

        assertThatThrownBy(() -> authService.login(new LoginRequest("admin", longPassword)))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).errorCode())
                .isEqualTo(ErrorCode.INVALID_CREDENTIALS);
        // 원문은 bcrypt 에 넘기지 않고(500 방지), 비용은 같게 더미 해시 비교를 한 번 수행한다
        verify(passwordEncoder, never()).matches(eq(longPassword), anyString());
        verify(passwordEncoder, times(1)).matches(anyString(), anyString());
        verify(tokenIssuer, never()).issue(anyString());
    }
}
