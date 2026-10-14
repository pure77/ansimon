package com.nmdw.ansimon.global.config;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.json.JsonTest;
import org.springframework.context.annotation.Import;
import tools.jackson.databind.ObjectMapper;

import java.time.Instant;

import static org.assertj.core.api.Assertions.assertThat;

@JsonTest
@Import(JacksonConfig.class)
class JacksonConfigTest {
    @Autowired private ObjectMapper objectMapper;

    @Test
    void serializesInstantInAsiaSeoulWithIso8601Offset() throws Exception {
        assertThat(objectMapper.writeValueAsString(Instant.parse("2026-08-17T05:30:00Z")))
                .isEqualTo("\"2026-08-17T14:30:00+09:00\"");
    }

    @Test
    void deserializesIso8601OffsetToInstant() throws Exception {
        assertThat(objectMapper.readValue("\"2026-08-17T14:30:00+09:00\"", Instant.class))
                .isEqualTo(Instant.parse("2026-08-17T05:30:00Z"));
    }
}
