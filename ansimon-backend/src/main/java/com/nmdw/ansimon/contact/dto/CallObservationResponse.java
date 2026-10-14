package com.nmdw.ansimon.contact.dto;

import com.nmdw.ansimon.contact.domain.CallObservation;
import com.nmdw.ansimon.contact.domain.ContactStatus;
import com.nmdw.ansimon.contact.domain.TriState;
import io.swagger.v3.oas.annotations.media.Schema;

import java.math.BigDecimal;
import java.time.Instant;

/**
 * 저장된 통화 결과를 클라이언트에 돌려주는 응답입니다.
 * 미응답이면 3상태 항목은 모두 UNKNOWN, 신뢰도는 0으로 기록됩니다.
 */
@Schema(description = "저장된 통화 결과")
public record CallObservationResponse(
        @Schema(description = "통화 결과 식별자", example = "5") Long id,
        @Schema(description = "전화 작업 식별자", example = "1") Long contactJobId,
        @Schema(description = "통화 결과 상태", example = "ANSWERED") ContactStatus contactStatus,
        @Schema(description = "쉼터 이동 의향", example = "YES") TriState shelterIntent,
        @Schema(description = "혼자 이동 가능 여부", example = "NO") TriState canMoveAlone,
        @Schema(description = "도움 필요 여부", example = "YES") TriState helpNeeded,
        @Schema(description = "증상 언급 여부", example = "YES") TriState symptomMentioned,
        @Schema(description = "통화 내용과 조치 내용 요약") String summary,
        @Schema(description = "녹취·전사 참조값") String transcriptRef,
        @Schema(description = "요약 신뢰도", example = "0.9100") BigDecimal confidence,
        @Schema(description = "통화 종료 시각", example = "2026-08-18T02:30:00Z") Instant endedAt
) {
    public static CallObservationResponse from(CallObservation observation) {
        return new CallObservationResponse(observation.getId(), observation.getContactJob().getId(),
                observation.getContactStatus(), observation.getShelterIntent(), observation.getCanMoveAlone(),
                observation.getHelpNeeded(), observation.getSymptomMentioned(), observation.getSummary(),
                observation.getTranscriptRef(), observation.getConfidence(), observation.getEndedAt());
    }
}
