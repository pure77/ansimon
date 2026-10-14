package com.nmdw.ansimon.contact.infra;

import com.nmdw.ansimon.contact.domain.CallObservation;
import com.nmdw.ansimon.contact.domain.ContactJob;
import com.nmdw.ansimon.contact.domain.ContactStatus;
import com.nmdw.ansimon.contact.domain.TriState;
import com.nmdw.ansimon.elderly.domain.ConsentStatus;
import com.nmdw.ansimon.elderly.domain.ElderlyProfile;
import com.nmdw.ansimon.elderly.infra.ElderlyProfileRepository;
import com.nmdw.ansimon.global.config.JpaAuditingConfig;
import com.nmdw.ansimon.guidance.domain.GuidanceStatus;
import com.nmdw.ansimon.guidance.domain.InterventionPlan;
import com.nmdw.ansimon.guidance.infra.InterventionPlanRepository;
import com.nmdw.ansimon.risk.domain.RiskLevel;
import com.nmdw.ansimon.risk.domain.RiskSnapshot;
import com.nmdw.ansimon.risk.infra.RiskSnapshotRepository;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.boot.jdbc.test.autoconfigure.AutoConfigureTestDatabase;
import org.springframework.context.annotation.Import;
import org.springframework.dao.DataIntegrityViolationException;

import java.math.BigDecimal;
import java.time.Instant;
import java.time.temporal.ChronoUnit;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@DataJpaTest
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Import(JpaAuditingConfig.class)
class CallObservationRepositoryTest {

    @Autowired
    private CallObservationRepository callObservationRepository;

    @Autowired
    private ContactJobRepository contactJobRepository;

    @Autowired
    private ElderlyProfileRepository elderlyProfileRepository;

    @Autowired
    private RiskSnapshotRepository riskSnapshotRepository;

    @Autowired
    private InterventionPlanRepository interventionPlanRepository;

    private ContactJob persistContactJob(String idempotencyKey) {
        ElderlyProfile elderly = elderlyProfileRepository.saveAndFlush(ElderlyProfile.builder()
                .displayName("김안심")
                .phone("hashed-phone-value")
                .address("서울시 종로구 1-1")
                .latitude(new BigDecimal("37.5730000"))
                .longitude(new BigDecimal("126.9794000"))
                .regionCode("11110")
                .consentStatus(ConsentStatus.CONSENTED)
                .build());

        Instant now = Instant.now().truncatedTo(ChronoUnit.MILLIS);
        RiskSnapshot riskSnapshot = riskSnapshotRepository.saveAndFlush(RiskSnapshot.builder()
                .regionCode("11110")
                .riskScore(new BigDecimal("0.8200"))
                .riskLevel(RiskLevel.HIGH)
                .targetStartAt(now)
                .targetEndAt(now.plusSeconds(3600))
                .modelVersion("heatwave-v1")
                .generatedAt(now)
                .build());

        InterventionPlan plan = interventionPlanRepository.saveAndFlush(InterventionPlan.builder()
                .elderly(elderly)
                .riskSnapshot(riskSnapshot)
                .status(GuidanceStatus.APPROVED)
                .guidanceJson("{\"summary\":\"실내에 머무르세요\"}")
                .questionsJson("[\"이동이 가능하신가요?\"]")
                .evidenceChunkIdsJson("[\"chunk-1\"]")
                .build());

        return contactJobRepository.saveAndFlush(ContactJob.builder()
                .elderly(elderly)
                .interventionPlan(plan)
                .status(ContactStatus.ANSWERED)
                .attemptCount(1)
                .scheduledAt(now)
                .idempotencyKey(idempotencyKey)
                .build());
    }

    @Test
    void savesAndReloadsCallObservationLinkedToContactJob() {
        ContactJob contactJob = persistContactJob("call-observation-key-1");

        CallObservation observation = CallObservation.builder()
                .contactJob(contactJob)
                .contactStatus(ContactStatus.ANSWERED)
                .shelterIntent(TriState.YES)
                .canMoveAlone(TriState.NO)
                .helpNeeded(TriState.YES)
                .symptomMentioned(TriState.UNKNOWN)
                .summary("어지러움을 호소하여 이동 지원이 필요함")
                .confidence(new BigDecimal("0.9100"))
                .endedAt(Instant.now().truncatedTo(ChronoUnit.MILLIS))
                .build();

        CallObservation saved = callObservationRepository.saveAndFlush(observation);

        CallObservation found = callObservationRepository.findById(saved.getId()).orElseThrow();
        assertThat(found.getContactJob().getId()).isEqualTo(contactJob.getId());
        assertThat(found.getHelpNeeded()).isEqualTo(TriState.YES);
        assertThat(found.getTranscriptRef()).isNull();
    }

    @Test
    void reportsWhetherAContactJobAlreadyHasAnObservation() {
        ContactJob contactJob = persistContactJob("call-observation-key-3");
        assertThat(callObservationRepository.existsByContactJobId(contactJob.getId())).isFalse();

        callObservationRepository.saveAndFlush(CallObservation.builder()
                .contactJob(contactJob)
                .contactStatus(ContactStatus.UNCONFIRMED)
                .shelterIntent(TriState.UNKNOWN)
                .canMoveAlone(TriState.UNKNOWN)
                .helpNeeded(TriState.UNKNOWN)
                .symptomMentioned(TriState.UNKNOWN)
                .summary("미응답으로 통화 내용이 없습니다.")
                .confidence(BigDecimal.ZERO)
                .endedAt(Instant.now().truncatedTo(ChronoUnit.MILLIS))
                .build());

        assertThat(callObservationRepository.existsByContactJobId(contactJob.getId())).isTrue();
    }

    @Test
    void rejectsSecondObservationForSameContactJob() {
        ContactJob contactJob = persistContactJob("call-observation-key-2");

        callObservationRepository.saveAndFlush(CallObservation.builder()
                .contactJob(contactJob)
                .contactStatus(ContactStatus.ANSWERED)
                .shelterIntent(TriState.NO)
                .canMoveAlone(TriState.YES)
                .helpNeeded(TriState.NO)
                .symptomMentioned(TriState.NO)
                .summary("특이사항 없음")
                .confidence(new BigDecimal("0.9500"))
                .endedAt(Instant.now().truncatedTo(ChronoUnit.MILLIS))
                .build());

        CallObservation duplicate = CallObservation.builder()
                .contactJob(contactJob)
                .contactStatus(ContactStatus.ANSWERED)
                .shelterIntent(TriState.NO)
                .canMoveAlone(TriState.YES)
                .helpNeeded(TriState.NO)
                .symptomMentioned(TriState.NO)
                .summary("중복 저장 시도")
                .confidence(new BigDecimal("0.9000"))
                .endedAt(Instant.now().truncatedTo(ChronoUnit.MILLIS))
                .build();

        assertThatThrownBy(() -> callObservationRepository.saveAndFlush(duplicate))
                .isInstanceOf(DataIntegrityViolationException.class);
    }
}
