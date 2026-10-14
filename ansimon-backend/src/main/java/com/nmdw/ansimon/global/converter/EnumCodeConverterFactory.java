package com.nmdw.ansimon.global.converter;

import org.springframework.core.convert.converter.Converter;
import org.springframework.core.convert.converter.ConverterFactory;
import org.springframework.format.FormatterRegistry;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.util.Arrays;

/**
 * Spring MVC 요청 파라미터의 문자열 코드를 {@link EnumCode} 구현 enum 상수로 변환하고 변환기를 등록합니다.
 * 컨트롤러는 enum별 파서 구현 없이 안정적인 공개 코드를 받을 수 있고, 알 수 없는 코드는 즉시 검증 오류로 처리됩니다.
 * enum 이름이 아닌 {@link EnumCode#code()}를 비교해 API 계약과 내부 식별자를 분리합니다.
 */
@Component
public class EnumCodeConverterFactory implements ConverterFactory<String, EnumCode>, WebMvcConfigurer {

    @Override
    public void addFormatters(FormatterRegistry registry) {
        registry.addConverterFactory(this);
    }

    @Override
    public <T extends EnumCode> Converter<String, T> getConverter(Class<T> targetType) {
        T[] enumConstants = targetType.getEnumConstants();
        if (enumConstants == null) {
            throw new IllegalArgumentException("Target type must be an enum: " + targetType.getName());
        }

        return source -> Arrays.stream(enumConstants)
                .filter(enumConstant -> enumConstant.code().equals(source))
                .findFirst()
                .orElseThrow(() -> new IllegalArgumentException("Unknown enum code: " + source));
    }
}
