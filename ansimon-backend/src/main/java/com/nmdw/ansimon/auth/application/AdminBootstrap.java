package com.nmdw.ansimon.auth.application;

import com.nmdw.ansimon.auth.domain.AdminAccount;
import com.nmdw.ansimon.auth.infra.AdminAccountRepository;
import com.nmdw.ansimon.global.security.AdminBootstrapProperties;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

/**
 * 관리자 계정이 하나도 없을 때 환경변수로 받은 첫 계정을 한 번만 만듭니다.
 * 계정이 이미 있으면 아무것도 하지 않으므로, 배포 후 환경변수를 지우지 않아도 비밀번호가 덮어써지지 않습니다.
 */
@Component
public class AdminBootstrap implements ApplicationRunner {

    private static final Logger log = LoggerFactory.getLogger(AdminBootstrap.class);
    private static final int MIN_PASSWORD_LENGTH = 12;

    private final AdminAccountRepository adminAccountRepository;
    private final PasswordEncoder passwordEncoder;
    private final AdminBootstrapProperties properties;

    public AdminBootstrap(AdminAccountRepository adminAccountRepository,
                          PasswordEncoder passwordEncoder,
                          AdminBootstrapProperties properties) {
        this.adminAccountRepository = adminAccountRepository;
        this.passwordEncoder = passwordEncoder;
        this.properties = properties;
    }

    @Override
    public void run(ApplicationArguments args) {
        if (adminAccountRepository.count() > 0) {
            return;
        }
        if (!StringUtils.hasText(properties.loginId()) || !StringUtils.hasText(properties.password())) {
            log.warn("No admin account exists. Set ADMIN_BOOTSTRAP_LOGIN_ID and ADMIN_BOOTSTRAP_PASSWORD to create one.");
            return;
        }
        if (properties.password().length() < MIN_PASSWORD_LENGTH) {
            throw new IllegalStateException("ADMIN_BOOTSTRAP_PASSWORD must be at least 12 characters");
        }
        String loginId = properties.loginId().trim();
        adminAccountRepository.save(AdminAccount.create(loginId, passwordEncoder.encode(properties.password())));
        log.info("Created the first admin account '{}'.", loginId);
    }
}
