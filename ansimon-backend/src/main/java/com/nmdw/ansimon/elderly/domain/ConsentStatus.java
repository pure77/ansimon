package com.nmdw.ansimon.elderly.domain;

import com.nmdw.ansimon.global.converter.EnumCode;
import io.swagger.v3.oas.annotations.media.Schema;

/**
 * 관리 대상 노인의 자동전화 동의 상태입니다.
 * 동의, 미동의, 철회를 구분해 자동전화 대상 포함 여부를 판단하는 기준으로 사용합니다.
 */
@Schema(description = "자동전화 동의 상태", example = "consented")
public enum ConsentStatus implements EnumCode {
    CONSENTED("consented"),
    NOT_CONSENTED("not_consented"),
    WITHDRAWN("withdrawn");

    private final String code;

    ConsentStatus(String code) {
        this.code = code;
    }

    @Override
    public String code() {
        return code;
    }
}
