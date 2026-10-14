package com.nmdw.ansimon.guidance.application;

import com.nmdw.ansimon.elderly.domain.ConsentStatus;
import com.nmdw.ansimon.elderly.domain.ElderlyProfile;
import com.nmdw.ansimon.elderly.infra.ElderlyProfileRepository;
import com.nmdw.ansimon.global.error.BusinessException;
import com.nmdw.ansimon.guidance.dto.CareRunAck;
import com.nmdw.ansimon.guidance.dto.CareRunRequest;
import com.nmdw.ansimon.guidance.dto.CareRunTriggerResponse;
import com.nmdw.ansimon.guidance.infra.client.ConnectionClient;
import com.nmdw.ansimon.risk.domain.RiskLevel;
import com.nmdw.ansimon.risk.domain.RiskSnapshot;
import com.nmdw.ansimon.risk.infra.RiskSnapshotRepository;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class GuidanceServiceTest {

    private final ElderlyProfileRepository elderlyProfileRepository = mock(ElderlyProfileRepository.class);
    private final RiskSnapshotRepository riskSnapshotRepository = mock(RiskSnapshotRepository.class);
    private final ConnectionClient connectionClient = mock(ConnectionClient.class);
    private final GuidanceService service = new GuidanceService(elderlyProfileRepository,
            riskSnapshotRepository, connectionClient);

    @Test
    void resolvesTheSiDoRiskAndDispatchesTheCompleteCareRunRequest() {
        when(elderlyProfileRepository.findById(1L)).thenReturn(Optional.of(elderly()));
        when(riskSnapshotRepository.findTopByRegionCodeOrderByGeneratedAtDesc("11"))
                .thenReturn(Optional.of(riskSnapshot()));
        when(connectionClient.requestCareRun(any())).thenReturn(new CareRunAck("CA_1", true));

        CareRunTriggerResponse response = service.triggerCareRun(1L);

        assertThat(response.elderlyId()).isEqualTo(1L);
        assertThat(response.externalCallId()).isEqualTo("CA_1");
        assertThat(response.answered()).isTrue();
        ArgumentCaptor<CareRunRequest> requestCaptor = ArgumentCaptor.forClass(CareRunRequest.class);
        verify(connectionClient).requestCareRun(requestCaptor.capture());
        assertThat(requestCaptor.getValue().elderly().phone()).isEqualTo("010-1234-5678");
        assertThat(requestCaptor.getValue().elderly().regionCode()).isEqualTo("1114000000");
        assertThat(requestCaptor.getValue().risk().score()).isEqualByComparingTo("0.8238");
        assertThat(requestCaptor.getValue().risk().modelVersion())
                .isEqualTo("heatwave-xgb-v1+illness-xgb-v1");
    }

    @Test
    void rejectsWhenTheElderlyDoesNotExist() {
        when(elderlyProfileRepository.findById(99L)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.triggerCareRun(99L)).isInstanceOf(BusinessException.class);
    }

    private ElderlyProfile elderly() {
        return ElderlyProfile.builder().id(1L).displayName("김안심").phone("010-1234-5678")
                .address("서울시 종로구 1-1").latitude(new BigDecimal("37.5730000"))
                .longitude(new BigDecimal("126.9794000")).regionCode("1114000000")
                .consentStatus(ConsentStatus.CONSENTED).healthNote("고혈압").build();
    }

    private RiskSnapshot riskSnapshot() {
        Instant now = Instant.now();
        return RiskSnapshot.builder().id(7L).regionCode("11").riskScore(new BigDecimal("0.8238"))
                .riskLevel(RiskLevel.HIGH).targetStartAt(now).targetEndAt(now.plusSeconds(3600))
                .modelVersion("heatwave-xgb-v1+illness-xgb-v1").generatedAt(now).build();
    }
}
