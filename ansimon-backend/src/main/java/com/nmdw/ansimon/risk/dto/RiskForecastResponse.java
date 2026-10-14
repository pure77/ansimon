package com.nmdw.ansimon.risk.dto;

import com.nmdw.ansimon.risk.domain.RiskLevel;
import com.nmdw.ansimon.risk.domain.RiskSnapshot;

import java.math.BigDecimal;
import java.time.Instant;

/**
 * 저장된 RiskSnapshot 요약 응답입니다.
 */
public record RiskForecastResponse(
        Long id,
        String regionCode,
        BigDecimal riskScore,
        RiskLevel riskLevel,
        Instant targetStartAt,
        Instant targetEndAt,
        Instant peakStartAt,
        Instant peakEndAt,
        String modelVersion,
        Instant generatedAt
) {
    public static RiskForecastResponse from(RiskSnapshot snapshot) {
        return new RiskForecastResponse(snapshot.getId(), snapshot.getRegionCode(), snapshot.getRiskScore(),
                snapshot.getRiskLevel(), snapshot.getTargetStartAt(), snapshot.getTargetEndAt(),
                snapshot.getPeakStartAt(), snapshot.getPeakEndAt(), snapshot.getModelVersion(),
                snapshot.getGeneratedAt());
    }
}
