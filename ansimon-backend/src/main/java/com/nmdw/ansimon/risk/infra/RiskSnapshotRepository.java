package com.nmdw.ansimon.risk.infra;

import com.nmdw.ansimon.risk.domain.RiskSnapshot;
import org.springframework.data.jpa.repository.JpaRepository;

import java.time.Instant;
import java.util.Optional;

public interface RiskSnapshotRepository extends JpaRepository<RiskSnapshot, Long> {

    Optional<RiskSnapshot> findTopByRegionCodeOrderByGeneratedAtDesc(String regionCode);

    Optional<RiskSnapshot> findTopByRegionCodeAndGeneratedAtGreaterThanEqualOrderByGeneratedAtDesc(
            String regionCode, Instant from);
}
