package com.nmdw.ansimon.auth.domain;

import com.nmdw.ansimon.global.persistence.BaseTimeEntity;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.time.Instant;

/**
 * 관리자 콘솔에 로그인할 수 있는 운영자 계정입니다.
 * 비밀번호는 알고리즘 접두사가 붙은 해시로만 보관하며, 마지막 로그인 시각으로 사용 여부를 추적합니다.
 */
@Entity
@Table(name = "admin_account")
@Getter
@EqualsAndHashCode(of = "id", callSuper = false)
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class AdminAccount extends BaseTimeEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "login_id", nullable = false, length = 50, unique = true)
    private String loginId;

    @Column(name = "password_hash", nullable = false)
    private String passwordHash;

    @Column(name = "last_login_at")
    private Instant lastLoginAt;

    private AdminAccount(String loginId, String passwordHash) {
        this.loginId = loginId;
        this.passwordHash = passwordHash;
    }

    public static AdminAccount create(String loginId, String passwordHash) {
        return new AdminAccount(loginId, passwordHash);
    }

    public void recordLogin(Instant loggedInAt) {
        this.lastLoginAt = loggedInAt;
    }
}
