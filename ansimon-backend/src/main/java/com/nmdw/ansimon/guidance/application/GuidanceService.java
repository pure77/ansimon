package com.nmdw.ansimon.guidance.application;

import com.nmdw.ansimon.elderly.domain.ElderlyProfile;
import com.nmdw.ansimon.elderly.infra.ElderlyProfileRepository;
import com.nmdw.ansimon.global.error.BusinessException;
import com.nmdw.ansimon.global.error.ErrorCode;
import com.nmdw.ansimon.global.util.RegionCodes;
import com.nmdw.ansimon.guidance.dto.CareRunAck;
import com.nmdw.ansimon.guidance.dto.CareRunRequest;
import com.nmdw.ansimon.guidance.dto.CareRunTriggerResponse;
import com.nmdw.ansimon.guidance.infra.client.ConnectionClient;
import com.nmdw.ansimon.risk.domain.RiskSnapshot;
import com.nmdw.ansimon.risk.infra.RiskSnapshotRepository;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * 노인 정보와 최신 시도 단위 위험도 스냅샷을 조립해 안심온 커넥션의 care-run을 실행합니다.
 * 계획과 통화 결과 저장은 커넥션이 별도로 보내는 contact 결과 콜백이 전담합니다.
 */
@Service
public class GuidanceService {

    private final ElderlyProfileRepository elderlyProfileRepository;
    private final RiskSnapshotRepository riskSnapshotRepository;
    private final ConnectionClient connectionClient;

    public GuidanceService(ElderlyProfileRepository elderlyProfileRepository,
                           RiskSnapshotRepository riskSnapshotRepository,
                           ConnectionClient connectionClient) {
        this.elderlyProfileRepository = elderlyProfileRepository;
        this.riskSnapshotRepository = riskSnapshotRepository;
        this.connectionClient = connectionClient;
    }

    public CareRunTriggerResponse triggerCareRun(Long elderlyId) {
        ElderlyProfile elderly = elderlyProfileRepository.findById(elderlyId)
                .orElseThrow(() -> new BusinessException(ErrorCode.RESOURCE_NOT_FOUND));
        RiskSnapshot riskSnapshot = riskSnapshotRepository
                .findTopByRegionCodeOrderByGeneratedAtDesc(RegionCodes.siDoCode(elderly.getRegionCode()))
                .orElseThrow(() -> new BusinessException(ErrorCode.RESOURCE_NOT_FOUND));

        CareRunRequest request = new CareRunRequest(
                new CareRunRequest.Elderly(elderly.getId(), elderly.getPhone(), elderly.getAge(),
                        elderly.getHealthNote(), elderly.getRegionCode(), elderly.getConsentStatus()),
                new CareRunRequest.Location(elderly.getLatitude(), elderly.getLongitude()),
                new CareRunRequest.Risk(riskSnapshot.getId(), riskSnapshot.getRiskScore(),
                        riskSnapshot.getRiskLevel(), riskSnapshot.getTargetStartAt(), riskSnapshot.getTargetEndAt(),
                        riskSnapshot.getPeakStartAt(), riskSnapshot.getPeakEndAt(),
                        List.of(), riskSnapshot.getModelVersion())
        );

        CareRunAck ack = connectionClient.requestCareRun(request);
        return new CareRunTriggerResponse(elderly.getId(), ack.externalCallId(), ack.answered());
    }
}
