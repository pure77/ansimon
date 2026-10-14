package com.nmdw.ansimon.guidance.domain;

import com.nmdw.ansimon.elderly.domain.ElderlyProfile;
import com.nmdw.ansimon.global.persistence.BaseTimeEntity;
import com.nmdw.ansimon.risk.domain.RiskSnapshot;
import com.nmdw.ansimon.shelter.domain.Shelter;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

@Entity
@Table(
        name = "intervention_plan",
        indexes = {
                @Index(name = "idx_plan_elderly_risk", columnList = "elderly_id, risk_snapshot_id"),
                @Index(name = "idx_plan_risk_snapshot", columnList = "risk_snapshot_id"),
                @Index(name = "idx_plan_shelter", columnList = "shelter_id")
        }
)
@Getter
@EqualsAndHashCode(of = "id", callSuper = false)
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor(access = AccessLevel.PRIVATE)
@Builder
public class InterventionPlan extends BaseTimeEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "elderly_id", nullable = false)
    private ElderlyProfile elderly;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "risk_snapshot_id", nullable = false)
    private RiskSnapshot riskSnapshot;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "shelter_id")
    private Shelter shelter;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 40)
    private GuidanceStatus status;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "guidance_json", nullable = false)
    private String guidanceJson;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "questions_json", nullable = false)
    private String questionsJson;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "evidence_chunk_ids_json", nullable = false)
    private String evidenceChunkIdsJson;
}
