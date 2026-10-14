package com.nmdw.ansimon.contact.dto;

import com.nmdw.ansimon.contact.domain.ContactStatus;
import com.nmdw.ansimon.contact.domain.TriState;
import io.swagger.v3.oas.annotations.media.Schema;

import java.math.BigDecimal;
import java.time.Instant;

/**
 * 통화 기록 목록 한 줄에 해당하는 응답입니다.
 * 목록 화면은 어르신 이름과 그 통화의 대응계획 문구까지 함께 보여주므로
 * 단건 교정 응답({@link CallObservationResponse})과 필드 구성이 다릅니다.
 */
@Schema(description = "통화 기록 목록 항목")
public record CallObservationListResponse(
        @Schema(description = "통화 결과 식별자", example = "5") Long id,
        @Schema(description = "전화 작업 식별자", example = "1") Long contactJobId,
        @Schema(description = "어르신 식별자", example = "10") Long elderlyId,
        @Schema(description = "어르신 이름", example = "김안심") String elderlyName,
        @Schema(description = "통화 결과 상태", example = "ANSWERED") ContactStatus contactStatus,
        @Schema(description = "쉼터 이동 의향", example = "YES") TriState shelterIntent,
        @Schema(description = "혼자 이동 가능 여부", example = "NO") TriState canMoveAlone,
        @Schema(description = "도움 필요 여부", example = "YES") TriState helpNeeded,
        @Schema(description = "증상 언급 여부", example = "YES") TriState symptomMentioned,
        @Schema(description = "통화 내용과 조치 내용 요약") String summary,
        @Schema(description = "요약 신뢰도", example = "0.9100") BigDecimal confidence,
        @Schema(description = "통화 종료 시각", example = "2026-08-18T02:30:00Z") Instant endedAt,
        @Schema(description = "이 통화의 조치 방안") String actionGuidance,
        @Schema(description = "쉼터 안내 문구") String shelterRecommendationText
) {
}
