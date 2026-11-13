package com.nmdw.ansimon.auth.infra;

import com.nmdw.ansimon.auth.domain.AdminAccount;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

/**
 * {@link AdminAccount}를 로그인 아이디로 조회하는 Spring Data JPA 저장소입니다.
 */
public interface AdminAccountRepository extends JpaRepository<AdminAccount, Long> {

    Optional<AdminAccount> findByLoginId(String loginId);
}
