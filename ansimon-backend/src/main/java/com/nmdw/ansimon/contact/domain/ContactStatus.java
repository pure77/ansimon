package com.nmdw.ansimon.contact.domain;

/**
 * 전화 작업과 통화 결과의 상태를 표현합니다.
 * 전화는 복지사가 직접 걸기 때문에 발신 중·재시도 예약 같은 자동 발신 워커 전용 상태는 두지 않습니다.
 */
public enum ContactStatus {
    PENDING,
    READY_FOR_REVIEW,
    SCHEDULED,
    ANSWERED,
    UNCONFIRMED,
    FAILED,
    ANALYZED,
    ACTION_REQUIRED,
    COMPLETED
}
