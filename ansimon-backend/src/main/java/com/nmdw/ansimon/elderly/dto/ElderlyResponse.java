package com.nmdw.ansimon.elderly.dto;

import com.nmdw.ansimon.elderly.domain.ConsentStatus;
import com.nmdw.ansimon.elderly.domain.ElderlyProfile;
import io.swagger.v3.oas.annotations.media.Schema;

import java.math.BigDecimal;
import java.time.Instant;

/**
 * 노인 프로필과 주소 기반 위치, 자동전화 동의 상태를 클라이언트에 반환하는 응답입니다.
 * {@link #from(ElderlyProfile)}을 통해 영속 엔티티를 API 계약으로 분리해 전달합니다.
 */
@Schema(description = "노인 프로필 응답")
public record ElderlyResponse(
        @Schema(description = "노인 프로필 식별자", example = "1") Long id,
        @Schema(description = "화면 표시 이름", example = "김안심") String displayName,
        @Schema(description = "전화번호", example = "010-1234-5678") String phone,
        @Schema(description = "거주지 전체 주소", example = "서울특별시 종로구 세종대로 1") String address,
        @Schema(description = "위도", example = "37.5730000") BigDecimal latitude,
        @Schema(description = "경도", example = "126.9794000") BigDecimal longitude,
        @Schema(description = "행정구역 코드", example = "11110") String regionCode,
        @Schema(description = "자동전화 동의 상태", example = "consented") ConsentStatus consentStatus,
        @Schema(description = "나이", example = "75") Integer age,
        @Schema(description = "기저질환/건강상태 메모", example = "고혈압, 당뇨") String healthNote,
        @Schema(description = "등록 시각", example = "2026-08-18T01:00:00Z") Instant createdAt,
        @Schema(description = "마지막 수정 시각", example = "2026-08-18T01:30:00Z") Instant updatedAt
) {
    public static ElderlyResponse from(ElderlyProfile profile) {
        return new ElderlyResponse(profile.getId(), profile.getDisplayName(), profile.getPhone(), profile.getAddress(),
                profile.getLatitude(), profile.getLongitude(), profile.getRegionCode(), profile.getConsentStatus(),
                profile.getAge(), profile.getHealthNote(), profile.getCreatedAt(), profile.getUpdatedAt());
    }
}
