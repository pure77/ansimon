package com.nmdw.ansimon.global.converter;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(controllers = EnumCodeConverterFactoryTest.TestController.class)
@Import(EnumCodeConverterFactoryTest.TestController.class)
class EnumCodeConverterFactoryTest {

    private final EnumCodeConverterFactory factory = new EnumCodeConverterFactory();

    @Autowired
    private MockMvc mockMvc;

    @Test
    void convertsAnExplicitEnumCodeToItsEnumConstant() {
        DeliveryMode result = factory.getConverter(DeliveryMode.class).convert("scheduled");

        assertThat(result).isEqualTo(DeliveryMode.SCHEDULED);
    }

    @Test
    void rejectsAnUnknownEnumCodeInsteadOfSelectingAnArbitraryConstant() {
        assertThatThrownBy(() -> factory.getConverter(DeliveryMode.class).convert("unknown"))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void bindsAnExplicitEnumCodeFromARequestParameter() throws Exception {
        mockMvc.perform(get("/test/delivery").param("mode", "scheduled"))
                .andExpect(status().isOk())
                .andExpect(content().string("scheduled"));
    }

    @Test
    void mapsAnUnknownEnumCodeFromARequestParameterToBadRequest() throws Exception {
        mockMvc.perform(get("/test/delivery").param("mode", "unknown"))
                .andExpect(status().isBadRequest());
    }

    private enum DeliveryMode implements EnumCode {
        IMMEDIATE("immediate"),
        SCHEDULED("scheduled");

        private final String code;

        DeliveryMode(String code) {
            this.code = code;
        }

        @Override
        public String code() {
            return code;
        }
    }

    @RestController
    @RequestMapping("/test")
    static class TestController {

        @GetMapping("/delivery")
        String delivery(@RequestParam DeliveryMode mode) {
            return mode.code();
        }
    }
}
