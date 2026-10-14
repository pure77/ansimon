package com.nmdw.ansimon.contact.dto;

import com.nmdw.ansimon.contact.domain.TriState;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;

/**
 * 외부 LLM/RAG 서버가 대응계획 생성과 전화를 모두 마친 뒤 한 번에 전달하는 최종 결과입니다.
 * 이 요청 하나로 안내계획, 전화 작업, 통화 결과가 함께 생성되므로 중간 상태 갱신은 받지 않습니다.
 */
@Schema(description = "외부 LLM/RAG 서버가 전달하는 대응계획 + 통화 결과")
public record CallOutcomeRequest(
        @Schema(description = "대상 노인 식별자", example = "1", requiredMode = Schema.RequiredMode.REQUIRED)
        @NotNull Long elderlyId,

        @Schema(description = "외부 서버가 부여한 통화 식별자. 중복 전송을 막는 멱등키로 사용합니다.", example = "call-abc-123", requiredMode = Schema.RequiredMode.REQUIRED)
        @NotBlank String externalCallId,

        @Schema(description = "생성된 대응계획", requiredMode = Schema.RequiredMode.REQUIRED)
        @NotNull @Valid Plan plan,

        @Schema(description = "통화 결과와 조치 내용 요약", requiredMode = Schema.RequiredMode.REQUIRED)
        @NotNull @Valid Call call
) {

    /**
     * LLM/RAG 서버가 생성한 대응계획 본문입니다.
     * 근거 문서 ID는 저장 후 원천 문서 레지스트리와 대조할 수 있도록 그대로 보관합니다.
     */
    @Schema(description = "생성된 대응계획")
    public record Plan(
            @Schema(description = "개인별 행동지침", requiredMode = Schema.RequiredMode.REQUIRED)
            @NotBlank String actionGuidance,

            @Schema(description = "추천 쉼터 안내문", requiredMode = Schema.RequiredMode.REQUIRED)
            @NotBlank String shelterRecommendationText,

            @Schema(description = "전화에서 사용한 질문 순서", requiredMode = Schema.RequiredMode.REQUIRED)
            @NotEmpty List<String> callQuestionOrder,

            @Schema(description = "RAG 근거 문서 ID 목록")
            List<String> evidenceDocumentIds
    ) {
    }

    /**
     * 통화 결과입니다. 미응답이면 요약과 3상태 항목은 비워 보내고 서버가 UNKNOWN으로 기록합니다.
     * 응답한 통화는 요약, 3상태 항목 네 개, 신뢰도를 모두 채워야 합니다.
     */
    @Schema(description = "통화 결과")
    public record Call(
            @Schema(description = "통화 응답 여부", example = "true", requiredMode = Schema.RequiredMode.REQUIRED)
            @NotNull Boolean answered,

            @Schema(description = "통화 내용과 조치 내용 요약. 응답한 통화는 필수입니다.")
            String summary,

            @Schema(description = "쉼터 이동 의향", example = "YES") TriState shelterIntent,
            @Schema(description = "혼자 이동 가능 여부", example = "NO") TriState canMoveAlone,
            @Schema(description = "도움 필요 여부", example = "YES") TriState helpNeeded,
            @Schema(description = "증상 언급 여부", example = "YES") TriState symptomMentioned,

            @Schema(description = "요약 신뢰도(0~1). 응답한 통화는 필수입니다.", example = "0.91")
            BigDecimal confidence,

            @Schema(description = "접근이 통제된 녹취·전사 참조값. 원문은 저장하지 않습니다.")
            String transcriptRef,

            @Schema(description = "통화 종료 시각", example = "2026-08-19T02:30:00Z", requiredMode = Schema.RequiredMode.REQUIRED)
            @NotNull Instant endedAt
    ) {
    }
}
