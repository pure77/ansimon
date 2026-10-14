package com.nmdw.ansimon.support.infra;

import com.nmdw.ansimon.elderly.domain.ConsentStatus;
import com.nmdw.ansimon.elderly.domain.ElderlyProfile;
import com.nmdw.ansimon.elderly.infra.ElderlyProfileRepository;
import com.nmdw.ansimon.global.config.JpaAuditingConfig;
import com.nmdw.ansimon.support.domain.SupportPriority;
import com.nmdw.ansimon.support.domain.SupportStatus;
import com.nmdw.ansimon.support.domain.SupportTask;
import com.nmdw.ansimon.support.domain.SupportTaskType;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.boot.jdbc.test.autoconfigure.AutoConfigureTestDatabase;
import org.springframework.context.annotation.Import;
import org.springframework.dao.DataIntegrityViolationException;

import java.math.BigDecimal;
import java.time.Instant;
import java.time.temporal.ChronoUnit;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@DataJpaTest
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Import(JpaAuditingConfig.class)
class SupportTaskRepositoryTest {

    @Autowired
    private SupportTaskRepository supportTaskRepository;

    @Autowired
    private ElderlyProfileRepository elderlyProfileRepository;

    private ElderlyProfile persistElderly() {
        return elderlyProfileRepository.saveAndFlush(ElderlyProfile.builder()
                .displayName("김안심")
                .phone("hashed-phone-value")
                .address("서울시 종로구 1-1")
                .latitude(new BigDecimal("37.5730000"))
                .longitude(new BigDecimal("126.9794000"))
                .regionCode("11110")
                .consentStatus(ConsentStatus.CONSENTED)
                .build());
    }

    @Test
    void savesAndReloadsSupportTaskWithoutContactJobOrAssignee() {
        ElderlyProfile elderly = persistElderly();
        Instant now = Instant.now().truncatedTo(ChronoUnit.MILLIS);

        SupportTask task = SupportTask.builder()
                .elderly(elderly)
                .contactJob(null)
                .assigneeId(null)
                .taskType(SupportTaskType.WELFARE_CHECK)
                .priority(SupportPriority.HIGH)
                .status(SupportStatus.PENDING)
                .reason("2회 미응답으로 수동 확인 필요")
                .dueAt(now.plusSeconds(7200))
                .deduplicationKey("support-key-1")
                .build();

        SupportTask saved = supportTaskRepository.saveAndFlush(task);

        SupportTask found = supportTaskRepository.findById(saved.getId()).orElseThrow();
        assertThat(found.getContactJob()).isNull();
        assertThat(found.getAssigneeId()).isNull();
        assertThat(found.getStatus()).isEqualTo(SupportStatus.PENDING);
        assertThat(found.getCreatedAt()).isNotNull();
    }

    @Test
    void rejectsDuplicateDeduplicationKey() {
        ElderlyProfile elderly = persistElderly();
        Instant now = Instant.now().truncatedTo(ChronoUnit.MILLIS);

        supportTaskRepository.saveAndFlush(SupportTask.builder()
                .elderly(elderly)
                .taskType(SupportTaskType.WELFARE_CHECK)
                .priority(SupportPriority.HIGH)
                .status(SupportStatus.PENDING)
                .reason("사유")
                .dueAt(now.plusSeconds(3600))
                .deduplicationKey("dup-support-key")
                .build());

        SupportTask duplicate = SupportTask.builder()
                .elderly(elderly)
                .taskType(SupportTaskType.WELFARE_CHECK)
                .priority(SupportPriority.HIGH)
                .status(SupportStatus.PENDING)
                .reason("중복 시도")
                .dueAt(now.plusSeconds(3600))
                .deduplicationKey("dup-support-key")
                .build();

        assertThatThrownBy(() -> supportTaskRepository.saveAndFlush(duplicate))
                .isInstanceOf(DataIntegrityViolationException.class);
    }
}
