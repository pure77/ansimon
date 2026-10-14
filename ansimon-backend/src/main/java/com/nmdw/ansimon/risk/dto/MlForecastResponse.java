package com.nmdw.ansimon.risk.dto;

/**
 * ML API(GET /v1/forecast)가 돌려주는 원시 예측 결과입니다.
 */
public record MlForecastResponse(
        String date,
        String region,
        Double heatwaveRiskScore,
        String heatwavePrediction,
        Double elderlyHeatIllnessRiskScore,
        String illnessWeatherEstimation,
        Integer historicalAnalogRows,
        String modelVersion
) {
}
