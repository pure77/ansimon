package com.nmdw.ansimon.auth.application;

import com.nmdw.ansimon.auth.domain.AdminAccount;
import com.nmdw.ansimon.auth.dto.LoginRequest;
import com.nmdw.ansimon.auth.dto.LoginResponse;
import com.nmdw.ansimon.auth.infra.AdminAccountRepository;
import com.nmdw.ansimon.global.error.BusinessException;
import com.nmdw.ansimon.global.error.ErrorCode;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Optional;

/**
 * 관리자 아이디·비밀번호를 확인하고 액세스 토큰을 발급합니다.
 * 아이디가 없을 때도 같은 비용의 해시 비교를 수행하고 같은 오류를 돌려줘, 응답으로 계정 존재 여부가 드러나지 않게 합니다.
 * 같은 아이디로 시도가 몰리면 {@link LoginAttemptLimiter}가 비밀번호 확인 전에 시도 횟수를 먼저 예약하고, 한도를 넘으면 잠시 로그인을 막습니다.
 */
@Service
public class AuthService {

    private static final int BCRYPT_MAX_PASSWORD_BYTES = 72;
    private static final String TIMING_EQUALIZER_PASSWORD = "ansimon-timing-equalizer";

    private final AdminAccountRepository adminAccountRepository;
    private final AccessTokenIssuer accessTokenIssuer;
    private final PasswordEncoder passwordEncoder;
    private final LoginAttemptLimiter loginAttemptLimiter;
    private final String dummyHash;

    public AuthService(AdminAccountRepository adminAccountRepository,
                       AccessTokenIssuer accessTokenIssuer,
                       PasswordEncoder passwordEncoder,
                       LoginAttemptLimiter loginAttemptLimiter) {
        this.adminAccountRepository = adminAccountRepository;
        this.accessTokenIssuer = accessTokenIssuer;
        this.passwordEncoder = passwordEncoder;
        this.loginAttemptLimiter = loginAttemptLimiter;
        this.dummyHash = passwordEncoder.encode(TIMING_EQUALIZER_PASSWORD);
    }

    @Transactional
    public LoginResponse login(LoginRequest request) {
        String loginId = request.loginId().trim();
        if (!loginAttemptLimiter.tryAcquire(loginId)) {
            throw new BusinessException(ErrorCode.TOO_MANY_LOGIN_ATTEMPTS);
        }
        if (request.password().getBytes(StandardCharsets.UTF_8).length > BCRYPT_MAX_PASSWORD_BYTES) {
            // bcrypt 는 72바이트를 넘으면 예외를 던져 500 이 된다. 같은 비용의 더미 비교만 하고 같은 401 로 거절한다.
            passwordEncoder.matches(TIMING_EQUALIZER_PASSWORD, dummyHash);
            throw new BusinessException(ErrorCode.INVALID_CREDENTIALS);
        }
        Optional<AdminAccount> account = adminAccountRepository.findByLoginId(loginId);
        String hash = account.map(AdminAccount::getPasswordHash).orElse(dummyHash);
        boolean matches = passwordEncoder.matches(request.password(), hash);
        if (account.isEmpty() || !matches) {
            throw new BusinessException(ErrorCode.INVALID_CREDENTIALS);
        }
        loginAttemptLimiter.recordSuccess(loginId);
        AdminAccount admin = account.get();
        admin.recordLogin(Instant.now());
        AccessTokenIssuer.IssuedToken token = accessTokenIssuer.issue(admin.getLoginId());
        return new LoginResponse(token.value(), "Bearer", token.expiresInSeconds());
    }
}
