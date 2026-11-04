package com.nmdw.ansimon.auth.application;

import com.nmdw.ansimon.auth.domain.AdminAccount;
import com.nmdw.ansimon.auth.infra.AdminAccountRepository;
import com.nmdw.ansimon.global.security.AdminBootstrapProperties;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.security.crypto.factory.PasswordEncoderFactories;
import org.springframework.security.crypto.password.PasswordEncoder;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class AdminBootstrapTest {

    private final AdminAccountRepository repository = mock(AdminAccountRepository.class);
    private final PasswordEncoder passwordEncoder = PasswordEncoderFactories.createDelegatingPasswordEncoder();

    @Test
    void createsFirstAdminWhenTableIsEmpty() throws Exception {
        when(repository.count()).thenReturn(0L);

        bootstrap(" admin ", "correct-horse-battery").run(null);

        ArgumentCaptor<AdminAccount> saved = ArgumentCaptor.forClass(AdminAccount.class);
        verify(repository).save(saved.capture());
        assertThat(saved.getValue().getLoginId()).isEqualTo("admin");
        assertThat(saved.getValue().getPasswordHash()).startsWith("{bcrypt}");
        assertThat(passwordEncoder.matches("correct-horse-battery", saved.getValue().getPasswordHash())).isTrue();
    }

    @Test
    void doesNothingWhenAnAdminAlreadyExists() throws Exception {
        when(repository.count()).thenReturn(1L);

        bootstrap("admin", "correct-horse-battery").run(null);

        verify(repository, never()).save(any());
    }

    @Test
    void skipsWhenBootstrapCredentialsAreNotConfigured() throws Exception {
        when(repository.count()).thenReturn(0L);

        bootstrap("", null).run(null);

        verify(repository, never()).save(any());
    }

    @Test
    void refusesShortBootstrapPassword() {
        when(repository.count()).thenReturn(0L);

        assertThatThrownBy(() -> bootstrap("admin", "short-pw").run(null))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("12");
        verify(repository, never()).save(any());
    }

    private AdminBootstrap bootstrap(String loginId, String password) {
        return new AdminBootstrap(repository, passwordEncoder, new AdminBootstrapProperties(loginId, password));
    }
}
