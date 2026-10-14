package com.nmdw.ansimon.support.domain;

import com.nmdw.ansimon.contact.domain.ContactJob;
import com.nmdw.ansimon.elderly.domain.ElderlyProfile;
import com.nmdw.ansimon.global.persistence.BaseTimeEntity;
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
import jakarta.persistence.UniqueConstraint;
import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.time.Instant;

@Entity
@Table(
        name = "support_task",
        uniqueConstraints = {
                @UniqueConstraint(name = "uk_support_task_deduplication_key", columnNames = "deduplication_key")
        },
        indexes = {
                @Index(name = "idx_support_status_priority_due", columnList = "status, priority, due_at"),
                @Index(name = "idx_support_assignee_status", columnList = "assignee_id, status"),
                @Index(name = "idx_support_contact_job", columnList = "contact_job_id")
        }
)
@Getter
@EqualsAndHashCode(of = "id", callSuper = false)
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor(access = AccessLevel.PRIVATE)
@Builder
public class SupportTask extends BaseTimeEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "elderly_id", nullable = false)
    private ElderlyProfile elderly;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "contact_job_id")
    private ContactJob contactJob;

    @Column(name = "assignee_id")
    private Long assigneeId;

    @Enumerated(EnumType.STRING)
    @Column(name = "task_type", nullable = false, length = 60)
    private SupportTaskType taskType;

    @Enumerated(EnumType.STRING)
    @Column(name = "priority", nullable = false, length = 30)
    private SupportPriority priority;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false, length = 30)
    private SupportStatus status;

    @Column(name = "reason", nullable = false, length = 500)
    private String reason;

    @Column(name = "due_at", nullable = false)
    private Instant dueAt;

    @Column(name = "assigned_at")
    private Instant assignedAt;

    @Column(name = "completed_at")
    private Instant completedAt;

    @Column(name = "completion_note", length = 1000)
    private String completionNote;

    @Column(name = "deduplication_key", nullable = false, length = 160)
    private String deduplicationKey;
}
