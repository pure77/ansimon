package com.nmdw.ansimon.risk.api;

import com.nmdw.ansimon.global.response.ApiResponse;
import com.nmdw.ansimon.risk.application.RiskService;
import com.nmdw.ansimon.risk.dto.RiskForecastRequest;
import com.nmdw.ansimon.risk.dto.RiskForecastResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * ML 서버에 위험도 예측을 수동으로 트리거하는 내부 API입니다.
 * ML이 아직 임의 날짜를 지원하지 않아 자동 스케줄러 대신 관리자 트리거로 운영합니다.
 */
@Tag(name = "위험도예측 (내부)", description = "ML 서버에 위험도 예측을 요청하고 RiskSnapshot으로 저장합니다.")
@RestController
@RequestMapping("/internal/v1/risk")
public class RiskController {

    private final RiskService riskService;

    public RiskController(RiskService riskService) {
        this.riskService = riskService;
    }

    @Operation(summary = "위험도 예측 트리거",
            description = "ML 서버에 지역 위험도 예측을 요청하고 결과를 RiskSnapshot으로 저장합니다. "
                    + "region을 생략하면 서울로 간주합니다 (MVP는 서울만 지원).")
    @PostMapping("/forecast")
    public ApiResponse<RiskForecastResponse> forecast(
            @RequestBody(required = false) RiskForecastRequest request) {
        RiskForecastRequest effectiveRequest = request != null ? request : new RiskForecastRequest(null);
        return ApiResponse.success(riskService.forecast(effectiveRequest));
    }
}
