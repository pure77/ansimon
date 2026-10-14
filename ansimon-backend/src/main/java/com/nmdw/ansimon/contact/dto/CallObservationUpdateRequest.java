package com.nmdw.ansimon.contact.dto;

import com.nmdw.ansimon.contact.domain.TriState;
import io.swagger.v3.oas.annotations.media.Schema;

/**
 * 저장된 통화 결과를 담당자가 교정할 때 사용하는 부분 수정 요청입니다.
 * 전달된 값만 반영하고 비어 있는 항목은 기존 값을 유지합니다.
 */
@Schema(description = "통화 결과 교정 요청. 전달한 항목만 수정됩니다.")
public record CallObservationUpdateRequest(
        @Schema(description = "통화 내용과 조치 내용 요약", example = "복지사 확인 결과 이동 지원은 불필요함")
        String summary,

        @Schema(description = "쉼터 이동 의향", example = "NO") TriState shelterIntent,
        @Schema(description = "혼자 이동 가능 여부", example = "YES") TriState canMoveAlone,
        @Schema(description = "도움 필요 여부", example = "NO") TriState helpNeeded,
        @Schema(description = "증상 언급 여부", example = "NO") TriState symptomMentioned
) {
}
