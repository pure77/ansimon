package com.nmdw.ansimon.auth.application;

import org.springframework.stereotype.Component;

import java.time.Duration;
import java.time.Instant;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.Supplier;

/**
 * 로그인 아이디별로 실패 횟수를 세어 무차별 대입을 막습니다.
 * 첫 실패부터 {@link #WINDOW} 안에 {@link #MAX_FAILURES}번 실패하면 그 시간이 끝날 때까지 로그인을 거절합니다.
 * 없는 아이디도 똑같이 세고 막으므로 차단 응답으로 계정 존재 여부가 드러나지 않습니다.
 * 서버 한 대를 전제로 한 메모리 구현이며, 서버를 여러 대로 늘리면 Redis 같은 공유 저장소로 옮겨야 합니다.
 */
@Component
public class LoginAttemptLimiter {

    static final int MAX_FAILURES = 5;
    static final Duration WINDOW = Duration.ofMinutes(15);
    private static final int MAX_TRACKED_IDS = 10_000;

    private final Map<String, Failures> failures = new ConcurrentHashMap<>();
    private final Supplier<Instant> now;

    public LoginAttemptLimiter() {
        this(Instant::now);
    }

    LoginAttemptLimiter(Supplier<Instant> now) {
        this.now = now;
    }

    public boolean isBlocked(String loginId) {
        Failures current = failures.get(key(loginId));
        return current != null && !current.expiredAt(now.get()) && current.count() >= MAX_FAILURES;
    }

    public void recordFailure(String loginId) {
        Instant at = now.get();
        if (failures.size() >= MAX_TRACKED_IDS) {
            failures.values().removeIf(entry -> entry.expiredAt(at));
        }
        failures.compute(key(loginId), (id, current) -> current == null || current.expiredAt(at)
                ? new Failures(1, at)
                : new Failures(current.count() + 1, current.firstFailureAt()));
    }

    public void recordSuccess(String loginId) {
        failures.remove(key(loginId));
    }

    private static String key(String loginId) {
        return loginId.trim().toLowerCase(Locale.ROOT);
    }

    private record Failures(int count, Instant firstFailureAt) {
        boolean expiredAt(Instant at) {
            return !at.isBefore(firstFailureAt.plus(WINDOW));
        }
    }
}
