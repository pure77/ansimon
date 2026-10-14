package com.nmdw.ansimon.elderly.api;

import com.nmdw.ansimon.elderly.application.ElderlyService;
import com.nmdw.ansimon.elderly.domain.ConsentStatus;
import com.nmdw.ansimon.elderly.dto.ElderlyResponse;
import com.nmdw.ansimon.global.error.BusinessException;
import com.nmdw.ansimon.global.error.ErrorCode;
import com.nmdw.ansimon.global.error.GlobalExceptionHandler;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.math.BigDecimal;
import java.time.Instant;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(ElderlyController.class)
@Import(GlobalExceptionHandler.class)
class ElderlyControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private ElderlyService elderlyService;

    @Test
    void createsAndPartiallyUpdatesAnElderlyProfile() throws Exception {
        when(elderlyService.register(any())).thenReturn(response());
        when(elderlyService.update(eq(1L), any())).thenReturn(response());

        mockMvc.perform(post("/api/v1/elderly").contentType("application/json").content("""
                {"displayName":"김안심","phone":"010","address":"서울시 종로구 1-1","consentStatus":"consented"}
                """))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.data.consentStatus").value("consented"));
        mockMvc.perform(patch("/api/v1/elderly/1").contentType("application/json").content("{" + "\"consentStatus\":\"withdrawn\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true));
    }

    @Test
    void deletesAnElderlyProfile() throws Exception {
        mockMvc.perform(delete("/api/v1/elderly/1"))
                .andExpect(status().isNoContent());

        verify(elderlyService).delete(1L);
    }

    @Test
    void reportsAConflictWhenTheProfileStillHasInterventionHistory() throws Exception {
        doThrow(new BusinessException(ErrorCode.CONFLICT)).when(elderlyService).delete(1L);

        mockMvc.perform(delete("/api/v1/elderly/1"))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.success").value(false));
    }

    private ElderlyResponse response() {
        return new ElderlyResponse(1L, "김안심", "010", "서울시 종로구 1-1", new BigDecimal("37.5730000"),
                new BigDecimal("126.9794000"), "11110", ConsentStatus.CONSENTED, 75, "고혈압, 당뇨",
                Instant.now(), Instant.now());
    }
}
