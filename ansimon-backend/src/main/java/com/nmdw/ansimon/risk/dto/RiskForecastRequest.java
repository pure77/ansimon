package com.nmdw.ansimon.risk.dto;

/**
 * 위험도 예측 트리거 요청입니다. region 이 비어 있으면 "서울"로 간주합니다 (MVP는 서울만 지원).
 */
public record RiskForecastRequest(String region) {
}
