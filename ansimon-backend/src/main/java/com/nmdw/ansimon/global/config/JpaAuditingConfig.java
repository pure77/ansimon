package com.nmdw.ansimon.global.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.data.jpa.repository.config.EnableJpaAuditing;

/**
 * JPA 엔티티의 생성·수정 시각을 Spring Data Auditing으로 자동 관리하도록 활성화합니다.
 * {@code BaseTimeEntity}처럼 감사 필드를 선언한 공통 엔티티 기반 클래스가 이 설정을 통해 저장 시점의 시간을 채웁니다.
 */
@Configuration
@EnableJpaAuditing
public class JpaAuditingConfig {
}