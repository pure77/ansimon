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

import java.time.Instant;
import java.util.Optional;

/**
 * 관리자 아이디·비밀번호를 확인하고 액세스 토큰을 발급합니다.
 * 아이디가 없을 때도 같은 비용의 해시 비교를 수행하고 같은 오류를 돌려줘, 응답으로 계정 존재 여부가 드러나지 않게 합니다.
 */
@Service
public class AuthService {

    private final AdminAccountRepository adminAccountRepository;
    private final AccessTokenIssuer accessTokenIssuer;
    private final PasswordEncoder passwordEncoder;
    private final String dummyHash;

    public AuthService(AdminAccountRepository adminAccountRepository,
                       AccessTokenIssuer accessTokenIssuer,
                       PasswordEncoder passwordEncoder) {
        this.adminAccountRepository = adminAccountRepository;
        this.accessTokenIssuer = accessTokenIssuer;
        this.passwordEncoder = passwordEncoder;
        this.dummyHash = passwordEncoder.encode("ansimon-timing-equalizer");
    }

    @Transactional
    public LoginResponse login(LoginRequest request) {
        Optional<AdminAccount> account = adminAccountRepository.findByLoginId(request.loginId().trim());
        String hash = account.map(AdminAccount::getPasswordHash).orElse(dummyHash);
        boolean matches = passwordEncoder.matches(request.password(), hash);
        if (account.isEmpty() || !matches) {
            throw new BusinessException(ErrorCode.INVALID_CREDENTIALS);
        }
        AdminAccount admin = account.get();
        admin.recordLogin(Instant.now());
        AccessTokenIssuer.IssuedToken token = accessTokenIssuer.issue(admin.getLoginId());
        return new LoginResponse(token.value(), "Bearer", token.expiresInSeconds());
    }
}
