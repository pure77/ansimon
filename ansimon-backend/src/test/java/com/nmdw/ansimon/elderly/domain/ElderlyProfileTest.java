package com.nmdw.ansimon.elderly.domain;

import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.ZoneId;

import static org.assertj.core.api.Assertions.assertThat;

class ElderlyProfileTest {

    private ElderlyProfile newProfile() {
        return ElderlyProfile.builder()
                .displayName("김안심")
                .phone("010-1234-5678")
                .address("서울시 종로구 1-1")
                .latitude(new BigDecimal("37.5730000"))
                .longitude(new BigDecimal("126.9794000"))
                .regionCode("11110")
                .consentStatus(ConsentStatus.CONSENTED)
                .build();
    }

    @Test
    void updatesDisplayNameAndPhoneTogether() {
        ElderlyProfile profile = newProfile();

        profile.updateProfile("박안심", "010-9999-0000");

        assertThat(profile.getDisplayName()).isEqualTo("박안심");
        assertThat(profile.getPhone()).isEqualTo("010-9999-0000");
    }

    @Test
    void updatesAddressWithItsRecomputedCoordinatesAndRegionCode() {
        ElderlyProfile profile = newProfile();

        profile.updateAddress("서울시 마포구 2-2", new BigDecimal("37.5500000"), new BigDecimal("126.9100000"), "11440");

        assertThat(profile.getAddress()).isEqualTo("서울시 마포구 2-2");
        assertThat(profile.getLatitude()).isEqualByComparingTo("37.5500000");
        assertThat(profile.getLongitude()).isEqualByComparingTo("126.9100000");
        assertThat(profile.getRegionCode()).isEqualTo("11440");
    }

    @Test
    void updatesConsentStatus() {
        ElderlyProfile profile = newProfile();

        profile.updateConsentStatus(ConsentStatus.WITHDRAWN);

        assertThat(profile.getConsentStatus()).isEqualTo(ConsentStatus.WITHDRAWN);
    }

    @Test
    void updatesHealthInfo() {
        ElderlyProfile profile = newProfile();

        profile.updateHealthInfo(LocalDate.of(1950, 3, 1), "고혈압, 당뇨");

        assertThat(profile.getBirthDate()).isEqualTo(LocalDate.of(1950, 3, 1));
        assertThat(profile.getHealthNote()).isEqualTo("고혈압, 당뇨");
    }

    @Test
    void computesAgeFromBirthDateAndReturnsNullWhenMissing() {
        ElderlyProfile withBirthDate = newProfile();
        withBirthDate.updateHealthInfo(LocalDate.now(ZoneId.of("Asia/Seoul")).minusYears(75), null);
        ElderlyProfile withoutBirthDate = newProfile();

        assertThat(withBirthDate.getAge()).isEqualTo(75);
        assertThat(withoutBirthDate.getAge()).isNull();
    }
}
