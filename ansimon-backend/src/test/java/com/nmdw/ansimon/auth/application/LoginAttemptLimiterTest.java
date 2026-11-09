package com.nmdw.ansimon.auth.application;

import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.time.Instant;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.assertThat;

class LoginAttemptLimiterTest {

    private final AtomicReference<Instant> now = new AtomicReference<>(Instant.parse("2026-11-09T00:00:00Z"));
    private final LoginAttemptLimiter limiter = new LoginAttemptLimiter(now::get);

    @Test
    void blocksAfterFiveFailuresWithinTheWindow() {
        for (int i = 0; i < LoginAttemptLimiter.MAX_FAILURES - 1; i++) {
            limiter.recordFailure("admin");
        }
        assertThat(limiter.isBlocked("admin")).isFalse();

        limiter.recordFailure("admin");

        assertThat(limiter.isBlocked("admin")).isTrue();
    }

    @Test
    void treatsLoginIdsCaseAndSpaceInsensitively() {
        for (int i = 0; i < LoginAttemptLimiter.MAX_FAILURES; i++) {
            limiter.recordFailure(i % 2 == 0 ? " Admin " : "admin");
        }

        assertThat(limiter.isBlocked("ADMIN")).isTrue();
    }

    @Test
    void unblocksOnceTheWindowHasPassed() {
        for (int i = 0; i < LoginAttemptLimiter.MAX_FAILURES; i++) {
            limiter.recordFailure("admin");
        }

        now.set(now.get().plus(LoginAttemptLimiter.WINDOW));

        assertThat(limiter.isBlocked("admin")).isFalse();
    }

    @Test
    void successClearsEarlierFailures() {
        for (int i = 0; i < LoginAttemptLimiter.MAX_FAILURES - 1; i++) {
            limiter.recordFailure("admin");
        }

        limiter.recordSuccess("admin");
        limiter.recordFailure("admin");

        assertThat(limiter.isBlocked("admin")).isFalse();
    }

    @Test
    void countsOtherLoginIdsSeparately() {
        for (int i = 0; i < LoginAttemptLimiter.MAX_FAILURES; i++) {
            limiter.recordFailure("attacker-target");
        }

        assertThat(limiter.isBlocked("admin")).isFalse();
    }

    @Test
    void windowStartsAtTheFirstFailure() {
        limiter.recordFailure("admin");
        now.set(now.get().plus(LoginAttemptLimiter.WINDOW).plus(Duration.ofSeconds(1)));
        for (int i = 0; i < LoginAttemptLimiter.MAX_FAILURES - 1; i++) {
            limiter.recordFailure("admin");
        }

        assertThat(limiter.isBlocked("admin")).isFalse();
    }
}
