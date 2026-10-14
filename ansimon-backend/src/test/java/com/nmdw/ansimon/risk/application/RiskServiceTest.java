package com.nmdw.ansimon.risk.application;

import com.nmdw.ansimon.risk.domain.RiskLevel;
import com.nmdw.ansimon.risk.domain.RiskSnapshot;
import com.nmdw.ansimon.risk.dto.MlForecastResponse;
import com.nmdw.ansimon.risk.dto.RiskForecastRequest;
import com.nmdw.ansimon.risk.dto.RiskForecastResponse;
import com.nmdw.ansimon.risk.infra.RiskSnapshotRepository;
import com.nmdw.ansimon.risk.infra.client.MlClient;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.json.JsonMapper;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class RiskServiceTest {

    private final MlClient mlClient = mock(MlClient.class);
    private final RiskSnapshotRepository riskSnapshotRepository = mock(RiskSnapshotRepository.class);
    private final RiskService service = new RiskService(mlClient, riskSnapshotRepository,
            new RiskPolicyProperties(), JsonMapper.builder().build());

    @Test
    void classifiesTheScoreIntoARiskLevelAndSavesTheSnapshotForTheDefaultRegion() {
        when(mlClient.forecast("서울")).thenReturn(new MlForecastResponse(
                "2026-08-18", "서울", 0.067534, "X", 0.823778,
                "historical_analog", 159, "heatwave-xgb-v1+illness-xgb-v1"));
        when(riskSnapshotRepository.save(any(RiskSnapshot.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        RiskForecastResponse response = service.forecast(new RiskForecastRequest(null));

        verify(mlClient).forecast("서울");
        assertThat(response.regionCode()).isEqualTo("11");
        assertThat(response.riskLevel()).isEqualTo(RiskLevel.HIGH);
        assertThat(response.riskScore()).isEqualByComparingTo("0.8238");
    }

    @Test
    void classifiesALowScoreAsLowRisk() {
        when(mlClient.forecast("서울")).thenReturn(new MlForecastResponse(
                "2026-08-18", "서울", 0.02, "X", 0.10,
                "historical_analog", 40, "heatwave-xgb-v1+illness-xgb-v1"));
        when(riskSnapshotRepository.save(any(RiskSnapshot.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        RiskForecastResponse response = service.forecast(new RiskForecastRequest(null));

        assertThat(response.riskLevel()).isEqualTo(RiskLevel.LOW);
    }
}
