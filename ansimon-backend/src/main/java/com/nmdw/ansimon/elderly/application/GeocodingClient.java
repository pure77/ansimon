package com.nmdw.ansimon.elderly.application;

/**
 * 주소를 좌표와 행정구역 코드로 변환하는 외부 지오코딩 기능의 포트입니다.
 * 애플리케이션 계층이 특정 지도 제공자의 API 형식에 의존하지 않도록 경계를 제공합니다.
 */
public interface GeocodingClient {

    GeocodingResult geocode(String address);
}
