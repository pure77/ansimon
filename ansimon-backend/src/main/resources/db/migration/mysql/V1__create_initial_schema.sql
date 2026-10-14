CREATE TABLE elderly_profile (
    id BIGINT NOT NULL AUTO_INCREMENT,
    display_name VARCHAR(100) NOT NULL,
    phone VARCHAR(128) NOT NULL,
    address VARCHAR(255) NOT NULL,
    latitude DECIMAL(10, 7) NOT NULL,
    longitude DECIMAL(10, 7) NOT NULL,
    region_code VARCHAR(20) NOT NULL,
    consent_status VARCHAR(30) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    INDEX idx_elderly_region_code (region_code),
    INDEX idx_elderly_phone_hash (phone),
    CONSTRAINT chk_elderly_latitude CHECK (latitude BETWEEN -90 AND 90),
    CONSTRAINT chk_elderly_longitude CHECK (longitude BETWEEN -180 AND 180)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE risk_snapshot (
    id BIGINT NOT NULL AUTO_INCREMENT,
    region_code VARCHAR(20) NOT NULL,
    risk_score DECIMAL(5, 4) NOT NULL,
    risk_level VARCHAR(30) NOT NULL,
    target_start_at DATETIME(6) NOT NULL,
    target_end_at DATETIME(6) NOT NULL,
    peak_start_at DATETIME(6) NULL,
    peak_end_at DATETIME(6) NULL,
    model_version VARCHAR(100) NOT NULL,
    top_factors_json JSON NULL,
    generated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    INDEX idx_risk_region_target (region_code, target_start_at, target_end_at),
    CONSTRAINT chk_risk_score_range CHECK (risk_score BETWEEN 0 AND 1),
    CONSTRAINT chk_risk_target_window CHECK (target_start_at < target_end_at),
    CONSTRAINT chk_risk_peak_window CHECK (
        (peak_start_at IS NULL AND peak_end_at IS NULL)
        OR (
            peak_start_at IS NOT NULL
            AND peak_end_at IS NOT NULL
            AND peak_start_at < peak_end_at
        )
    )
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE shelter (
    id BIGINT NOT NULL AUTO_INCREMENT,
    source_id VARCHAR(100) NOT NULL,
    name VARCHAR(150) NOT NULL,
    address VARCHAR(255) NOT NULL,
    latitude DECIMAL(10, 7) NOT NULL,
    longitude DECIMAL(10, 7) NOT NULL,
    open_status VARCHAR(30) NOT NULL,
    source_version VARCHAR(100) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_shelter_source_id (source_id),
    CONSTRAINT chk_shelter_latitude CHECK (latitude BETWEEN -90 AND 90),
    CONSTRAINT chk_shelter_longitude CHECK (longitude BETWEEN -180 AND 180)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE intervention_plan (
    id BIGINT NOT NULL AUTO_INCREMENT,
    elderly_id BIGINT NOT NULL,
    risk_snapshot_id BIGINT NOT NULL,
    shelter_id BIGINT NULL,
    status VARCHAR(40) NOT NULL,
    guidance_json JSON NOT NULL,
    questions_json JSON NOT NULL,
    evidence_chunk_ids_json JSON NOT NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    INDEX idx_plan_elderly_risk (elderly_id, risk_snapshot_id),
    INDEX idx_plan_risk_snapshot (risk_snapshot_id),
    INDEX idx_plan_shelter (shelter_id),
    CONSTRAINT fk_intervention_plan_elderly
        FOREIGN KEY (elderly_id) REFERENCES elderly_profile(id),
    CONSTRAINT fk_intervention_plan_risk_snapshot
        FOREIGN KEY (risk_snapshot_id) REFERENCES risk_snapshot(id),
    CONSTRAINT fk_intervention_plan_shelter
        FOREIGN KEY (shelter_id) REFERENCES shelter(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE contact_job (
    id BIGINT NOT NULL AUTO_INCREMENT,
    elderly_id BIGINT NOT NULL,
    intervention_plan_id BIGINT NOT NULL,
    status VARCHAR(40) NOT NULL,
    attempt_count INT NOT NULL,
    scheduled_at DATETIME(6) NOT NULL,
    approved_by VARCHAR(100) NULL,
    approved_at DATETIME(6) NULL,
    last_attempt_at DATETIME(6) NULL,
    next_retry_at DATETIME(6) NULL,
    provider_call_id VARCHAR(160) NULL,
    failure_reason VARCHAR(500) NULL,
    lock_token VARCHAR(64) NULL,
    locked_until DATETIME(6) NULL,
    idempotency_key VARCHAR(160) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_contact_idempotency_key (idempotency_key),
    UNIQUE KEY uk_contact_provider_call_id (provider_call_id),
    INDEX idx_contact_status_scheduled (status, scheduled_at),
    INDEX idx_contact_status_next_retry (status, next_retry_at),
    INDEX idx_contact_lock_expiry (locked_until),
    INDEX idx_contact_intervention_plan (intervention_plan_id),
    CONSTRAINT chk_contact_attempt_count CHECK (attempt_count >= 0),
    CONSTRAINT fk_contact_job_elderly
        FOREIGN KEY (elderly_id) REFERENCES elderly_profile(id),
    CONSTRAINT fk_contact_job_intervention_plan
        FOREIGN KEY (intervention_plan_id) REFERENCES intervention_plan(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE call_observation (
    id BIGINT NOT NULL AUTO_INCREMENT,
    contact_job_id BIGINT NOT NULL,
    contact_status VARCHAR(40) NOT NULL,
    shelter_intent VARCHAR(20) NOT NULL,
    can_move_alone VARCHAR(20) NOT NULL,
    help_needed VARCHAR(20) NOT NULL,
    symptom_mentioned VARCHAR(20) NOT NULL,
    summary VARCHAR(1000) NOT NULL,
    transcript_ref VARCHAR(500) NULL,
    confidence DECIMAL(5, 4) NOT NULL,
    ended_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_observation_contact_job (contact_job_id),
    CONSTRAINT chk_observation_confidence CHECK (confidence BETWEEN 0 AND 1),
    CONSTRAINT fk_call_observation_contact_job
        FOREIGN KEY (contact_job_id) REFERENCES contact_job(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE support_task (
    id BIGINT NOT NULL AUTO_INCREMENT,
    elderly_id BIGINT NOT NULL,
    contact_job_id BIGINT NULL,
    assignee_id BIGINT NULL,
    task_type VARCHAR(60) NOT NULL,
    priority VARCHAR(30) NOT NULL,
    status VARCHAR(30) NOT NULL,
    reason VARCHAR(500) NOT NULL,
    due_at DATETIME(6) NOT NULL,
    assigned_at DATETIME(6) NULL,
    completed_at DATETIME(6) NULL,
    completion_note VARCHAR(1000) NULL,
    deduplication_key VARCHAR(160) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_support_task_deduplication_key (deduplication_key),
    INDEX idx_support_status_priority_due (status, priority, due_at),
    INDEX idx_support_assignee_status (assignee_id, status),
    INDEX idx_support_contact_job (contact_job_id),
    CONSTRAINT fk_support_task_elderly
        FOREIGN KEY (elderly_id) REFERENCES elderly_profile(id),
    CONSTRAINT fk_support_task_contact_job
        FOREIGN KEY (contact_job_id) REFERENCES contact_job(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
