package com.nmdw.ansimon.contact.application;

import com.nmdw.ansimon.contact.domain.CallObservation;
import com.nmdw.ansimon.contact.domain.ContactJob;
import com.nmdw.ansimon.contact.domain.ContactStatus;
import com.nmdw.ansimon.contact.domain.TriState;
import com.nmdw.ansimon.contact.dto.CallOutcomeRequest;
import com.nmdw.ansimon.contact.dto.CallOutcomeResponse;
import com.nmdw.ansimon.contact.infra.CallObservationRepository;
import com.nmdw.ansimon.contact.infra.ContactJobRepository;
import com.nmdw.ansimon.elderly.domain.ConsentStatus;
import com.nmdw.ansimon.elderly.domain.ElderlyProfile;
import com.nmdw.ansimon.elderly.infra.ElderlyProfileRepository;
import com.nmdw.ansimon.global.error.BusinessException;
import com.nmdw.ansimon.global.error.ErrorCode;
import com.nmdw.ansimon.guidance.domain.GuidanceStatus;
import com.nmdw.ansimon.guidance.domain.InterventionPlan;
import com.nmdw.ansimon.guidance.infra.InterventionPlanRepository;
import com.nmdw.ansimon.risk.domain.RiskLevel;
import com.nmdw.ansimon.risk.domain.RiskSnapshot;
import com.nmdw.ansimon.risk.infra.RiskSnapshotRepository;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import tools.jackson.databind.json.JsonMapper;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class ContactServiceTest {

    private final ElderlyProfileRepository elderlyProfileRepository = mock(ElderlyProfileRepository.class);
    private final RiskSnapshotRepository riskSnapshotRepository = mock(RiskSnapshotRepository.class);
    private final InterventionPlanRepository interventionPlanRepository = mock(InterventionPlanRepository.class);
    private final ContactJobRepository contactJobRepository = mock(ContactJobRepository.class);
    private final CallObservationRepository callObservationRepository = mock(CallObservationRepository.class);
    private final ContactService service = new ContactService(elderlyProfileRepository, riskSnapshotRepository,
            interventionPlanRepository, contactJobRepository, callObservationRepository, JsonMapper.builder().build());

    private final Instant endedAt = Instant.parse("2026-08-19T02:30:00Z");

    @Test
    void storesThePlanContactJobAndObservationForAnAnsweredCall() {
        givenElderlyAndRiskSnapshotExist();
        ArgumentCaptor<CallObservation> observationCaptor = ArgumentCaptor.forClass(CallObservation.class);

        CallOutcomeResponse response = service.registerCallOutcome(request(answeredCall()));

        assertThat(response.contactStatus()).isEqualTo(ContactStatus.ANSWERED);
        assertThat(response.summary()).isEqualTo("어지러움을 호소해 쉼터 이동 지원이 필요합니다.");

        verify(callObservationRepository).save(observationCaptor.capture());
        CallObservation observation = observationCaptor.getValue();
        assertThat(observation.getHelpNeeded()).isEqualTo(TriState.YES);
        assertThat(observation.getCanMoveAlone()).isEqualTo(TriState.NO);
        assertThat(observation.getConfidence()).isEqualByComparingTo(new BigDecimal("0.91"));
        assertThat(observation.getTranscriptRef()).isEqualTo("recording/2026/08/19/1");
    }

    @Test
    void linksTheStoredPlanToTheLatestRiskSnapshotOfTheElderlyRegion() {
        givenElderlyAndRiskSnapshotExist();
        ArgumentCaptor<InterventionPlan> planCaptor = ArgumentCaptor.forClass(InterventionPlan.class);

        service.registerCallOutcome(request(answeredCall()));

        verify(interventionPlanRepository).save(planCaptor.capture());
        InterventionPlan plan = planCaptor.getValue();
        assertThat(plan.getStatus()).isEqualTo(GuidanceStatus.APPROVED);
        assertThat(plan.getGuidanceJson()).contains("실내에 머무르며 수분을 섭취하세요.");
        assertThat(plan.getQuestionsJson()).contains("호흡 확인");
        assertThat(plan.getEvidenceChunkIdsJson()).contains("kma-guide-2024-03");
        assertThat(plan.getRiskSnapshot().getRegionCode()).isEqualTo("11");
    }

    @Test
    void completesTheContactJobAndKeepsTheExternalCallIdAsIdempotencyKey() {
        givenElderlyAndRiskSnapshotExist();
        ArgumentCaptor<ContactJob> jobCaptor = ArgumentCaptor.forClass(ContactJob.class);

        service.registerCallOutcome(request(answeredCall()));

        verify(contactJobRepository).save(jobCaptor.capture());
        ContactJob job = jobCaptor.getValue();
        assertThat(job.getStatus()).isEqualTo(ContactStatus.COMPLETED);
        assertThat(job.getIdempotencyKey()).isEqualTo("call-abc-123");
        assertThat(job.getAttemptCount()).isEqualTo(1);
        assertThat(job.getLastAttemptAt()).isEqualTo(endedAt);
    }

    @Test
    void storesAnUnansweredCallAsUnknownObservationWithoutRequiringSummaryFields() {
        givenElderlyAndRiskSnapshotExist();
        ArgumentCaptor<ContactJob> jobCaptor = ArgumentCaptor.forClass(ContactJob.class);

        CallOutcomeResponse response = service.registerCallOutcome(request(
                new CallOutcomeRequest.Call(false, null, null, null, null, null, null, null, endedAt)));

        assertThat(response.contactStatus()).isEqualTo(ContactStatus.UNCONFIRMED);
        assertThat(response.shelterIntent()).isEqualTo(TriState.UNKNOWN);
        assertThat(response.canMoveAlone()).isEqualTo(TriState.UNKNOWN);
        assertThat(response.helpNeeded()).isEqualTo(TriState.UNKNOWN);
        assertThat(response.symptomMentioned()).isEqualTo(TriState.UNKNOWN);
        assertThat(response.confidence()).isEqualByComparingTo(BigDecimal.ZERO);

        verify(contactJobRepository).save(jobCaptor.capture());
        assertThat(jobCaptor.getValue().getStatus()).isEqualTo(ContactStatus.UNCONFIRMED);
    }

    @Test
    void rejectsAnAnsweredCallMissingTheStructuredSummaryFields() {
        givenElderlyAndRiskSnapshotExist();

        assertThatThrownBy(() -> service.registerCallOutcome(request(
                new CallOutcomeRequest.Call(true, "요약", TriState.YES, TriState.NO, null, TriState.YES,
                        new BigDecimal("0.91"), null, endedAt))))
                .isInstanceOfSatisfying(BusinessException.class,
                        exception -> assertThat(exception.errorCode()).isEqualTo(ErrorCode.VALIDATION_ERROR));
        verify(callObservationRepository, never()).save(any());
    }

    @Test
    void rejectsAnAnsweredCallWhoseConfidenceIsOutsideZeroToOne() {
        givenElderlyAndRiskSnapshotExist();

        assertThatThrownBy(() -> service.registerCallOutcome(request(
                new CallOutcomeRequest.Call(true, "요약", TriState.YES, TriState.NO, TriState.YES, TriState.YES,
                        new BigDecimal("1.4"), null, endedAt))))
                .isInstanceOfSatisfying(BusinessException.class,
                        exception -> assertThat(exception.errorCode()).isEqualTo(ErrorCode.VALIDATION_ERROR));
    }

    @Test
    void rejectsAResubmissionOfTheSameExternalCallId() {
        givenElderlyAndRiskSnapshotExist();
        when(contactJobRepository.existsByIdempotencyKey("call-abc-123")).thenReturn(true);

        assertThatThrownBy(() -> service.registerCallOutcome(request(answeredCall())))
                .isInstanceOfSatisfying(BusinessException.class,
                        exception -> assertThat(exception.errorCode()).isEqualTo(ErrorCode.CONFLICT));
        verify(interventionPlanRepository, never()).save(any());
    }

    @Test
    void rejectsAnOutcomeForAnElderlyThatDoesNotExist() {
        when(elderlyProfileRepository.findById(99L)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.registerCallOutcome(new CallOutcomeRequest(99L, "call-x",
                plan(), answeredCall())))
                .isInstanceOfSatisfying(BusinessException.class,
                        exception -> assertThat(exception.errorCode()).isEqualTo(ErrorCode.RESOURCE_NOT_FOUND));
    }

    @Test
    void rejectsAnOutcomeWhenTheRegionHasNoRiskSnapshot() {
        when(elderlyProfileRepository.findById(1L)).thenReturn(Optional.of(elderly()));
        when(riskSnapshotRepository.findTopByRegionCodeOrderByGeneratedAtDesc("11")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.registerCallOutcome(request(answeredCall())))
                .isInstanceOfSatisfying(BusinessException.class,
                        exception -> assertThat(exception.errorCode()).isEqualTo(ErrorCode.RESOURCE_NOT_FOUND));
    }

    private void givenElderlyAndRiskSnapshotExist() {
        when(elderlyProfileRepository.findById(1L)).thenReturn(Optional.of(elderly()));
        when(riskSnapshotRepository.findTopByRegionCodeOrderByGeneratedAtDesc("11"))
                .thenReturn(Optional.of(riskSnapshot()));
        when(interventionPlanRepository.save(any(InterventionPlan.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));
        when(contactJobRepository.save(any(ContactJob.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));
        when(callObservationRepository.save(any(CallObservation.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));
    }

    private CallOutcomeRequest request(CallOutcomeRequest.Call call) {
        return new CallOutcomeRequest(1L, "call-abc-123", plan(), call);
    }

    private CallOutcomeRequest.Plan plan() {
        return new CallOutcomeRequest.Plan("실내에 머무르며 수분을 섭취하세요.", "종로구민센터 쉼터로 이동을 권장합니다.",
                List.of("호흡 확인", "실내 온도 확인"), List.of("kma-guide-2024-03"));
    }

    private CallOutcomeRequest.Call answeredCall() {
        return new CallOutcomeRequest.Call(true, "어지러움을 호소해 쉼터 이동 지원이 필요합니다.",
                TriState.YES, TriState.NO, TriState.YES, TriState.YES, new BigDecimal("0.91"),
                "recording/2026/08/19/1", endedAt);
    }

    private ElderlyProfile elderly() {
        return ElderlyProfile.builder().displayName("김안심").phone("010").address("서울시 종로구 1-1")
                .latitude(new BigDecimal("37.5730000")).longitude(new BigDecimal("126.9794000"))
                .regionCode("11110").consentStatus(ConsentStatus.CONSENTED).build();
    }

    private RiskSnapshot riskSnapshot() {
        return RiskSnapshot.builder().regionCode("11").riskScore(new BigDecimal("0.8000"))
                .riskLevel(RiskLevel.HIGH).targetStartAt(endedAt).targetEndAt(endedAt.plusSeconds(3600))
                .modelVersion("heatwave-v1").generatedAt(endedAt).build();
    }
}
