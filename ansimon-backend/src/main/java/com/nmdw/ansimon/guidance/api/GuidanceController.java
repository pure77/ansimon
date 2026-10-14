package com.nmdw.ansimon.guidance.api;

import com.nmdw.ansimon.global.response.ApiResponse;
import com.nmdw.ansimon.guidance.application.GuidanceService;
import com.nmdw.ansimon.guidance.dto.CareRunTriggerResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 특정 노인의 대응계획 생성, 예방 전화, 통화 요약을 안심온 커넥션에 요청하는 내부 API입니다.
 */
@Tag(name = "안심 돌봄 실행 (내부)", description = "노인 정보와 최신 위험도로 커넥션의 전체 care-run을 실행합니다.")
@RestController
@RequestMapping("/internal/v1/guidance")
public class GuidanceController {

    private final GuidanceService guidanceService;

    public GuidanceController(GuidanceService guidanceService) {
        this.guidanceService = guidanceService;
    }

    @Operation(summary = "care-run 실행", description = "대응계획 생성, 전화, 요약을 요청합니다. 실제 저장은 결과 콜백에서 이루어집니다.")
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "실행 완료"),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "403", description = "자동전화 동의 없음"),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "422", description = "RAG 근거 검증 실패"),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "404", description = "노인 또는 위험도 스냅샷을 찾을 수 없음"),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "502", description = "커넥션 서버 오류"),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "504", description = "커넥션 서버 시간 초과")
    })
    @PostMapping("/care-runs/{elderlyId}")
    public ApiResponse<CareRunTriggerResponse> triggerCareRun(
            @Parameter(description = "노인 프로필 식별자", example = "1", required = true)
            @PathVariable Long elderlyId) {
        return ApiResponse.success(guidanceService.triggerCareRun(elderlyId));
    }
}
