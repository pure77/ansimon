package com.nmdw.ansimon.global.security;

import com.nmdw.ansimon.global.response.ApiResponse;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpHeaders;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.options;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(controllers = InternalApiSecurityTest.ProbeController.class)
@Import({InternalApiSecurityTest.ProbeController.class, SecurityConfig.class})
class InternalApiSecurityTest {

    private static final String CURRENT_KEY = "test-internal-key-current-0000000000";
    private static final String PREVIOUS_KEY = "test-internal-key-previous-000000000";
    private static final String ADMIN_ORIGIN = "http://localhost:5500";

    @Autowired
    private MockMvc mockMvc;

    @Test
    void rejectsInternalCallWithoutCredentials() throws Exception {
        mockMvc.perform(post("/internal/v1/probe"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.error.code").value("GLOBAL_UNAUTHORIZED"));
    }

    @Test
    void rejectsInternalCallWithWrongKey() throws Exception {
        mockMvc.perform(post("/internal/v1/probe")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer wrong-key-wrong-key-wrong-key-0000"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void rejectsInternalCallWithNonBearerScheme() throws Exception {
        mockMvc.perform(post("/internal/v1/probe")
                        .header(HttpHeaders.AUTHORIZATION, "Basic " + CURRENT_KEY))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void acceptsBothCurrentAndPreviousKeysDuringRotation() throws Exception {
        mockMvc.perform(post("/internal/v1/probe")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + CURRENT_KEY))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data").value("internal"));
        mockMvc.perform(post("/internal/v1/probe")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + PREVIOUS_KEY))
                .andExpect(status().isOk());
    }

    @Test
    void doesNotGrantCorsToBrowsersOnInternalApi() throws Exception {
        mockMvc.perform(options("/internal/v1/probe")
                        .header(HttpHeaders.ORIGIN, ADMIN_ORIGIN)
                        .header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, "POST"))
                .andExpect(header().doesNotExist(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN));
    }

    @RestController
    static class ProbeController {
        @PostMapping("/internal/v1/probe") ApiResponse<String> internal() { return ApiResponse.success("internal"); }
    }
}
