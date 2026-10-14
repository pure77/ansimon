package com.nmdw.ansimon.global.persistence;

import jakarta.persistence.Column;
import jakarta.persistence.EntityListeners;
import jakarta.persistence.MappedSuperclass;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.annotation.LastModifiedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

import java.time.Instant;

/**
 * 영속 엔티티가 공통으로 상속하는 생성·수정 시각 기반 클래스입니다.
 * JPA Auditing이 저장과 수정 시점에 UTC 기준 {@link Instant} 필드를 자동으로 채우며, 실제 엔티티는 중복 매핑 없이 감사 정보를 갖습니다.
 * 이 클래스는 시간 기록만 담당하고 각 도메인의 상태 전이 또는 업무 정책은 소유하지 않습니다.
 */
@MappedSuperclass
@EntityListeners(AuditingEntityListener.class)
public abstract class BaseTimeEntity {

    @CreatedDate
    @Column(name = "created_at", nullable = false, updatable = false, columnDefinition = "DATETIME(6)")
    private Instant createdAt;

    @LastModifiedDate
    @Column(name = "updated_at", nullable = false, columnDefinition = "DATETIME(6)")
    private Instant updatedAt;

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }
}
