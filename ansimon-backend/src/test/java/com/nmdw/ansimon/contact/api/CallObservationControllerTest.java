package com.nmdw.ansimon.contact.api;

import com.nmdw.ansimon.contact.application.CallObservationService;
import com.nmdw.ansimon.contact.domain.ContactStatus;
import com.nmdw.ansimon.contact.domain.TriState;
import com.nmdw.ansimon.contact.dto.CallObservationResponse;
import com.nmdw.ansimon.global.error.BusinessException;
import com.nmdw.ansimon.global.error.ErrorCode;
import com.nmdw.ansimon.global.error.GlobalExceptionHandler;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
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
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(CallObservationController.class)
@Import(GlobalExceptionHandler.class)
class CallObservationControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private CallObservationService callObservationService;

    @Test
    void correctsAStoredCallObservation() throws Exception {
        when(callObservationService.update(eq(5L), any())).thenReturn(new CallObservationResponse(
                5L, 7L, ContactStatus.ANSWERED, TriState.NO, TriState.YES, TriState.NO, TriState.NO,
                "복지사 확인 결과 이동 지원은 불필요함", null, new BigDecimal("0.9100"),
                Instant.parse("2026-08-19T02:30:00Z")));

        mockMvc.perform(patch("/api/v1/contact/observations/5")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"summary\":\"복지사 확인 결과 이동 지원은 불필요함\",\"helpNeeded\":\"NO\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.helpNeeded").value("NO"))
                .andExpect(jsonPath("$.data.summary").value("복지사 확인 결과 이동 지원은 불필요함"));
    }

    @Test
    void reportsNotFoundWhenCorrectingAnUnknownObservation() throws Exception {
        when(callObservationService.update(eq(99L), any()))
                .thenThrow(new BusinessException(ErrorCode.RESOURCE_NOT_FOUND));

        mockMvc.perform(patch("/api/v1/contact/observations/99")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"helpNeeded\":\"NO\"}"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.success").value(false));
    }

    @Test
    void deletesAStoredCallObservation() throws Exception {
        mockMvc.perform(delete("/api/v1/contact/observations/5"))
                .andExpect(status().isNoContent());

        verify(callObservationService).delete(5L);
    }

    @Test
    void reportsNotFoundWhenDeletingAnUnknownObservation() throws Exception {
        doThrow(new BusinessException(ErrorCode.RESOURCE_NOT_FOUND)).when(callObservationService).delete(99L);

        mockMvc.perform(delete("/api/v1/contact/observations/99"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.success").value(false));
    }
}
