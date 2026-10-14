package com.nmdw.ansimon.risk.domain;

import com.nmdw.ansimon.global.converter.EnumCode;

public enum RiskLevel implements EnumCode {
    LOW("low"),
    MEDIUM("medium"),
    HIGH("high"),
    CRITICAL("critical");

    private final String code;

    RiskLevel(String code) {
        this.code = code;
    }

    @Override
    public String code() {
        return code;
    }
}
