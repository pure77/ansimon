package com.nmdw.ansimon.shelter.infra;

import com.nmdw.ansimon.global.config.JpaAuditingConfig;
import com.nmdw.ansimon.shelter.domain.OpenStatus;
import com.nmdw.ansimon.shelter.domain.Shelter;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.boot.jdbc.test.autoconfigure.AutoConfigureTestDatabase;
import org.springframework.context.annotation.Import;
import org.springframework.dao.DataIntegrityViolationException;

import java.math.BigDecimal;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@DataJpaTest
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Import(JpaAuditingConfig.class)
class ShelterRepositoryTest {

    @Autowired
    private ShelterRepository shelterRepository;

    @Test
    void savesAndReloadsShelterWithAuditedUpdatedAt() {
        Shelter shelter = Shelter.builder()
                .sourceId("SRC-001")
                .name("종로구민센터 쉼터")
                .address("서울시 종로구 세종대로 1")
                .latitude(new BigDecimal("37.5730000"))
                .longitude(new BigDecimal("126.9794000"))
                .openStatus(OpenStatus.OPEN)
                .sourceVersion("2026-08-01")
                .build();

        Shelter saved = shelterRepository.saveAndFlush(shelter);

        Shelter found = shelterRepository.findById(saved.getId()).orElseThrow();
        assertThat(found.getName()).isEqualTo("종로구민센터 쉼터");
        assertThat(found.getUpdatedAt()).isNotNull();
    }

    @Test
    void rejectsDuplicateSourceId() {
        shelterRepository.saveAndFlush(Shelter.builder()
                .sourceId("SRC-DUP")
                .name("쉼터 A")
                .address("주소 A")
                .latitude(new BigDecimal("37.0000000"))
                .longitude(new BigDecimal("127.0000000"))
                .openStatus(OpenStatus.OPEN)
                .sourceVersion("v1")
                .build());

        Shelter duplicate = Shelter.builder()
                .sourceId("SRC-DUP")
                .name("쉼터 B")
                .address("주소 B")
                .latitude(new BigDecimal("37.1000000"))
                .longitude(new BigDecimal("127.1000000"))
                .openStatus(OpenStatus.OPEN)
                .sourceVersion("v1")
                .build();

        assertThatThrownBy(() -> shelterRepository.saveAndFlush(duplicate))
                .isInstanceOf(DataIntegrityViolationException.class);
    }
}
