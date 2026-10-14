package com.nmdw.ansimon.guidance.dto;

/**
 * care-run 트리거 확인값입니다. 실제 결과 저장은 contact 결과 콜백이 전담합니다.
 */
public record CareRunTriggerResponse(Long elderlyId, String externalCallId, Boolean answered) {
}
