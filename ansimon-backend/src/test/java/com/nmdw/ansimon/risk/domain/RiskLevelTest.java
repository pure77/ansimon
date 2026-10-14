package com.nmdw.ansimon.risk.domain;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class RiskLevelTest {

    @Test
    void exposesLowercaseStableCodes() {
        assertThat(RiskLevel.LOW.code()).isEqualTo("low");
        assertThat(RiskLevel.MEDIUM.code()).isEqualTo("medium");
        assertThat(RiskLevel.HIGH.code()).isEqualTo("high");
        assertThat(RiskLevel.CRITICAL.code()).isEqualTo("critical");
    }
}
