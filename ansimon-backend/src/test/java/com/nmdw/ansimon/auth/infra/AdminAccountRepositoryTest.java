package com.nmdw.ansimon.auth.infra;

import com.nmdw.ansimon.auth.domain.AdminAccount;
import com.nmdw.ansimon.global.config.JpaAuditingConfig;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.boot.jdbc.test.autoconfigure.AutoConfigureTestDatabase;
import org.springframework.context.annotation.Import;
import org.springframework.dao.DataIntegrityViolationException;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@DataJpaTest
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Import(JpaAuditingConfig.class)
class AdminAccountRepositoryTest {

    @Autowired
    private AdminAccountRepository repository;

    @Test
    void savesAndFindsByLoginIdWithAuditedTimestamp() {
        repository.saveAndFlush(AdminAccount.create("admin", "{bcrypt}hash"));

        AdminAccount found = repository.findByLoginId("admin").orElseThrow();

        assertThat(found.getPasswordHash()).isEqualTo("{bcrypt}hash");
        assertThat(found.getCreatedAt()).isNotNull();
    }

    @Test
    void returnsEmptyForUnknownLoginId() {
        assertThat(repository.findByLoginId("ghost")).isEmpty();
    }

    @Test
    void rejectsDuplicateLoginId() {
        repository.saveAndFlush(AdminAccount.create("admin", "{bcrypt}hash"));

        assertThatThrownBy(() -> repository.saveAndFlush(AdminAccount.create("admin", "{bcrypt}other")))
                .isInstanceOf(DataIntegrityViolationException.class);
    }
}
