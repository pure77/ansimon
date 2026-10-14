package com.nmdw.ansimon.global.converter;

import com.fasterxml.jackson.annotation.JsonValue;

/**
 * API 계약이나 명시적 저장값으로 노출되는 안정적인 문자열 코드를 enum이 제공하도록 하는 공통 인터페이스입니다.
 * {@link EnumCodeConverterFactory}는 이 계약을 구현한 enum만 대상으로 요청 파라미터 문자열을 도메인 값으로 변환합니다.
 * enum 이름 변경과 무관하게 외부에 약속한 코드를 유지할 수 있도록 코드 값을 타입에 귀속합니다.
 */
public interface EnumCode {

    @JsonValue
    String code();
}
