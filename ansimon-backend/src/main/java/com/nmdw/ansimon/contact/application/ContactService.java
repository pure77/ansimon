package com.nmdw.ansimon.contact.application;

import com.nmdw.ansimon.contact.domain.CallObservation;
import com.nmdw.ansimon.contact.domain.ContactJob;
import com.nmdw.ansimon.contact.domain.ContactStatus;
import com.nmdw.ansimon.contact.domain.TriState;
import com.nmdw.ansimon.contact.dto.CallOutcomeRequest;
import com.nmdw.ansimon.contact.dto.CallOutcomeResponse;
import com.nmdw.ansimon.contact.infra.CallObservationRepository;
import com.nmdw.ansimon.contact.infra.ContactJobRepository;
import com.nmdw.ansimon.elderly.domain.ElderlyProfile;
import com.nmdw.ansimon.elderly.infra.ElderlyProfileRepository;
import com.nmdw.ansimon.global.error.BusinessException;
import com.nmdw.ansimon.global.error.ErrorCode;
import com.nmdw.ansimon.global.util.RegionCodes;
import com.nmdw.ansimon.guidance.domain.GuidanceStatus;
import com.nmdw.ansimon.guidance.domain.InterventionPlan;
import com.nmdw.ansimon.guidance.infra.InterventionPlanRepository;
import com.nmdw.ansimon.risk.domain.RiskSnapshot;
import com.nmdw.ansimon.risk.infra.RiskSnapshotRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;
import tools.jackson.core.JacksonException;
import tools.jackson.databind.ObjectMapper;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

/**
 * 외부 LLM/RAG 서버가 대응계획 생성과 전화를 마친 뒤 보내는 최종 결과를 받아
 * 안내계획, 전화 작업, 통화 결과를 한 트랜잭션으로 저장하는 애플리케이션 서비스입니다.
 * 발신과 재시도는 외부에서 이루어지므로 이 서비스는 예약이나 재시도를 관리하지 않습니다.
 */
@Service
@Transactional
public class ContactService {

    private static final String UNANSWERED_SUMMARY = "미응답으로 통화 내용이 없습니다.";
    private static final BigDecimal UNANSWERED_CONFIDENCE = new BigDecimal("0.0000");

    private final ElderlyProfileRepository elderlyProfileRepository;
    private final RiskSnapshotRepository riskSnapshotRepository;
    private final InterventionPlanRepository interventionPlanRepository;
    private final ContactJobRepository contactJobRepository;
    private final CallObservationRepository callObservationRepository;
    private final ObjectMapper objectMapper;

    public ContactService(ElderlyProfileRepository elderlyProfileRepository,
                          RiskSnapshotRepository riskSnapshotRepository,
                          InterventionPlanRepository interventionPlanRepository,
                          ContactJobRepository contactJobRepository,
                          CallObservationRepository callObservationRepository,
                          ObjectMapper objectMapper) {
        this.elderlyProfileRepository = elderlyProfileRepository;
        this.riskSnapshotRepository = riskSnapshotRepository;
        this.interventionPlanRepository = interventionPlanRepository;
        this.contactJobRepository = contactJobRepository;
        this.callObservationRepository = callObservationRepository;
        this.objectMapper = objectMapper;
    }

    public CallOutcomeResponse registerCallOutcome(CallOutcomeRequest request) {
        ElderlyProfile elderly = elderlyProfileRepository.findById(request.elderlyId())
                .orElseThrow(() -> new BusinessException(ErrorCode.RESOURCE_NOT_FOUND));
        RiskSnapshot riskSnapshot = riskSnapshotRepository
                .findTopByRegionCodeOrderByGeneratedAtDesc(RegionCodes.siDoCode(elderly.getRegionCode()))
                .orElseThrow(() -> new BusinessException(ErrorCode.RESOURCE_NOT_FOUND));
        if (contactJobRepository.existsByIdempotencyKey(request.externalCallId())) {
            throw new BusinessException(ErrorCode.CONFLICT);
        }

        boolean answered = Boolean.TRUE.equals(request.call().answered());
        if (answered) {
            requireStructuredSummary(request.call());
        }

        InterventionPlan plan = interventionPlanRepository.save(toPlan(elderly, riskSnapshot, request.plan()));
        ContactJob job = contactJobRepository.save(toContactJob(elderly, plan, request, answered));
        CallObservation observation = callObservationRepository.save(toObservation(job, request.call(), answered));
        return CallOutcomeResponse.of(plan, observation);
    }

