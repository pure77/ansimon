package com.nmdw.ansimon.risk.api;

import com.nmdw.ansimon.global.response.ApiResponse;
import com.nmdw.ansimon.risk.application.RiskService;
import com.nmdw.ansimon.risk.dto.CurrentRiskResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.enums.ParameterIn;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 화면이 지금 쓸 위험도를 돌려주는 공개 조회 API입니다.
 * 수동 예측 트리거는 {@code /internal/v1/risk/forecast}에 그대로 남아 있습니다.
 */
@Tag(name = "위험도", description = "화면이 표시할 현재 위험도를 조회합니다.")
@RestController
@RequestMapping("/api/v1/risk")
public class CurrentRiskController {

    private final RiskService riskService;

    public CurrentRiskController(RiskService riskService) {
        this.riskService = riskService;
    }

    @Operation(summary = "현재 위험도 조회",
            description = "오늘자 예측이 없으면 ML에 한 번 요청해 만들어 둡니다. region을 생략하면 서울로 봅니다.")
    @GetMapping("/current")
    public ApiResponse<CurrentRiskResponse> current(
            @Parameter(description = "지역명", example = "서울", in = ParameterIn.QUERY)
            @RequestParam(required = false) String region) {
        return ApiResponse.success(riskService.current(region));
    }
}
