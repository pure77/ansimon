package com.nmdw.ansimon.contact.application;

import com.nmdw.ansimon.contact.domain.CallObservation;
import com.nmdw.ansimon.contact.domain.ContactStatus;
import com.nmdw.ansimon.contact.dto.CallObservationListResponse;
import com.nmdw.ansimon.contact.dto.CallObservationResponse;
import com.nmdw.ansimon.contact.dto.CallObservationUpdateRequest;
import com.nmdw.ansimon.contact.infra.CallObservationRepository;
import com.nmdw.ansimon.global.error.BusinessException;
import com.nmdw.ansimon.global.error.ErrorCode;
import com.nmdw.ansimon.global.response.PageResponse;
import com.nmdw.ansimon.guidance.domain.InterventionPlan;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;

/**
 * 저장된 통화 결과를 조회하고, 담당자가 교정하거나 삭제하는 유스케이스를 담당하는 애플리케이션 서비스입니다.
 * 후속 지원 업무 판단이 이 판정값에 의존하므로, LLM이 잘못 판단한 항목을 사람이 바로잡을 수 있게 합니다.
 */
@Service
@Transactional
public class CallObservationService {

    private static final ZoneId ASIA_SEOUL = ZoneId.of("Asia/Seoul");

    private final CallObservationRepository repository;
    private final ObjectMapper objectMapper;

    public CallObservationService(CallObservationRepository repository, ObjectMapper objectMapper) {
        this.repository = repository;
        this.objectMapper = objectMapper;
    }

    /**
     * date를 주면 그 날짜(Asia/Seoul)에 끝난 통화만 봅니다. 대시보드는 오늘을, 상세화면은 날짜 없이 전체를 봅니다.
     */
    @Transactional(readOnly = true)
    public PageResponse<CallObservationListResponse> search(Long elderlyId, ContactStatus status,
                                                            LocalDate date, Pageable pageable) {
        Instant from = date == null ? null : date.atStartOfDay(ASIA_SEOUL).toInstant();
        Instant to = date == null ? null : date.plusDays(1).atStartOfDay(ASIA_SEOUL).toInstant();
        return PageResponse.from(repository.search(elderlyId, status, from, to, pageable).map(this::toListResponse));
    }

    public CallObservationResponse update(Long id, CallObservationUpdateRequest request) {
        CallObservation observation = findById(id);
        observation.correct(
                StringUtils.hasText(request.summary()) ? request.summary() : observation.getSummary(),
                request.shelterIntent() != null ? request.shelterIntent() : observation.getShelterIntent(),
                request.canMoveAlone() != null ? request.canMoveAlone() : observation.getCanMoveAlone(),
                request.helpNeeded() != null ? request.helpNeeded() : observation.getHelpNeeded(),
                request.symptomMentioned() != null ? request.symptomMentioned() : observation.getSymptomMentioned());
        return CallObservationResponse.from(observation);
    }

    public void delete(Long id) {
        repository.delete(findById(id));
    }

    private CallObservation findById(Long id) {
        return repository.findById(id)
                .orElseThrow(() -> new BusinessException(ErrorCode.RESOURCE_NOT_FOUND));
    }

    private CallObservationListResponse toListResponse(CallObservation observation) {
        InterventionPlan plan = observation.getContactJob().getInterventionPlan();
        JsonNode guidance = readGuidance(plan.getGuidanceJson());
        return new CallObservationListResponse(
                observation.getId(),
                observation.getContactJob().getId(),
                observation.getContactJob().getElderly().getId(),
                observation.getContactJob().getElderly().getDisplayName(),
                observation.getContactStatus(),
                observation.getShelterIntent(),
                observation.getCanMoveAlone(),
                observation.getHelpNeeded(),
                observation.getSymptomMentioned(),
                observation.getSummary(),
                observation.getConfidence(),
                observation.getEndedAt(),
                text(guidance, "actionGuidance"),
                text(guidance, "shelterRecommendationText"));
    }

    /**
     * 오래된 데이터 한 건의 형식이 어긋나더라도 목록 전체가 실패하면 안 되므로, 파싱 실패는 빈 값으로 넘어갑니다.
     */
    private JsonNode readGuidance(String guidanceJson) {
        if (!StringUtils.hasText(guidanceJson)) {
            return null;
        }
        try {
            return objectMapper.readTree(guidanceJson);
        } catch (RuntimeException exception) {
            return null;
        }
    }

    private String text(JsonNode node, String field) {
        if (node == null || !node.hasNonNull(field)) {
            return null;
        }
        return node.get(field).asString();
    }
}
