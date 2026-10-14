package com.nmdw.ansimon.elderly.infra;

import com.nmdw.ansimon.elderly.domain.ConsentStatus;
import com.nmdw.ansimon.elderly.domain.ElderlyProfile;
import com.nmdw.ansimon.global.config.JpaAuditingConfig;
import com.nmdw.ansimon.guidance.domain.GuidanceStatus;
import com.nmdw.ansimon.guidance.domain.InterventionPlan;
import com.nmdw.ansimon.guidance.infra.InterventionPlanRepository;
import com.nmdw.ansimon.risk.domain.RiskLevel;
import com.nmdw.ansimon.risk.domain.RiskSnapshot;
import com.nmdw.ansimon.risk.infra.RiskSnapshotRepository;
import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
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
class ElderlyProfileRepositoryTest {

    @Autowired
    private ElderlyProfileRepository elderlyProfileRepository;

    @Autowired
    private RiskSnapshotRepository riskSnapshotRepository;

    @Autowired
    private InterventionPlanRepository interventionPlanRepository;

    @PersistenceContext
    private EntityManager entityManager;

    @Test
    void deletesAProfileThatHasNoInterventionHistory() {
        ElderlyProfile saved = elderlyProfileRepository.saveAndFlush(profile());

        elderlyProfileRepository.delete(saved);
        elderlyProfileRepository.flush();

        assertThat(elderlyProfileRepository.findById(saved.getId())).isEmpty();
    }

    @Test
    void refusesToDeleteAProfileReferencedByAnInterventionPlan() {
        ElderlyProfile saved = elderlyProfileRepository.saveAndFlush(profile());
        Instant now = Instant.now().truncatedTo(ChronoUnit.MILLIS);
        RiskSnapshot riskSnapshot = riskSnapshotRepository.saveAndFlush(RiskSnapshot.builder()
                .regionCode("11110").riskScore(new BigDecimal("0.8200")).riskLevel(RiskLevel.HIGH)
                .targetStartAt(now).targetEndAt(now.plusSeconds(3600))
                .modelVersion("heatwave-v1").generatedAt(now).build());
        interventionPlanRepository.saveAndFlush(InterventionPlan.builder()
                .elderly(saved).riskSnapshot(riskSnapshot).status(GuidanceStatus.APPROVED)
                .guidanceJson("{\"actionGuidance\":\"실내에 머무르세요\"}")
                .questionsJson("[\"호흡 확인\"]").evidenceChunkIdsJson("[\"chunk-1\"]").build());
        // 삭제 서비스는 안내계획을 함께 로딩하지 않으므로, 실제 흐름처럼 영속성 컨텍스트를 비워 DELETE가 DB까지 가게 한다.
        entityManager.clear();

        elderlyProfileRepository.delete(elderlyProfileRepository.findById(saved.getId()).orElseThrow());

        assertThatThrownBy(() -> elderlyProfileRepository.flush())
                .isInstanceOf(DataIntegrityViolationException.class);
    }

    private ElderlyProfile profile() {
        return ElderlyProfile.builder()
                .displayName("김안심")
                .phone("hashed-phone-value")
                .address("서울시 종로구 1-1")
                .latitude(new BigDecimal("37.5730000"))
                .longitude(new BigDecimal("126.9794000"))
                .regionCode("11110")
                .consentStatus(ConsentStatus.CONSENTED)
                .build();
    }

    @Test
    void savesAndReloadsElderlyProfileWithAuditedTimestamps() {
        ElderlyProfile profile = ElderlyProfile.builder()
                .displayName("김안심")
                .phone("hashed-phone-value")
                .address("서울시 종로구 1-1")
                .latitude(new BigDecimal("37.5730000"))
                .longitude(new BigDecimal("126.9794000"))
                .regionCode("11110")
                .consentStatus(ConsentStatus.CONSENTED)
                .build();

        ElderlyProfile saved = elderlyProfileRepository.saveAndFlush(profile);

        ElderlyProfile found = elderlyProfileRepository.findById(saved.getId()).orElseThrow();
        assertThat(found.getDisplayName()).isEqualTo("김안심");
        assertThat(found.getConsentStatus()).isEqualTo(ConsentStatus.CONSENTED);
        assertThat(found.getCreatedAt()).isNotNull();
        assertThat(found.getUpdatedAt()).isNotNull();
    }
}
