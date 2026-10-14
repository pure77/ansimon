package com.nmdw.ansimon.guidance.dto;

import com.nmdw.ansimon.elderly.domain.ConsentStatus;
import com.nmdw.ansimon.risk.domain.RiskLevel;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;

/** 안심온 커넥션의 POST /v1/care-runs 요청 계약입니다. */
public record CareRunRequest(Elderly elderly, Location location, Risk risk) {

    public record Elderly(Long id, String phone, Integer age, String healthNote,
                          String regionCode, ConsentStatus consentStatus) {
    }

    public record Location(BigDecimal latitude, BigDecimal longitude) {
    }

    public record Risk(Long id, BigDecimal score, RiskLevel level,
                       Instant targetStartAt, Instant targetEndAt,
                       Instant peakStartAt, Instant peakEndAt,
                       List<String> topFactors, String modelVersion) {
    }
}
