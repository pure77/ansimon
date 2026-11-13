package com.nmdw.ansimon.auth.application;

import org.springframework.stereotype.Component;

import java.time.Duration;
import java.time.Instant;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.Supplier;

/**
 * 로그인 아이디별로 비밀번호 확인 시도 횟수를 세어 무차별 대입을 막습니다.
 * 비밀번호를 확인하기 전에 {@link #tryAcquire}로 시도 한 번을 원자적으로 예약하므로, 동시에 요청이 몰려도
 * 첫 시도부터 {@link #WINDOW} 안에 {@link #MAX_FAILURES}번까지만 비밀번호 확인에 도달하고 나머지는 그 시간이 끝날 때까지 거절됩니다.
 * 로그인에 성공하면 {@link #recordSuccess}로 횟수를 지웁니다.
 * 없는 아이디도 똑같이 세고 막으므로 차단 응답으로 계정 존재 여부가 드러나지 않습니다.
 * 아이디 단위로 막기 때문에 누구든 알려진 아이디(예: admin)로 계속 시도해 그 계정을 막아 둘 수 있습니다.
 * 프록시 뒤에서는 믿을 만한 클라이언트 IP가 없어 이를 감수하는 절충입니다.
 * 서버 한 대를 전제로 한 메모리 구현이라 프로세스를 재시작하면 기록이 사라지며,
 * 서버를 여러 대로 늘리면 Redis 같은 공유 저장소로 옮겨야 합니다.
 * 추적 중인 아이디가 10,000개를 넘으면 만료된 항목을 정리할 뿐, 개수에 대한 엄격한 상한은 아닙니다.
 */
@Component
public class LoginAttemptLimiter {

    static final int MAX_FAILURES = 5;
    static final Duration WINDOW = Duration.ofMinutes(15);
    private static final int MAX_TRACKED_IDS = 10_000;

    private final Map<String, Attempts> attempts = new ConcurrentHashMap<>();
    private final Supplier<Instant> now;

    public LoginAttemptLimiter() {
        this(Instant::now);
    }

    LoginAttemptLimiter(Supplier<Instant> now) {
        this.now = now;
    }

    /**
     * 비밀번호를 확인하기 전에 시도 한 번을 예약합니다. 한도 안이면 횟수를 올리고 true, 이미 한도에 닿았으면 false입니다.
     * 확인과 증가가 한 번의 원자적 갱신이라 동시 요청이 한도를 넘겨 통과할 수 없습니다.
     */
    public boolean tryAcquire(String loginId) {
        Instant at = now.get();
        if (attempts.size() >= MAX_TRACKED_IDS) {
            attempts.values().removeIf(entry -> entry.expiredAt(at));
        }
        boolean[] allowed = new boolean[1];
        attempts.compute(key(loginId), (id, current) -> {
            if (current == null || current.expiredAt(at)) {
                allowed[0] = true;
                return new Attempts(1, at);
            }
            if (current.count() >= MAX_FAILURES) {
                return current;
            }
            allowed[0] = true;
            return new Attempts(current.count() + 1, current.firstAttemptAt());
        });
        return allowed[0];
    }

    public void recordSuccess(String loginId) {
        attempts.remove(key(loginId));
    }

    private static String key(String loginId) {
        return loginId.trim().toLowerCase(Locale.ROOT);
    }

    private record Attempts(int count, Instant firstAttemptAt) {
        boolean expiredAt(Instant at) {
            return !at.isBefore(firstAttemptAt.plus(WINDOW));
        }
    }
}
