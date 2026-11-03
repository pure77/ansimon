package com.nmdw.ansimon.global.security;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class InternalApiPropertiesTest {

    private static final String KEY = "test-internal-key-current-0000000000";

    @Test
    void trimsKeysAndDropsBlankEntries() {
        InternalApiProperties properties = new InternalApiProperties(List.of("  " + KEY + "  ", "", "   "));

        assertThat(properties.apiKeys()).containsExactly(KEY);
    }

    @Test
    void refusesToStartWithoutAnyKey() {
        assertThatThrownBy(() -> new InternalApiProperties(null))
                .isInstanceOf(IllegalStateException.class);
        assertThatThrownBy(() -> new InternalApiProperties(List.of(" ")))
                .isInstanceOf(IllegalStateException.class);
    }

    @Test
    void refusesKeysShorterThan32Characters() {
        assertThatThrownBy(() -> new InternalApiProperties(List.of("short-key")))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("32");
    }
}
