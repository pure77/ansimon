package com.nmdw.ansimon.elderly.infra;

/**
 * TMAP 리버스 지오코딩 API 응답에서 서비스가 사용하는 법정동 코드만 역직렬화하는 내부 DTO입니다.
 * 도로명 주소로만 매칭되어 정방향 지오코딩 응답에 법정동 코드가 비어있는 경우, 좌표를 이 API에 다시 조회해 코드를 보완합니다.
 */
record TmapReverseGeocodingResponse(AddressInfo addressInfo) {

    record AddressInfo(String legalDongCode) {
    }
}
