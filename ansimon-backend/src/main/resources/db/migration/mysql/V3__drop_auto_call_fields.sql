-- 자동전화(발신 워커) 기능을 폐기하고 복지사 수동 전화 + 결과 제출 흐름으로 전환한다.
-- 전화사업자 연동 식별자, 재시도 예약, 워커 잠금 컬럼과 그 전용 인덱스는 더 이상 사용하지 않는다.
ALTER TABLE contact_job DROP INDEX idx_contact_status_next_retry;

ALTER TABLE contact_job DROP INDEX idx_contact_lock_expiry;

ALTER TABLE contact_job DROP INDEX uk_contact_provider_call_id;

ALTER TABLE contact_job DROP COLUMN provider_call_id;

ALTER TABLE contact_job DROP COLUMN next_retry_at;

ALTER TABLE contact_job DROP COLUMN lock_token;

ALTER TABLE contact_job DROP COLUMN locked_until;
