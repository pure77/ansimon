package com.nmdw.ansimon.guidance.dto;

import com.nmdw.ansimon.guidance.domain.GuidanceStatus;
import com.nmdw.ansimon.guidance.domain.InterventionPlan;
import io.swagger.v3.oas.annotations.media.Schema;

import java.time.Instant;

@Schema(description = "생성된 안내계획 요약 응답")
public record InterventionPlanSummaryResponse(
        @Schema(description = "안내계획 식별자", example = "1") Long id,
        @Schema(description = "대상 노인 식별자", example = "1") Long elderlyId,
        @Schema(description = "안내계획 상태", example = "READY_FOR_REVIEW") GuidanceStatus status,
        @Schema(description = "행동지침·쉼터 안내문 JSON") String guidanceJson,
        @Schema(description = "전화 질문 순서 JSON") String questionsJson,
        @Schema(description = "근거 문서 ID JSON") String evidenceChunkIdsJson,
        @Schema(description = "생성 시각", example = "2026-08-18T01:00:00Z") Instant createdAt
) {
    public static InterventionPlanSummaryResponse from(InterventionPlan plan) {
        return new InterventionPlanSummaryResponse(plan.getId(), plan.getElderly().getId(), plan.getStatus(),
                plan.getGuidanceJson(), plan.getQuestionsJson(), plan.getEvidenceChunkIdsJson(), plan.getCreatedAt());
    }
}
