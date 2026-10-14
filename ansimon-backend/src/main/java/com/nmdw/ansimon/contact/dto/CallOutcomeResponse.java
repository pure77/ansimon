package com.nmdw.ansimon.contact.dto;

import com.nmdw.ansimon.contact.domain.CallObservation;
import com.nmdw.ansimon.contact.domain.ContactStatus;
import com.nmdw.ansimon.contact.domain.TriState;
import com.nmdw.ansimon.guidance.domain.InterventionPlan;
import io.swagger.v3.oas.annotations.media.Schema;

import java.math.BigDecimal;
import java.time.Instant;

/**
 * 외부 결과 전송으로 함께 생성된 안내계획, 전화 작업, 통화 결과의 식별자와 저장된 값을 돌려줍니다.
 * 미응답이면 3상태 항목은 모두 UNKNOWN, 신뢰도는 0으로 기록됩니다.
 */
@Schema(description = "저장된 대응계획 + 통화 결과")
public record CallOutcomeResponse(
        @Schema(description = "안내계획 식별자", example = "10") Long interventionPlanId,
        @Schema(description = "전화 작업 식별자", example = "7") Long contactJobId,
        @Schema(description = "통화 결과 식별자", example = "5") Long callObservationId,
        @Schema(description = "통화 결과 상태", example = "ANSWERED") ContactStatus contactStatus,
        @Schema(description = "쉼터 이동 의향", example = "YES") TriState shelterIntent,
        @Schema(description = "혼자 이동 가능 여부", example = "NO") TriState canMoveAlone,
        @Schema(description = "도움 필요 여부", example = "YES") TriState helpNeeded,
        @Schema(description = "증상 언급 여부", example = "YES") TriState symptomMentioned,
        @Schema(description = "통화 내용과 조치 내용 요약") String summary,
        @Schema(description = "녹취·전사 참조값") String transcriptRef,
        @Schema(description = "요약 신뢰도", example = "0.9100") BigDecimal confidence,
        @Schema(description = "통화 종료 시각", example = "2026-08-19T02:30:00Z") Instant endedAt
) {
    public static CallOutcomeResponse of(InterventionPlan plan, CallObservation observation) {
        return new CallOutcomeResponse(plan.getId(), observation.getContactJob().getId(), observation.getId(),
                observation.getContactStatus(), observation.getShelterIntent(), observation.getCanMoveAlone(),
                observation.getHelpNeeded(), observation.getSymptomMentioned(), observation.getSummary(),
                observation.getTranscriptRef(), observation.getConfidence(), observation.getEndedAt());
    }
}
