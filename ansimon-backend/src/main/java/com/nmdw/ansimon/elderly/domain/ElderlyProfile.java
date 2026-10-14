package com.nmdw.ansimon.elderly.domain;

import com.nmdw.ansimon.global.persistence.BaseTimeEntity;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.Period;
import java.time.ZoneId;

/**
 * 폭염 예방 지원의 관리 대상 노인 프로필을 표현하는 핵심 도메인 엔티티입니다.
 * 기본 연락 정보, 주소 기반 위치, 행정구역 코드, 자동전화 동의 상태를 일관된 단위로 관리하며
 * 주소 변경 시 위치 관련 값을 함께 변경하도록 도메인 연산을 제공합니다.
 */
@Entity
@Table(
        name = "elderly_profile",
        indexes = {
                @Index(name = "idx_elderly_region_code", columnList = "region_code"),
                @Index(name = "idx_elderly_phone_hash", columnList = "phone")
        }
)
@Getter
@EqualsAndHashCode(of = "id", callSuper = false)
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor(access = AccessLevel.PRIVATE)
@Builder
public class ElderlyProfile extends BaseTimeEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "display_name", nullable = false, length = 100)
    private String displayName;

    @Column(name = "phone", nullable = false, length = 128)
    private String phone;

    @Column(name = "address", nullable = false, length = 255)
    private String address;

    @Column(name = "latitude", nullable = false, precision = 10, scale = 7)
    private BigDecimal latitude;

    @Column(name = "longitude", nullable = false, precision = 10, scale = 7)
    private BigDecimal longitude;

    @Column(name = "region_code", nullable = false, length = 20)
    private String regionCode;

    @Enumerated(EnumType.STRING)
    @Column(name = "consent_status", nullable = false, length = 30)
    private ConsentStatus consentStatus;

    @Column(name = "birth_date")
    private LocalDate birthDate;

    @Column(name = "health_note", length = 500)
    private String healthNote;

    public void updateProfile(String displayName, String phone) {
        this.displayName = displayName;
        this.phone = phone;
    }

    public void updateAddress(String address, BigDecimal latitude, BigDecimal longitude, String regionCode) {
        this.address = address;
        this.latitude = latitude;
        this.longitude = longitude;
        this.regionCode = regionCode;
    }

    public void updateConsentStatus(ConsentStatus consentStatus) {
        this.consentStatus = consentStatus;
    }

    public void updateHealthInfo(LocalDate birthDate, String healthNote) {
        this.birthDate = birthDate;
        this.healthNote = healthNote;
    }

    public Integer getAge() {
        if (birthDate == null) {
            return null;
        }
        return Period.between(birthDate, LocalDate.now(ZoneId.of("Asia/Seoul"))).getYears();
    }
}
