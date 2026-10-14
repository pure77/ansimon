package com.nmdw.ansimon.elderly.domain;

import com.nmdw.ansimon.global.converter.EnumCodeConverterFactory;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.json.JsonTest;
import tools.jackson.databind.ObjectMapper;

import static org.assertj.core.api.Assertions.assertThat;

@JsonTest
class ConsentStatusTest {

    @Autowired
    private ObjectMapper objectMapper;

    @Test
    void exposesStableLowercaseCodesForEachConsentState() {
        assertThat(ConsentStatus.CONSENTED.code()).isEqualTo("consented");
        assertThat(ConsentStatus.NOT_CONSENTED.code()).isEqualTo("not_consented");
        assertThat(ConsentStatus.WITHDRAWN.code()).isEqualTo("withdrawn");
    }

    @Test
    void convertsQueryParameterCodesToConsentStatusConstants() {
        ConsentStatus result = new EnumCodeConverterFactory().getConverter(ConsentStatus.class).convert("withdrawn");

        assertThat(result).isEqualTo(ConsentStatus.WITHDRAWN);
    }

    @Test
    void serializesAndDeserializesUsingTheCodeNotTheEnumName() throws Exception {
        String json = objectMapper.writeValueAsString(ConsentStatus.NOT_CONSENTED);

        assertThat(json).isEqualTo("\"not_consented\"");
        assertThat(objectMapper.readValue(json, ConsentStatus.class)).isEqualTo(ConsentStatus.NOT_CONSENTED);
    }
}
