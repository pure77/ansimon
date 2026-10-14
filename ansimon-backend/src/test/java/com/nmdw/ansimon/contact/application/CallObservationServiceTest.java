package com.nmdw.ansimon.contact.application;

import com.nmdw.ansimon.contact.domain.CallObservation;
import com.nmdw.ansimon.contact.domain.ContactJob;
import com.nmdw.ansimon.contact.domain.ContactStatus;
import com.nmdw.ansimon.contact.domain.TriState;
import com.nmdw.ansimon.contact.dto.CallObservationResponse;
import com.nmdw.ansimon.contact.dto.CallObservationUpdateRequest;
import com.nmdw.ansimon.contact.infra.CallObservationRepository;
import com.nmdw.ansimon.elderly.domain.ConsentStatus;
import com.nmdw.ansimon.elderly.domain.ElderlyProfile;
import com.nmdw.ansimon.global.error.BusinessException;
import com.nmdw.ansimon.global.error.ErrorCode;
import com.nmdw.ansimon.guidance.domain.GuidanceStatus;
import com.nmdw.ansimon.guidance.domain.InterventionPlan;
import com.nmdw.ansimon.risk.domain.RiskLevel;
import com.nmdw.ansimon.risk.domain.RiskSnapshot;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.ObjectMapper;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class CallObservationServiceTest {

    private final CallObservationRepository repository = mock(CallObservationRepository.class);
    private final CallObservationService service = new CallObservationService(repository, new ObjectMapper());

    private final Instant endedAt = Instant.parse("2026-08-19T02:30:00Z");

    @Test
    void correctsOnlyTheJudgementFieldsThatWereSupplied() {
        CallObservation observation = observation();
        when(repository.findById(5L)).thenReturn(Optional.of(observation));

        CallObservationResponse response = service.update(5L, new CallObservationUpdateRequest(
                null, TriState.NO, null, null, null));

        assertThat(response.shelterIntent()).isEqualTo(TriState.NO);
        assertThat(response.canMoveAlone()).isEqualTo(TriState.NO);
        assertThat(response.helpNeeded()).isEqualTo(TriState.YES);
        assertThat(response.symptomMentioned()).isEqualTo(TriState.YES);
        assertThat(response.summary()).isEqualTo("어지러움을 호소해 쉼터 이동 지원이 필요합니다.");
    }

    @Test
    void correctsTheSummaryTextWhenSupplied() {
        CallObservation observation = observation();
        when(repository.findById(5L)).thenReturn(Optional.of(observation));

        CallObservationResponse response = service.update(5L, new CallObservationUpdateRequest(
                "복지사 확인 결과 이동 지원은 불필요함", null, null, TriState.NO, null));

        assertThat(response.summary()).isEqualTo("복지사 확인 결과 이동 지원은 불필요함");
        assertThat(response.helpNeeded()).isEqualTo(TriState.NO);
        assertThat(observation.getSummary()).isEqualTo("복지사 확인 결과 이동 지원은 불필요함");
    }

    @Test
    void keepsEveryFieldWhenAnEmptyCorrectionIsSubmitted() {
        CallObservation observation = observation();
        when(repository.findById(5L)).thenReturn(Optional.of(observation));

        CallObservationResponse response = service.update(5L,
                new CallObservationUpdateRequest("   ", null, null, null, null));

        assertThat(response.summary()).isEqualTo("어지러움을 호소해 쉼터 이동 지원이 필요합니다.");
        assertThat(response.shelterIntent()).isEqualTo(TriState.YES);
    }

    @Test
    void rejectsACorrectionForAnObservationThatDoesNotExist() {
        when(repository.findById(99L)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.update(99L,
                new CallObservationUpdateRequest("수정", null, null, null, null)))
                .isInstanceOfSatisfying(BusinessException.class,
                        exception -> assertThat(exception.errorCode()).isEqualTo(ErrorCode.RESOURCE_NOT_FOUND));
    }

    @Test
    void deletesAStoredObservation() {
        CallObservation observation = observation();
        when(repository.findById(5L)).thenReturn(Optional.of(observation));

        service.delete(5L);

        verify(repository).delete(observation);
    }

    @Test
    void rejectsDeletionOfAnObservationThatDoesNotExist() {
        when(repository.findById(99L)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.delete(99L))
                .isInstanceOfSatisfying(BusinessException.class,
                        exception -> assertThat(exception.errorCode()).isEqualTo(ErrorCode.RESOURCE_NOT_FOUND));
    }

    private CallObservation observation() {
        ElderlyProfile elderly = ElderlyProfile.builder().displayName("김안심").phone("010")
                .address("서울시 종로구 1-1").latitude(new BigDecimal("37.5730000"))
                .longitude(new BigDecimal("126.9794000")).regionCode("11110")
                .consentStatus(ConsentStatus.CONSENTED).build();
        RiskSnapshot riskSnapshot = RiskSnapshot.builder().regionCode("11110")
                .riskScore(new BigDecimal("0.8000")).riskLevel(RiskLevel.HIGH)
                .targetStartAt(endedAt).targetEndAt(endedAt.plusSeconds(3600))
                .modelVersion("heatwave-v1").generatedAt(endedAt).build();
        InterventionPlan plan = InterventionPlan.builder().elderly(elderly).riskSnapshot(riskSnapshot)
                .status(GuidanceStatus.APPROVED).guidanceJson("{}").questionsJson("[]")
                .evidenceChunkIdsJson("[]").build();
        ContactJob job = ContactJob.builder().elderly(elderly).interventionPlan(plan)
                .status(ContactStatus.COMPLETED).attemptCount(1).scheduledAt(endedAt)
                .idempotencyKey("call-abc-123").build();
        return CallObservation.builder().contactJob(job).contactStatus(ContactStatus.ANSWERED)
                .shelterIntent(TriState.YES).canMoveAlone(TriState.NO).helpNeeded(TriState.YES)
                .symptomMentioned(TriState.YES).summary("어지러움을 호소해 쉼터 이동 지원이 필요합니다.")
                .confidence(new BigDecimal("0.9100")).endedAt(endedAt).build();
    }
}
