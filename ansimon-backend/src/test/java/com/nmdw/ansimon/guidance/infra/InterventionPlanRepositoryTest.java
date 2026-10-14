package com.nmdw.ansimon.guidance.infra;

import com.nmdw.ansimon.elderly.domain.ConsentStatus;
import com.nmdw.ansimon.elderly.domain.ElderlyProfile;
import com.nmdw.ansimon.elderly.infra.ElderlyProfileRepository;
import com.nmdw.ansimon.global.config.JpaAuditingConfig;
import com.nmdw.ansimon.guidance.domain.GuidanceStatus;
import com.nmdw.ansimon.guidance.domain.InterventionPlan;
import com.nmdw.ansimon.risk.domain.RiskLevel;
import com.nmdw.ansimon.risk.domain.RiskSnapshot;
import com.nmdw.ansimon.risk.infra.RiskSnapshotRepository;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.boot.jdbc.test.autoconfigure.AutoConfigureTestDatabase;
import org.springframework.context.annotation.Import;

import java.math.BigDecimal;
import java.time.Instant;
import java.time.temporal.ChronoUnit;

import static org.assertj.core.api.Assertions.assertThat;

@DataJpaTest
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Import(JpaAuditingConfig.class)
class InterventionPlanRepositoryTest {

    @Autowired
    private InterventionPlanRepository interventionPlanRepository;

    @Autowired
    private ElderlyProfileRepository elderlyProfileRepository;

    @Autowired
    private RiskSnapshotRepository riskSnapshotRepository;

    @Test
    void savesAndReloadsInterventionPlanWithRequiredForeignKeysAndNullableShelter() {
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

        InterventionPlan plan = InterventionPlan.builder()
                .elderly(elderly)
                .riskSnapshot(riskSnapshot)
                .shelter(null)
                .status(GuidanceStatus.PENDING)
                .guidanceJson("{\"summary\":\"실내에 머무르세요\"}")
                .questionsJson("[\"이동이 가능하신가요?\"]")
                .evidenceChunkIdsJson("[\"chunk-1\"]")
                .build();

        InterventionPlan saved = interventionPlanRepository.saveAndFlush(plan);

        InterventionPlan found = interventionPlanRepository.findById(saved.getId()).orElseThrow();
        assertThat(found.getElderly().getId()).isEqualTo(elderly.getId());
        assertThat(found.getRiskSnapshot().getId()).isEqualTo(riskSnapshot.getId());
        assertThat(found.getShelter()).isNull();
        assertThat(found.getStatus()).isEqualTo(GuidanceStatus.PENDING);
        assertThat(found.getGuidanceJson()).contains("실내");
        assertThat(found.getCreatedAt()).isNotNull();
    }
}
