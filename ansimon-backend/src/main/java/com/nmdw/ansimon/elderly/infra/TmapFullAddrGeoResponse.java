package com.nmdw.ansimon.elderly.infra;

import java.util.List;

/**
 * TMAP 전체 주소 지오코딩 API 응답에서 서비스가 사용하는 좌표 정보만 역직렬화하는 내부 DTO입니다.
 */
record TmapFullAddrGeoResponse(CoordinateInfo coordinateInfo) {

    /**
     * TMAP 주소 검색 결과로 반환된 좌표 목록을 담는 컨테이너입니다.
     */
    record CoordinateInfo(List<Coordinate> coordinate) {
    }

    /**
     * 검색된 한 주소의 위도, 경도, 법정동 코드를 담는 좌표 정보입니다.
     * 도로명 주소로만 매칭된 경우 TMAP은 {@code lat}/{@code lon}/{@code legalDongCode}를 비워두고
     * {@code newLat}/{@code newLon}에만 값을 채워 반환하므로 두 좌표 필드를 함께 보관합니다.
     */
    record Coordinate(String lat, String lon, String legalDongCode, String newLat, String newLon) {
    }
}
