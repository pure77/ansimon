package com.nmdw.ansimon.global.security;

import com.nmdw.ansimon.global.response.ApiResponse;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpHeaders;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.JwsHeader;
import org.springframework.security.oauth2.jwt.JwtClaimsSet;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.JwtEncoderParameters;
import org.springframework.security.oauth2.jwt.NimbusJwtEncoder;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;

import com.nimbusds.jose.jwk.source.ImmutableSecret;

import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.time.Instant;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.options;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(controllers = AdminApiSecurityTest.ProbeController.class)
@Import({AdminApiSecurityTest.ProbeController.class, SecurityConfig.class})
class AdminApiSecurityTest {

    private static final String ADMIN_ORIGIN = "http://localhost:5500";
    private static final String INTERNAL_KEY = "test-internal-key-current-0000000000";

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private JwtEncoder jwtEncoder;

    @Test
    void rejectsAdminApiWithoutToken() throws Exception {
        mockMvc.perform(get("/api/v1/probe"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.error.code").value("GLOBAL_UNAUTHORIZED"));
    }

    @Test
    void rejectsMalformedToken() throws Exception {
        mockMvc.perform(get("/api/v1/probe").header(HttpHeaders.AUTHORIZATION, "Bearer not-a-jwt"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.error.code").value("GLOBAL_UNAUTHORIZED"));
    }

    @Test
    void acceptsValidAdminToken() throws Exception {
        String token = token(jwtEncoder, "ansimon-backend", Instant.now().plusSeconds(600));

        mockMvc.perform(get("/api/v1/probe").header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data").value("admin"));
    }

    @Test
    void rejectsExpiredToken() throws Exception {
        String token = token(jwtEncoder, "ansimon-backend", Instant.now().minusSeconds(600));

        mockMvc.perform(get("/api/v1/probe").header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void rejectsTokenSignedWithAnotherSecret() throws Exception {
        JwtEncoder foreign = new NimbusJwtEncoder(new ImmutableSecret<>(new SecretKeySpec(
                "another-secret-0000000000000000000000".getBytes(StandardCharsets.UTF_8), "HmacSHA256")));
        String token = token(foreign, "ansimon-backend", Instant.now().plusSeconds(600));

        mockMvc.perform(get("/api/v1/probe").header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void rejectsTokenFromAnotherIssuer() throws Exception {
        String token = token(jwtEncoder, "someone-else", Instant.now().plusSeconds(600));

        mockMvc.perform(get("/api/v1/probe").header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void leavesLoginOpenWithoutToken() throws Exception {
        mockMvc.perform(post("/api/v1/auth/login"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data").value("login"));
    }

    @Test
    void grantsCorsPreflightToTheAdminFrontendWithoutToken() throws Exception {
        mockMvc.perform(options("/api/v1/probe")
                        .header(HttpHeaders.ORIGIN, ADMIN_ORIGIN)
                        .header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, "GET")
                        .header(HttpHeaders.ACCESS_CONTROL_REQUEST_HEADERS, "authorization"))
                .andExpect(status().isOk())
                .andExpect(header().string(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN, ADMIN_ORIGIN));
    }

    @Test
    void adminTokenDoesNotOpenInternalApi() throws Exception {
        String token = token(jwtEncoder, "ansimon-backend", Instant.now().plusSeconds(600));

        mockMvc.perform(post("/internal/v1/probe").header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isUnauthorized());
        mockMvc.perform(post("/internal/v1/probe").header(HttpHeaders.AUTHORIZATION, "Bearer " + INTERNAL_KEY))
                .andExpect(status().isOk());
    }

    @Test
    void internalKeyDoesNotOpenAdminApi() throws Exception {
        mockMvc.perform(get("/api/v1/probe").header(HttpHeaders.AUTHORIZATION, "Bearer " + INTERNAL_KEY))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void leavesNonApiPathsPublic() throws Exception {
        mockMvc.perform(get("/probe-public"))
                .andExpect(status().isOk());
    }

    private static String token(JwtEncoder encoder, String issuer, Instant expiresAt) {
        JwtClaimsSet claims = JwtClaimsSet.builder()
                .issuer(issuer)
                .subject("admin")
                .issuedAt(expiresAt.minusSeconds(3600))
                .expiresAt(expiresAt)
                .claim("scope", "admin")
                .build();
        return encoder.encode(JwtEncoderParameters.from(JwsHeader.with(MacAlgorithm.HS256).build(), claims))
                .getTokenValue();
    }

    @RestController
    static class ProbeController {
        @GetMapping("/api/v1/probe") ApiResponse<String> admin() { return ApiResponse.success("admin"); }
        @PostMapping("/api/v1/auth/login") ApiResponse<String> login() { return ApiResponse.success("login"); }
        @PostMapping("/internal/v1/probe") ApiResponse<String> internal() { return ApiResponse.success("internal"); }
        @GetMapping("/probe-public") ApiResponse<String> open() { return ApiResponse.success("public"); }
    }
}
