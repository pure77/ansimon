package com.nmdw.ansimon.risk.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.math.BigDecimal;
import java.time.Instant;

@Entity
@Table(
        name = "risk_snapshot",
        indexes = {
                @Index(name = "idx_risk_region_target", columnList = "region_code, target_start_at, target_end_at")
        }
)
@Getter
@EqualsAndHashCode(of = "id")
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor(access = AccessLevel.PRIVATE)
@Builder
public class RiskSnapshot {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "region_code", nullable = false, length = 20)
    private String regionCode;

    @Column(name = "risk_score", nullable = false, precision = 5, scale = 4)
    private BigDecimal riskScore;

    @Enumerated(EnumType.STRING)
    @Column(name = "risk_level", nullable = false, length = 30)
    private RiskLevel riskLevel;

    @Column(name = "target_start_at", nullable = false)
    private Instant targetStartAt;

    @Column(name = "target_end_at", nullable = false)
    private Instant targetEndAt;

    @Column(name = "peak_start_at")
    private Instant peakStartAt;

    @Column(name = "peak_end_at")
    private Instant peakEndAt;

    @Column(name = "model_version", nullable = false, length = 100)
    private String modelVersion;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "top_factors_json")
    private String topFactorsJson;

    @Column(name = "generated_at", nullable = false)
    private Instant generatedAt;
}
