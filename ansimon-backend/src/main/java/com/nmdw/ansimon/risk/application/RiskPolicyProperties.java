package com.nmdw.ansimon.risk.application;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;

/**
 * ML 이 주지 않는 값(위험 등급 임계값, 예측 대상/피크 시간대)을 재배포 없이 조정할 수 있게
 * 설정으로 뺀 것입니다. 확정된 운영 정책이 아니라 MVP placeholder이므로 값 자체는
 * {@code application*.yml}의 {@code ansimon.risk.*}로 언제든 바뀐 수 있습니다.
 */
@Component
@ConfigurationProperties(prefix = "ansimon.risk")
public class RiskPolicyProperties {

    private BigDecimal mediumThreshold = new BigDecimal("0.3");
    private BigDecimal highThreshold = new BigDecimal("0.6");
    private BigDecimal criticalThreshold = new BigDecimal("0.85");
    private int targetStartHour = 13;
    private int targetEndHour = 17;
    private int peakStartHour = 14;
    private int peakEndHour = 16;

    public BigDecimal getMediumThreshold() {
        return mediumThreshold;
    }

    public void setMediumThreshold(BigDecimal mediumThreshold) {
        this.mediumThreshold = mediumThreshold;
    }

    public BigDecimal getHighThreshold() {
        return highThreshold;
    }

    public void setHighThreshold(BigDecimal highThreshold) {
        this.highThreshold = highThreshold;
    }

    public BigDecimal getCriticalThreshold() {
        return criticalThreshold;
    }

    public void setCriticalThreshold(BigDecimal criticalThreshold) {
        this.criticalThreshold = criticalThreshold;
    }

    public int getTargetStartHour() {
        return targetStartHour;
    }

    public void setTargetStartHour(int targetStartHour) {
        this.targetStartHour = targetStartHour;
    }

    public int getTargetEndHour() {
        return targetEndHour;
    }

    public void setTargetEndHour(int targetEndHour) {
        this.targetEndHour = targetEndHour;
    }

    public int getPeakStartHour() {
        return peakStartHour;
    }

    public void setPeakStartHour(int peakStartHour) {
        this.peakStartHour = peakStartHour;
    }

    public int getPeakEndHour() {
        return peakEndHour;
    }

    public void setPeakEndHour(int peakEndHour) {
        this.peakEndHour = peakEndHour;
    }
}
