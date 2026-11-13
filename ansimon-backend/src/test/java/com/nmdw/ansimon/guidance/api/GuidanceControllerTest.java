package com.nmdw.ansimon.guidance.api;

import com.nmdw.ansimon.global.security.SecurityConfig;
import com.nmdw.ansimon.guidance.application.GuidanceService;
import com.nmdw.ansimon.guidance.dto.CareRunTriggerResponse;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.RequestPostProcessor;

import static org.mockito.Mockito.when;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(GuidanceController.class)
@Import(SecurityConfig.class)
class GuidanceControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private GuidanceService guidanceService;

    @Test
    void careRunIsReachableWithAdminToken() throws Exception {
        when(guidanceService.triggerCareRun(7L)).thenReturn(new CareRunTriggerResponse(7L, "CA_1", true));

        mockMvc.perform(post("/api/v1/guidance/care-runs/7").with(admin()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.elderlyId").value(7));
    }

    private static RequestPostProcessor admin() {
        return jwt().authorities(new SimpleGrantedAuthority("SCOPE_admin"));
    }
}