    /**
     * 응답한 통화는 후속 지원 업무 판단에 쓰이므로 요약, 3상태 항목 네 개, 0~1 범위 신뢰도를 모두 갖춰야 합니다.
     * LLM 결과를 그대로 믿지 않고 저장 전에 구조를 검증합니다.
     */
    private void requireStructuredSummary(CallOutcomeRequest.Call call) {
        if (!StringUtils.hasText(call.summary())
                || call.shelterIntent() == null
                || call.canMoveAlone() == null
                || call.helpNeeded() == null
                || call.symptomMentioned() == null
                || !isProbability(call.confidence())) {
            throw new BusinessException(ErrorCode.VALIDATION_ERROR);
        }
    }

    private boolean isProbability(BigDecimal confidence) {
        return confidence != null
                && confidence.compareTo(BigDecimal.ZERO) >= 0
                && confidence.compareTo(BigDecimal.ONE) <= 0;
    }

    private InterventionPlan toPlan(ElderlyProfile elderly, RiskSnapshot riskSnapshot,
                                    CallOutcomeRequest.Plan plan) {
        return InterventionPlan.builder()
                .elderly(elderly)
                .riskSnapshot(riskSnapshot)
                .status(GuidanceStatus.APPROVED)
                .guidanceJson(writeJson(Map.of(
                        "actionGuidance", plan.actionGuidance(),
                        "shelterRecommendationText", plan.shelterRecommendationText())))
                .questionsJson(writeJson(plan.callQuestionOrder()))
                .evidenceChunkIdsJson(writeJson(
                        plan.evidenceDocumentIds() == null ? List.of() : plan.evidenceDocumentIds()))
                .build();
    }

    private ContactJob toContactJob(ElderlyProfile elderly, InterventionPlan plan,
                                    CallOutcomeRequest request, boolean answered) {
        return ContactJob.builder()
                .elderly(elderly)
                .interventionPlan(plan)
                .status(answered ? ContactStatus.COMPLETED : ContactStatus.UNCONFIRMED)
                .attemptCount(1)
                .scheduledAt(request.call().endedAt())
                .lastAttemptAt(request.call().endedAt())
                .idempotencyKey(request.externalCallId())
                .build();
    }

    private CallObservation toObservation(ContactJob job, CallOutcomeRequest.Call call, boolean answered) {
        return CallObservation.builder()
                .contactJob(job)
                .contactStatus(answered ? ContactStatus.ANSWERED : ContactStatus.UNCONFIRMED)
                .shelterIntent(answered ? call.shelterIntent() : TriState.UNKNOWN)
                .canMoveAlone(answered ? call.canMoveAlone() : TriState.UNKNOWN)
                .helpNeeded(answered ? call.helpNeeded() : TriState.UNKNOWN)
                .symptomMentioned(answered ? call.symptomMentioned() : TriState.UNKNOWN)
                .summary(answered ? call.summary() : UNANSWERED_SUMMARY)
                .transcriptRef(call.transcriptRef())
                .confidence(answered ? call.confidence() : UNANSWERED_CONFIDENCE)
                .endedAt(call.endedAt())
                .build();
    }

    private String writeJson(Object value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (JacksonException exception) {
            throw new BusinessException(ErrorCode.INTERNAL_ERROR, exception);
        }
    }
}
