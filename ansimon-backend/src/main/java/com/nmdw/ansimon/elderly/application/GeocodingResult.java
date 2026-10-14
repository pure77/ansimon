package com.nmdw.ansimon.elderly.application;

import java.math.BigDecimal;

/**
 * 지오코딩으로 정규화한 위도, 경도, 행정구역 코드를 전달하는 불변 결과입니다.
 */
public record GeocodingResult(BigDecimal latitude, BigDecimal longitude, String regionCode) {
}
