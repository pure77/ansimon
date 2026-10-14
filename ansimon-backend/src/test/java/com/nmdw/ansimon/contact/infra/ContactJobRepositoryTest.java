package com.nmdw.ansimon.contact.infra;

import com.nmdw.ansimon.contact.domain.ContactJob;
import com.nmdw.ansimon.contact.domain.ContactStatus;
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
class ContactJobRepositoryTest {

    @Autowired
    private ContactJobRepository contactJobRepository;

    @Autowired
    private ElderlyProfileRepository elderlyProfileRepository;

    @Autowired
    private RiskSnapshotRepository riskSnapshotRepository;

    @Autowired
    private InterventionPlanRepository interventionPlanRepository;

    private InterventionPlan persistInterventionPlan() {
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

        return interventionPlanRepository.saveAndFlush(InterventionPlan.builder()
                .elderly(elderly)
                .riskSnapshot(riskSnapshot)
                .status(GuidanceStatus.APPROVED)
                .guidanceJson("{\"summary\":\"실내에 머무르세요\"}")
                .questionsJson("[\"이동이 가능하신가요?\"]")
                .evidenceChunkIdsJson("[\"chunk-1\"]")
                .build());
    }

    @Test
    void savesAndReloadsContactJobWithForeignKeysAndDefaults() {
        InterventionPlan plan = persistInterventionPlan();
        Instant now = Instant.now().truncatedTo(ChronoUnit.MILLIS);

        ContactJob job = ContactJob.builder()
                .elderly(plan.getElderly())
                .interventionPlan(plan)
                .status(ContactStatus.SCHEDULED)
                .attemptCount(0)
                .scheduledAt(now.plusSeconds(600))
                .idempotencyKey("elderly-" + plan.getElderly().getId() + "-risk-" + plan.getRiskSnapshot().getId())
                .build();

        ContactJob saved = contactJobRepository.saveAndFlush(job);

        ContactJob found = contactJobRepository.findById(saved.getId()).orElseThrow();
        assertThat(found.getStatus()).isEqualTo(ContactStatus.SCHEDULED);
        assertThat(found.getAttemptCount()).isZero();
        assertThat(found.getInterventionPlan().getId()).isEqualTo(plan.getId());
        assertThat(found.getCreatedAt()).isNotNull();
    }

    @Test
    void rejectsDuplicateIdempotencyKey() {
        InterventionPlan plan = persistInterventionPlan();
        Instant now = Instant.now().truncatedTo(ChronoUnit.MILLIS);

        contactJobRepository.saveAndFlush(ContactJob.builder()
                .elderly(plan.getElderly())
                .interventionPlan(plan)
                .status(ContactStatus.SCHEDULED)
                .attemptCount(0)
                .scheduledAt(now)
                .idempotencyKey("dup-key")
                .build());

        ContactJob duplicate = ContactJob.builder()
                .elderly(plan.getElderly())
                .interventionPlan(plan)
                .status(ContactStatus.SCHEDULED)
                .attemptCount(0)
                .scheduledAt(now)
                .idempotencyKey("dup-key")
                .build();

        assertThatThrownBy(() -> contactJobRepository.saveAndFlush(duplicate))
                .isInstanceOf(DataIntegrityViolationException.class);
    }
}
