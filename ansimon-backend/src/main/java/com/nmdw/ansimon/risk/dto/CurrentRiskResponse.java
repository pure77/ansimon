package com.nmdw.ansimon.risk.dto;

import com.nmdw.ansimon.risk.domain.RiskLevel;
import com.nmdw.ansimon.risk.domain.RiskSnapshot;
import io.swagger.v3.oas.annotations.media.Schema;

import java.math.BigDecimal;
import java.time.Instant;

/**
 * 화면이 지금 쓸 위험도 값입니다.
 * ML 호출이 실패해 지난 예측을 대신 내보낼 때는 stale이 true가 되고, 화면은 값이 오래되었음을 밝힙니다.
 */
@Schema(description = "현재 위험도")
public record CurrentRiskResponse(
        @Schema(description = "위험도 스냅샷 식별자", example = "12") Long id,
        @Schema(description = "행정구역 코드", example = "11000") String regionCode,
        @Schema(description = "위험도 점수", example = "0.8200") BigDecimal riskScore,
        @Schema(description = "위험 등급", example = "high") RiskLevel riskLevel,
        @Schema(description = "대상 시작 시각") Instant targetStartAt,
        @Schema(description = "대상 종료 시각") Instant targetEndAt,
        @Schema(description = "피크 시작 시각") Instant peakStartAt,
        @Schema(description = "피크 종료 시각") Instant peakEndAt,
        @Schema(description = "모델 버전", example = "heatwave-xgb-v1+illness-xgb-v1") String modelVersion,
        @Schema(description = "생성 시각") Instant generatedAt,
        @Schema(description = "오늘 예측이 아니라 지난 예측을 대신 내보냈는지", example = "false") boolean stale
) {
    public static CurrentRiskResponse of(RiskSnapshot snapshot, boolean stale) {
        return new CurrentRiskResponse(snapshot.getId(), snapshot.getRegionCode(), snapshot.getRiskScore(),
                snapshot.getRiskLevel(), snapshot.getTargetStartAt(), snapshot.getTargetEndAt(),
                snapshot.getPeakStartAt(), snapshot.getPeakEndAt(), snapshot.getModelVersion(),
                snapshot.getGeneratedAt(), stale);
    }
}
