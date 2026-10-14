package com.nmdw.ansimon.contact.api;

import com.nmdw.ansimon.contact.application.ContactService;
import com.nmdw.ansimon.contact.domain.ContactStatus;
import com.nmdw.ansimon.contact.domain.TriState;
import com.nmdw.ansimon.contact.dto.CallOutcomeResponse;
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
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(ContactController.class)
@Import(GlobalExceptionHandler.class)
class ContactControllerTest {

    private static final String ANSWERED_OUTCOME = """
            {"elderlyId":1,"externalCallId":"call-abc-123",
             "plan":{"actionGuidance":"실내에 머무르며 수분을 섭취하세요.",
                     "shelterRecommendationText":"종로구민센터 쉼터로 이동을 권장합니다.",
                     "callQuestionOrder":["호흡 확인"],"evidenceDocumentIds":["kma-guide-2024-03"]},
             "call":{"answered":true,"summary":"어지러움을 호소해 쉼터 이동 지원이 필요합니다.",
                     "shelterIntent":"YES","canMoveAlone":"NO","helpNeeded":"YES","symptomMentioned":"YES",
                     "confidence":0.91,"endedAt":"2026-08-19T02:30:00Z"}}
            """;

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private ContactService contactService;

    @Test
    void acceptsACompletedCallOutcomeAndReturnsTheStoredResult() throws Exception {
        when(contactService.registerCallOutcome(any())).thenReturn(new CallOutcomeResponse(
                10L, 7L, 5L, ContactStatus.ANSWERED, TriState.YES, TriState.NO, TriState.YES, TriState.YES,
                "어지러움을 호소해 쉼터 이동 지원이 필요합니다.", null, new BigDecimal("0.91"),
                Instant.parse("2026-08-19T02:30:00Z")));

        mockMvc.perform(post("/internal/v1/contact/results")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(ANSWERED_OUTCOME))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.interventionPlanId").value(10))
                .andExpect(jsonPath("$.data.contactJobId").value(7))
                .andExpect(jsonPath("$.data.contactStatus").value("ANSWERED"))
                .andExpect(jsonPath("$.data.helpNeeded").value("YES"));
    }

    @Test
    void rejectsAnOutcomeMissingTheExternalCallId() throws Exception {
        mockMvc.perform(post("/internal/v1/contact/results")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(ANSWERED_OUTCOME.replace("\"externalCallId\":\"call-abc-123\"",
                                "\"externalCallId\":\"\"")))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false));
    }

    @Test
    void rejectsAnOutcomeWithoutAPlan() throws Exception {
        mockMvc.perform(post("/internal/v1/contact/results")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                        {"elderlyId":1,"externalCallId":"call-abc-123",
                         "call":{"answered":false,"endedAt":"2026-08-19T02:30:00Z"}}
                        """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false));
    }

    @Test
    void reportsAConflictWhenTheSameExternalCallIdIsSubmittedTwice() throws Exception {
        when(contactService.registerCallOutcome(any())).thenThrow(new BusinessException(ErrorCode.CONFLICT));

        mockMvc.perform(post("/internal/v1/contact/results")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(ANSWERED_OUTCOME))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.success").value(false));
    }
}
