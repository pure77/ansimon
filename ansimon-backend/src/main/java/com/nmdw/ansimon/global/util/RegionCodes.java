package com.nmdw.ansimon.global.util;

import java.util.Map;

/**
 * 법정동 단위 regionCode 와 ML 이 돌려주는 지역명을 시도(2자리) 단위 코드로 정규화합니다.
 * ML 은 시도 단위로만 예측하고 노인 프로필은 법정동 단위 regionCode 를 쓰므로,
 * 둘을 시도 단위로 맞춰 RiskSnapshot 조회 시 exact-match 로 연결할 수 있게 합니다.
 */
public final class RegionCodes {

    private static final int SI_DO_CODE_LENGTH = 2;

    private static final Map<String, String> SI_DO_CODE_BY_NAME = Map.of(
            "서울", "11",
            "부산", "26"
    );

    private RegionCodes() {
    }

    public static String siDoCode(String fullRegionCode) {
        if (fullRegionCode == null || fullRegionCode.length() < SI_DO_CODE_LENGTH) {
            throw new IllegalArgumentException("regionCode must be at least "
                    + SI_DO_CODE_LENGTH + " digits: " + fullRegionCode);
        }
        return fullRegionCode.substring(0, SI_DO_CODE_LENGTH);
    }

    public static String siDoCodeForName(String regionName) {
        String code = SI_DO_CODE_BY_NAME.get(regionName);
        if (code == null) {
            throw new IllegalArgumentException("Unsupported region name: " + regionName);
        }
        return code;
    }
}
