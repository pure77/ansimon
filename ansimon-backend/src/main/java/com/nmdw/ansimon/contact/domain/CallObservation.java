package com.nmdw.ansimon.contact.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.OneToOne;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.Instant;

@Entity
@Table(
        name = "call_observation",
        uniqueConstraints = {
                @UniqueConstraint(name = "uk_observation_contact_job", columnNames = "contact_job_id")
        }
)
@Getter
@EqualsAndHashCode(of = "id")
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor(access = AccessLevel.PRIVATE)
@Builder
public class CallObservation {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @OneToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "contact_job_id", nullable = false, unique = true)
    private ContactJob contactJob;

    @Enumerated(EnumType.STRING)
    @Column(name = "contact_status", nullable = false, length = 40)
    private ContactStatus contactStatus;

    @Enumerated(EnumType.STRING)
    @Column(name = "shelter_intent", nullable = false, length = 20)
    private TriState shelterIntent;

    @Enumerated(EnumType.STRING)
    @Column(name = "can_move_alone", nullable = false, length = 20)
    private TriState canMoveAlone;

    @Enumerated(EnumType.STRING)
    @Column(name = "help_needed", nullable = false, length = 20)
    private TriState helpNeeded;

    @Enumerated(EnumType.STRING)
    @Column(name = "symptom_mentioned", nullable = false, length = 20)
    private TriState symptomMentioned;

    @Column(name = "summary", nullable = false, length = 1000)
    private String summary;

    @Column(name = "transcript_ref", length = 500)
    private String transcriptRef;

    @Column(name = "confidence", nullable = false, precision = 5, scale = 4)
    private BigDecimal confidence;

    @Column(name = "ended_at", nullable = false)
    private Instant endedAt;

    /**
     * 담당자가 확인한 내용으로 요약과 판정 항목을 교정합니다.
     * 후속 지원 업무는 이 판정값으로 결정되므로, LLM이 잘못 판단한 항목을 사람이 바로잡을 수 있어야 합니다.
     */
    public void correct(String summary, TriState shelterIntent, TriState canMoveAlone,
                        TriState helpNeeded, TriState symptomMentioned) {
        this.summary = summary;
        this.shelterIntent = shelterIntent;
        this.canMoveAlone = canMoveAlone;
        this.helpNeeded = helpNeeded;
        this.symptomMentioned = symptomMentioned;
    }
}
