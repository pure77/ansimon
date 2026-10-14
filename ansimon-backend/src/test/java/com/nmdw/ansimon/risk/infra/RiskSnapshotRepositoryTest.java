package com.nmdw.ansimon.risk.infra;

import com.nmdw.ansimon.risk.domain.RiskLevel;
import com.nmdw.ansimon.risk.domain.RiskSnapshot;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.boot.jdbc.test.autoconfigure.AutoConfigureTestDatabase;

import java.math.BigDecimal;
import java.time.Instant;
import java.time.temporal.ChronoUnit;

import static org.assertj.core.api.Assertions.assertThat;

@DataJpaTest
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
class RiskSnapshotRepositoryTest {

    @Autowired
    private RiskSnapshotRepository riskSnapshotRepository;

    @Test
    void savesAndReloadsRiskSnapshotWithJsonAndPeakWindow() {
        Instant now = Instant.now().truncatedTo(ChronoUnit.MILLIS);
        RiskSnapshot snapshot = RiskSnapshot.builder()
                .regionCode("11110")
                .riskScore(new BigDecimal("0.8200"))
                .riskLevel(RiskLevel.HIGH)
                .targetStartAt(now)
                .targetEndAt(now.plusSeconds(3600))
                .peakStartAt(now.plusSeconds(1800))
                .peakEndAt(now.plusSeconds(2400))
                .modelVersion("heatwave-v1")
                .topFactorsJson("[{\"factor\":\"temperature\",\"weight\":0.6}]")
                .generatedAt(now)
                .build();

        RiskSnapshot saved = riskSnapshotRepository.saveAndFlush(snapshot);

        RiskSnapshot found = riskSnapshotRepository.findById(saved.getId()).orElseThrow();
        assertThat(found.getRiskLevel()).isEqualTo(RiskLevel.HIGH);
        assertThat(found.getTopFactorsJson()).contains("temperature");
        assertThat(found.getPeakStartAt()).isEqualTo(now.plusSeconds(1800));
    }

    @Test
    void savesRiskSnapshotWithNullTopFactorsJsonAndNullPeakWindow() {
        Instant now = Instant.now().truncatedTo(ChronoUnit.MILLIS);
        RiskSnapshot snapshot = RiskSnapshot.builder()
                .regionCode("11110")
                .riskScore(new BigDecimal("0.1500"))
                .riskLevel(RiskLevel.LOW)
                .targetStartAt(now)
                .targetEndAt(now.plusSeconds(3600))
                .modelVersion("heatwave-v1")
                .generatedAt(now)
                .build();

        RiskSnapshot saved = riskSnapshotRepository.saveAndFlush(snapshot);

        RiskSnapshot found = riskSnapshotRepository.findById(saved.getId()).orElseThrow();
        assertThat(found.getTopFactorsJson()).isNull();
        assertThat(found.getPeakStartAt()).isNull();
        assertThat(found.getPeakEndAt()).isNull();
    }

    @Test
    void findsTheMostRecentSnapshotForARegion() {
        Instant now = Instant.now();
        riskSnapshotRepository.saveAndFlush(snapshot("11110", now.minus(2, ChronoUnit.HOURS)));
        RiskSnapshot latest = riskSnapshotRepository.saveAndFlush(snapshot("11110", now));
        riskSnapshotRepository.saveAndFlush(snapshot("11440", now));

        RiskSnapshot found = riskSnapshotRepository.findTopByRegionCodeOrderByGeneratedAtDesc("11110").orElseThrow();

        assertThat(found.getId()).isEqualTo(latest.getId());
    }

    @Test
    void returnsEmptyWhenNoSnapshotExistsForTheRegion() {
        assertThat(riskSnapshotRepository.findTopByRegionCodeOrderByGeneratedAtDesc("99999")).isEmpty();
    }

    private RiskSnapshot snapshot(String regionCode, Instant generatedAt) {
        return RiskSnapshot.builder()
                .regionCode(regionCode)
                .riskScore(new BigDecimal("0.8000"))
                .riskLevel(RiskLevel.HIGH)
                .targetStartAt(generatedAt)
                .targetEndAt(generatedAt.plus(3, ChronoUnit.HOURS))
                .modelVersion("test-model-v1")
                .generatedAt(generatedAt)
                .build();
    }
}
