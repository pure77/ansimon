package com.nmdw.ansimon.global.util;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class RegionCodesTest {

    @Test
    void extractsTheSiDoPrefixAndResolvesKnownRegionNames() {
        assertThat(RegionCodes.siDoCode("1114000000")).isEqualTo("11");
        assertThat(RegionCodes.siDoCodeForName("서울")).isEqualTo("11");
    }

    @Test
    void rejectsInvalidInput() {
        assertThatThrownBy(() -> RegionCodes.siDoCode("1")).isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> RegionCodes.siDoCodeForName("대전")).isInstanceOf(IllegalArgumentException.class);
    }
}
