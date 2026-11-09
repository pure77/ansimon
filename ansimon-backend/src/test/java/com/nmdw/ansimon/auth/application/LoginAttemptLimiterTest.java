package com.nmdw.ansimon.auth.application;

import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.assertThat;

class LoginAttemptLimiterTest {

    private final AtomicReference<Instant> now = new AtomicReference<>(Instant.parse("2026-11-09T00:00:00Z"));
    private final LoginAttemptLimiter limiter = new LoginAttemptLimiter(now::get);

    @Test
    void allowsFiveAttemptsWithinTheWindowThenRefuses() {
        for (int i = 0; i < LoginAttemptLimiter.MAX_FAILURES; i++) {
            assertThat(limiter.tryAcquire("admin")).isTrue();
        }

        assertThat(limiter.tryAcquire("admin")).isFalse();
        assertThat(limiter.tryAcquire("admin")).isFalse();
    }

    @Test
    void treatsLoginIdsCaseAndSpaceInsensitively() {
        for (int i = 0; i < LoginAttemptLimiter.MAX_FAILURES; i++) {
            assertThat(limiter.tryAcquire(i % 2 == 0 ? " Admin " : "admin")).isTrue();
        }

        assertThat(limiter.tryAcquire("ADMIN")).isFalse();
    }

    @Test
    void allowsAgainExactlyWhenTheWindowEnds() {
        for (int i = 0; i < LoginAttemptLimiter.MAX_FAILURES; i++) {
            limiter.tryAcquire("admin");
        }

        now.set(now.get().plus(LoginAttemptLimiter.WINDOW).minusNanos(1));
        assertThat(limiter.tryAcquire("admin")).isFalse();

        now.set(now.get().plusNanos(1));
        assertThat(limiter.tryAcquire("admin")).isTrue();
    }

    @Test
    void successClearsEarlierAttempts() {
        for (int i = 0; i < LoginAttemptLimiter.MAX_FAILURES; i++) {
            limiter.tryAcquire("admin");
        }

        limiter.recordSuccess("admin");

        assertThat(limiter.tryAcquire("admin")).isTrue();
    }

    @Test
    void countsOtherLoginIdsSeparately() {
        for (int i = 0; i < LoginAttemptLimiter.MAX_FAILURES; i++) {
            limiter.tryAcquire("attacker-target");
        }

        assertThat(limiter.tryAcquire("attacker-target")).isFalse();
        assertThat(limiter.tryAcquire("admin")).isTrue();
    }

    @Test
    void windowStartsAtTheFirstAttempt() {
        limiter.tryAcquire("admin");
        now.set(now.get().plus(LoginAttemptLimiter.WINDOW).plus(Duration.ofSeconds(1)));
        for (int i = 0; i < LoginAttemptLimiter.MAX_FAILURES; i++) {
            assertThat(limiter.tryAcquire("admin")).isTrue();
        }

        assertThat(limiter.tryAcquire("admin")).isFalse();
    }

    @Test
    void parallelAttemptsNeverExceedTheLimit() throws Exception {
        int threads = 20;
        ExecutorService pool = Executors.newFixedThreadPool(threads);
        CountDownLatch start = new CountDownLatch(1);
        try {
            List<Future<Boolean>> results = new ArrayList<>();
            for (int i = 0; i < threads; i++) {
                results.add(pool.submit(() -> {
                    start.await();
                    return limiter.tryAcquire("admin");
                }));
            }
            start.countDown();

            int allowed = 0;
            for (Future<Boolean> result : results) {
                if (result.get(5, TimeUnit.SECONDS)) {
                    allowed++;
                }
            }
            assertThat(allowed).isEqualTo(LoginAttemptLimiter.MAX_FAILURES);
        } finally {
            pool.shutdownNow();
        }
    }
}
