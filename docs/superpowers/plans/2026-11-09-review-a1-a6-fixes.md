# 리뷰 A1–A6 수정 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 이력서·포트폴리오 리뷰에서 나온 A1–A6을 고친다. 코드가 문장과 다른 곳(A4 로그인 시도 제한, A6 동시 중복 요청 500)은 코드를 고치고, 나머지는 문장을 코드 사실에 맞춘다.

**Architecture:** 백엔드는 두 군데만 바꾼다. `ContactService`에서 유니크 위반을 409로 바꾸고, `AuthService` 앞에 메모리 기반 `LoginAttemptLimiter`를 둔다. 프론트는 `api.js`에서 모든 관리자 화면에 로그아웃 버튼을 붙이고, 로그인 화면에 429 안내 문구를 넣는다. 문서는 원본을 덮어쓰지 않고 새 버전(이력서_v27, 포트폴리오_v23)으로 저장한다.

**Tech Stack:** Spring Boot 4 / Spring Security / JPA / JUnit5 + Mockito + AssertJ, 정적 HTML+JS, Word(.docx)

**Spec:** 이 대화에서 받은 리뷰 표 A1–A6과 코드 대조 결과. 원문 위치: `C:\Users\ParkMinHyun\Desktop\이력서 및 포트폴리오\이력서_v26.docx`(17·69·76·78·80·82번째 문단), `포트폴리오_v22.docx`(57번째 문단).

## Global Constraints

- 작업 브랜치: `feat/admin-jwt`에서 새로 딴 `fix/review-a1-a6`. 인증 코드가 아직 main에 없으므로 main에서 따지 않는다.
- 백엔드 명령은 `ansimon-backend`에서 `./gradlew` (PowerShell이면 `.\gradlew.bat`)로 실행한다.
- 에러 응답은 기존 `BusinessException(ErrorCode)` → `GlobalExceptionHandler` 경로만 쓴다. 새 핸들러는 만들지 않는다.
- 문서에는 코드에 있는 사실만 쓴다. 숫자(5회, 15분, 1시간, 32자, 32바이트)는 코드 상수와 같아야 한다.
- 단순 설정·주석·프론트 변경은 TDD를 생략하고 수동 확인만 한다.
- 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`를 붙인다.

## 의도적으로 하지 않는 것

- **서버 측 토큰 즉시 폐기(A3):** 관리자 계정 하나에 쓰는 콘솔이라, 요청마다 DB를 조회하는 폐기 목록을 넣으면 비용이 이득보다 큽니다. 대신 만료 1시간과 "유출 시 JWT 비밀키 교체로 전체 무효화"를 문서에 정직하게 적습니다. 면접에서 물으면 "다음 단계로 계정별 `tokens_not_before` 컬럼을 두고 JWT 검증기에서 `iat`와 비교하는 방식을 생각해 두었다"고 답합니다.
- **내부 API 키를 바이트 기준으로 바꾸기(A5):** 내부 키는 HMAC 키가 아니라 서로 비교만 하는 공유 비밀입니다. Java·Python 일곱 곳이 모두 글자 수 기준으로 일관돼 있으므로 코드는 그대로 두고, 문서에서 "API 키 32자 / JWT 비밀키 32바이트"를 나눠 적습니다.
- **IP 기준 시도 제한(A4):** 프록시 뒤에서 실제 IP를 믿을 근거가 없으므로 로그인 아이디 기준으로만 제한합니다.

## File Structure

| 파일 | 변경 | 책임 |
|---|---|---|
| `ansimon-backend/src/main/java/com/nmdw/ansimon/contact/application/ContactService.java` | 수정 | 전화 작업 저장 시 유니크 위반 → `CONFLICT` |
| `ansimon-backend/src/test/java/com/nmdw/ansimon/contact/application/ContactServiceTest.java` | 수정 | 동시 중복 테스트 1개 추가 |
| `ansimon-backend/src/main/java/com/nmdw/ansimon/global/error/ErrorCode.java` | 수정 | `TOO_MANY_LOGIN_ATTEMPTS`(429) 추가 |
| `ansimon-backend/src/main/java/com/nmdw/ansimon/auth/application/LoginAttemptLimiter.java` | 생성 | 아이디별 실패 횟수 집계·차단 판정 |
| `ansimon-backend/src/test/java/com/nmdw/ansimon/auth/application/LoginAttemptLimiterTest.java` | 생성 | 제한기 단위 테스트 |
| `ansimon-backend/src/main/java/com/nmdw/ansimon/auth/application/AuthService.java` | 수정 | 로그인 전후에 제한기 호출 |
| `ansimon-backend/src/test/java/com/nmdw/ansimon/auth/application/AuthServiceTest.java` | 수정 | 생성자 변경 + 차단 테스트 |
| `ansimon-backend/src/main/java/com/nmdw/ansimon/global/config/CorsConfig.java` | 수정 | 틀린 Javadoc(A1) 정정 |
| `ansimon_front_end/assets/api.js` | 수정 | 로그아웃 버튼 자동 부착 |
| `ansimon_front_end/login.html` | 수정 | 429 안내 문구 |
| `이력서_v27.docx`, `포트폴리오_v23.docx` (바탕화면 `이력서 및 포트폴리오`) | 생성(복사 후 수정) | A1–A6 문장 반영 |

---

### Task 1: 동시 중복 통화 결과를 409로 돌려주기 (A6)

**Files:**
- Modify: `ansimon-backend/src/main/java/com/nmdw/ansimon/contact/application/ContactService.java:21-23, 80`
- Test: `ansimon-backend/src/test/java/com/nmdw/ansimon/contact/application/ContactServiceTest.java`

**Interfaces:**
- Consumes: 기존 `ContactJobRepository.save(ContactJob)`, `flush()`(JpaRepository 상속), `ErrorCode.CONFLICT`
- Produces: 없음(내부 private 메서드 `saveContactJob(ContactJob)`)

배경: `existsByIdempotencyKey` 확인과 저장 사이에 같은 `externalCallId`가 동시에 들어오면 두 번째 INSERT가 `uk_contact_idempotency_key`에 걸린다. `ContactJob`은 IDENTITY 키라 INSERT가 `save()` 시점에 나가므로 `save`와 `flush`를 함께 감싼다. 예외를 다시 던지면 클래스의 `@Transactional`이 앞서 저장한 안내계획까지 롤백한다. `ElderlyService.delete`와 같은 방식이다.

- [ ] **Step 1: 실패하는 테스트 작성** — `ContactServiceTest`의 기존 `existsByIdempotencyKey` 테스트(145행 근처) 아래에 추가

```java
    @Test
    void reportsConflictWhenAConcurrentDuplicateHitsTheUniqueKey() {
        givenElderlyAndRiskSnapshotExist();
        doThrow(new DataIntegrityViolationException("Duplicate entry 'call-abc-123' for key 'uk_contact_idempotency_key'"))
                .when(contactJobRepository).save(any(ContactJob.class));

        assertThatThrownBy(() -> service.registerCallOutcome(request(answeredCall())))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).errorCode())
                .isEqualTo(ErrorCode.CONFLICT);
        verify(callObservationRepository, never()).save(any());
    }
```

import 추가:

```java
import org.springframework.dao.DataIntegrityViolationException;
import static org.mockito.Mockito.doThrow;
```

- [ ] **Step 2: 실패 확인**

Run: `cd ansimon-backend && ./gradlew test --tests "com.nmdw.ansimon.contact.application.ContactServiceTest"`
Expected: 새 테스트 FAIL — `DataIntegrityViolationException`이 그대로 올라와 `BusinessException`이 아님

- [ ] **Step 3: 구현** — `ContactService`

import 추가:

```java
import org.springframework.dao.DataIntegrityViolationException;
```

`registerCallOutcome`의 job 저장 줄을 바꾼다:

```java
        ContactJob job = saveContactJob(toContactJob(elderly, plan, request, answered));
```

`requireStructuredSummary` 위에 메서드 추가:

```java
    /**
     * 같은 통화 결과가 동시에 두 번 들어와 사전 중복 조회를 함께 통과하면, 두 번째 INSERT는 멱등 키 유니크 제약에 걸립니다.
     * 이를 500으로 내보내지 않고 사전 조회와 같은 409로 바꿔, 호출한 서버가 "이미 처리됨"으로 판단할 수 있게 합니다.
     * 예외가 나가면 트랜잭션이 롤백되어 먼저 저장한 안내계획도 남지 않습니다.
     */
    private ContactJob saveContactJob(ContactJob job) {
        try {
            ContactJob saved = contactJobRepository.save(job);
            contactJobRepository.flush();
            return saved;
        } catch (DataIntegrityViolationException exception) {
            throw new BusinessException(ErrorCode.CONFLICT, exception);
        }
    }
```

- [ ] **Step 4: 통과 확인**

Run: `cd ansimon-backend && ./gradlew test --tests "com.nmdw.ansimon.contact.*"`
Expected: 전부 PASS (기존 `save` 검증 테스트도 그대로 통과)

- [ ] **Step 5: 커밋**

```bash
git add ansimon-backend/src/main/java/com/nmdw/ansimon/contact/application/ContactService.java ansimon-backend/src/test/java/com/nmdw/ansimon/contact/application/ContactServiceTest.java
git commit -m "fix(contact): map concurrent duplicate call outcomes to 409 instead of 500"
```

---

### Task 2: 로그인 시도 제한 (A4)

**Files:**
- Modify: `ansimon-backend/src/main/java/com/nmdw/ansimon/global/error/ErrorCode.java:19`
- Create: `ansimon-backend/src/main/java/com/nmdw/ansimon/auth/application/LoginAttemptLimiter.java`
- Create: `ansimon-backend/src/test/java/com/nmdw/ansimon/auth/application/LoginAttemptLimiterTest.java`
- Modify: `ansimon-backend/src/main/java/com/nmdw/ansimon/auth/application/AuthService.java`
- Modify: `ansimon-backend/src/test/java/com/nmdw/ansimon/auth/application/AuthServiceTest.java:37`
- Modify: `ansimon-backend/src/test/java/com/nmdw/ansimon/global/error/ErrorCodeTest.java`

**Interfaces:**
- Produces:
  - `ErrorCode.TOO_MANY_LOGIN_ATTEMPTS` → code `"AUTH_TOO_MANY_ATTEMPTS"`, `HttpStatus.TOO_MANY_REQUESTS`
  - `LoginAttemptLimiter` (`@Component`): `boolean isBlocked(String loginId)`, `void recordFailure(String loginId)`, `void recordSuccess(String loginId)`, 상수 `MAX_FAILURES = 5`, `WINDOW = Duration.ofMinutes(15)`, 테스트용 package-private 생성자 `LoginAttemptLimiter(Supplier<Instant> now)`
  - `AuthService(AdminAccountRepository, AccessTokenIssuer, PasswordEncoder, LoginAttemptLimiter)`

규칙: 같은 아이디(trim + 소문자)로 첫 실패부터 15분 안에 5번 실패하면 그 15분이 끝날 때까지 비밀번호 확인 없이 429를 준다. 없는 아이디도 똑같이 세고 똑같이 막으므로, 차단 응답으로 계정 존재 여부가 드러나지 않는다. 성공하면 기록을 지운다. 서로 다른 아이디를 무한히 넣어 메모리를 채우는 공격에 대비해 추적 수가 10,000개를 넘으면 만료된 기록을 정리한다. 서버가 한 대라는 전제의 메모리 구현이다.

- [ ] **Step 1: 제한기 실패 테스트 작성** — `LoginAttemptLimiterTest.java`

```java
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
```

- [ ] **Step 2: 실패 확인**

Run: `cd ansimon-backend && ./gradlew test --tests "com.nmdw.ansimon.auth.application.LoginAttemptLimiterTest"`
Expected: 컴파일 실패 — `LoginAttemptLimiter` 없음

- [ ] **Step 3: 제한기 구현** — `LoginAttemptLimiter.java`

```java
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
```

- [ ] **Step 4: 제한기 통과 확인**

Run: `cd ansimon-backend && ./gradlew test --tests "com.nmdw.ansimon.auth.application.LoginAttemptLimiterTest"`
Expected: 6개 PASS

- [ ] **Step 5: AuthService 실패 테스트 작성** — `AuthServiceTest`

`setUp`의 생성자 줄(37행)과 필드를 바꾼다:

```java
    private final LoginAttemptLimiter limiter = new LoginAttemptLimiter();
```

```java
        authService = new AuthService(repository, tokenIssuer, passwordEncoder, limiter);
```

테스트 추가:

```java
    @Test
    void refusesWithoutCheckingThePasswordOnceTheLoginIdIsBlocked() {
        when(repository.findByLoginId("admin")).thenReturn(Optional.of(admin));
        for (int i = 0; i < LoginAttemptLimiter.MAX_FAILURES; i++) {
            assertThatThrownBy(() -> authService.login(new LoginRequest("admin", "wrong-password")))
                    .isInstanceOf(BusinessException.class);
        }

        assertThatThrownBy(() -> authService.login(new LoginRequest("admin", "correct-horse-battery")))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).errorCode())
                .isEqualTo(ErrorCode.TOO_MANY_LOGIN_ATTEMPTS);
        verify(tokenIssuer, never()).issue(anyString());
    }

    @Test
    void blocksUnknownLoginIdsTheSameWaySoBlockingRevealsNothing() {
        when(repository.findByLoginId("ghost")).thenReturn(Optional.empty());
        for (int i = 0; i < LoginAttemptLimiter.MAX_FAILURES; i++) {
            assertThatThrownBy(() -> authService.login(new LoginRequest("ghost", "whatever")))
                    .isInstanceOf(BusinessException.class);
        }

        assertThatThrownBy(() -> authService.login(new LoginRequest("ghost", "whatever")))
                .extracting(e -> ((BusinessException) e).errorCode())
                .isEqualTo(ErrorCode.TOO_MANY_LOGIN_ATTEMPTS);
    }

    @Test
    void successfulLoginClearsEarlierFailures() {
        when(repository.findByLoginId("admin")).thenReturn(Optional.of(admin));
        when(tokenIssuer.issue("admin")).thenReturn(new AccessTokenIssuer.IssuedToken("jwt-value", 3600));
        for (int i = 0; i < LoginAttemptLimiter.MAX_FAILURES - 1; i++) {
            assertThatThrownBy(() -> authService.login(new LoginRequest("admin", "wrong-password")))
                    .isInstanceOf(BusinessException.class);
        }

        authService.login(new LoginRequest("admin", "correct-horse-battery"));

        assertThat(limiter.isBlocked("admin")).isFalse();
    }
```

`ErrorCodeTest.exposesStableNamespacedCodesWithTheirPublicHttpStatuses` 끝에 추가:

```java
        assertThat(ErrorCode.TOO_MANY_LOGIN_ATTEMPTS.code()).isEqualTo("AUTH_TOO_MANY_ATTEMPTS");
        assertThat(ErrorCode.TOO_MANY_LOGIN_ATTEMPTS.status()).isEqualTo(HttpStatus.TOO_MANY_REQUESTS);
```

- [ ] **Step 6: 실패 확인**

Run: `cd ansimon-backend && ./gradlew test --tests "com.nmdw.ansimon.auth.*" --tests "com.nmdw.ansimon.global.error.ErrorCodeTest"`
Expected: 컴파일 실패 — 4인자 생성자와 `TOO_MANY_LOGIN_ATTEMPTS` 없음

- [ ] **Step 7: 구현**

`ErrorCode.java`의 `INVALID_CREDENTIALS` 다음 줄에 추가:

```java
    TOO_MANY_LOGIN_ATTEMPTS("AUTH_TOO_MANY_ATTEMPTS", HttpStatus.TOO_MANY_REQUESTS, "Too many failed login attempts. Try again later."),
```

`AuthService.java` — 필드·생성자·`login` 전체를 아래로 교체하고, 클래스 Javadoc 둘째 줄 끝에 "같은 아이디로 연속 실패하면 {@link LoginAttemptLimiter}가 잠시 로그인을 막습니다."를 덧붙인다:

```java
    private final AdminAccountRepository adminAccountRepository;
    private final AccessTokenIssuer accessTokenIssuer;
    private final PasswordEncoder passwordEncoder;
    private final LoginAttemptLimiter loginAttemptLimiter;
    private final String dummyHash;

    public AuthService(AdminAccountRepository adminAccountRepository,
                       AccessTokenIssuer accessTokenIssuer,
                       PasswordEncoder passwordEncoder,
                       LoginAttemptLimiter loginAttemptLimiter) {
        this.adminAccountRepository = adminAccountRepository;
        this.accessTokenIssuer = accessTokenIssuer;
        this.passwordEncoder = passwordEncoder;
        this.loginAttemptLimiter = loginAttemptLimiter;
        this.dummyHash = passwordEncoder.encode(TIMING_EQUALIZER_PASSWORD);
    }

    @Transactional
    public LoginResponse login(LoginRequest request) {
        String loginId = request.loginId().trim();
        if (loginAttemptLimiter.isBlocked(loginId)) {
            throw new BusinessException(ErrorCode.TOO_MANY_LOGIN_ATTEMPTS);
        }
        if (request.password().getBytes(StandardCharsets.UTF_8).length > BCRYPT_MAX_PASSWORD_BYTES) {
            // bcrypt 는 72바이트를 넘으면 예외를 던져 500 이 된다. 같은 비용의 더미 비교만 하고 같은 401 로 거절한다.
            passwordEncoder.matches(TIMING_EQUALIZER_PASSWORD, dummyHash);
            loginAttemptLimiter.recordFailure(loginId);
            throw new BusinessException(ErrorCode.INVALID_CREDENTIALS);
        }
        Optional<AdminAccount> account = adminAccountRepository.findByLoginId(loginId);
        String hash = account.map(AdminAccount::getPasswordHash).orElse(dummyHash);
        boolean matches = passwordEncoder.matches(request.password(), hash);
        if (account.isEmpty() || !matches) {
            loginAttemptLimiter.recordFailure(loginId);
            throw new BusinessException(ErrorCode.INVALID_CREDENTIALS);
        }
        loginAttemptLimiter.recordSuccess(loginId);
        AdminAccount admin = account.get();
        admin.recordLogin(Instant.now());
        AccessTokenIssuer.IssuedToken token = accessTokenIssuer.issue(admin.getLoginId());
        return new LoginResponse(token.value(), "Bearer", token.expiresInSeconds());
    }
```

- [ ] **Step 8: 전체 백엔드 테스트 통과 확인**

Run: `cd ansimon-backend && ./gradlew test`
Expected: BUILD SUCCESSFUL. `AuthControllerTest`는 `AuthService`를 `@MockitoBean`으로 쓰므로 영향 없음.

- [ ] **Step 9: 커밋**

```bash
git add ansimon-backend/src/main/java/com/nmdw/ansimon/global/error/ErrorCode.java ansimon-backend/src/main/java/com/nmdw/ansimon/auth/application/LoginAttemptLimiter.java ansimon-backend/src/main/java/com/nmdw/ansimon/auth/application/AuthService.java ansimon-backend/src/test/java/com/nmdw/ansimon/auth/application/LoginAttemptLimiterTest.java ansimon-backend/src/test/java/com/nmdw/ansimon/auth/application/AuthServiceTest.java ansimon-backend/src/test/java/com/nmdw/ansimon/global/error/ErrorCodeTest.java
git commit -m "feat(auth): block a login ID for 15 minutes after 5 failed attempts"
```

---

### Task 3: 프론트 로그아웃 버튼·429 문구, CORS 주석 정정 (A3·A4·A1)

> 실행 중 결정: 로그아웃 버튼은 api.js에 이미 있어 Step 1을 건너뛰었다(중복 방지). 최종 리뷰 후 로그인 제한은 tryAcquire 원자 예약으로, 409 매핑은 멱등 키 제약 위반으로만 좁혔다.

**Files:**
- Modify: `ansimon_front_end/assets/api.js` (토큰 함수 블록 아래, 36행 `if (!IS_LOGIN_PAGE && !getToken()) redirectToLogin();` 다음)
- Modify: `ansimon_front_end/login.html:50-52`
- Modify: `ansimon-backend/src/main/java/com/nmdw/ansimon/global/config/CorsConfig.java:12-16`

**Interfaces:**
- Consumes: 기존 `clearToken()`, `apiParam(prefix)`, `$()`, `IS_LOGIN_PAGE`; Task 2의 에러 코드 문자열 `"AUTH_TOO_MANY_ATTEMPTS"`

- [ ] **Step 1: 로그아웃 버튼** — `api.js`에 추가

```js
/* 관리자 화면 상단 nav 오른쪽에 로그아웃 버튼을 붙인다.
   서버는 토큰을 따로 폐기하지 않으므로(만료 1시간) 이 브라우저의 사본을 지우고 로그인 화면으로 보낸다. */
function mountLogoutButton() {
  const nav = $(".nav");
  if (IS_LOGIN_PAGE || !nav || $("#logout-btn")) return;
  const button = document.createElement("button");
  button.id = "logout-btn";
  button.type = "button";
  button.className = "pill-btn";
  button.textContent = "로그아웃";
  button.addEventListener("click", () => {
    clearToken();
    location.href = `login.html${apiParam("?")}`;
  });
  (nav.querySelector(".nav-end") || nav).appendChild(button);
}
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mountLogoutButton);
else mountLogoutButton();
```

- [ ] **Step 2: 429 문구** — `login.html`의 catch 블록을 교체

```js
    } catch (err) {
      $("#login-error").textContent = err.code === "AUTH_INVALID_CREDENTIALS"
        ? "아이디 또는 비밀번호가 올바르지 않습니다."
        : err.code === "AUTH_TOO_MANY_ATTEMPTS"
          ? "로그인 실패가 많아 잠시 막혔습니다. 15분 뒤 다시 시도하세요."
          : `로그인할 수 없습니다 (${err.message}).`;
```

- [ ] **Step 3: CORS Javadoc 정정** — `CorsConfig.java` 클래스 주석 교체

```java
/**
 * 관리자 프론트엔드가 다른 출처에서 관리자 API({@code /api/**})를 호출할 수 있도록 CORS 정책을 한곳에서 정의합니다.
 * 허용 출처는 {@link CorsProperties}가 설정에서 읽어오며, 이 소스는 관리자 보안 체인에만 연결됩니다.
 * {@code /internal/**}은 브라우저가 부를 경로가 아니므로 CORS를 열지 않습니다. CORS는 브라우저가 응답을 읽는 것만 제한하므로
 * 내부 API의 실제 차단은 {@code InternalApiKeyFilter}의 API 키 검사가 맡습니다.
 * 인증 쿠키를 쓰지 않으므로 자격 증명 전송은 허용하지 않습니다.
 */
```

- [ ] **Step 4: 수동 확인** — 백엔드(`./gradlew bootRun`, local 프로필)와 프론트(`ansimon_front_end`를 정적 서버로, 예: `npx serve -l 5500 ansimon_front_end`)를 띄운다.
  1. 로그인 → `index.html`, `elderly.html`, `elderly-detail.html` 각각 nav에 "로그아웃" 버튼이 한 개씩 보인다.
  2. 로그아웃 클릭 → `login.html`로 이동하고, 개발자도구에서 `sessionStorage.getItem("ansimon.accessToken")`가 `null`이다.
  3. 틀린 비밀번호로 5번 → 6번째에 "로그인 실패가 많아…" 문구가 나온다. 네트워크 탭 응답이 429, `error.code`가 `AUTH_TOO_MANY_ATTEMPTS`다.

- [ ] **Step 5: 커밋**

```bash
git add ansimon_front_end/assets/api.js ansimon_front_end/login.html ansimon-backend/src/main/java/com/nmdw/ansimon/global/config/CorsConfig.java
git commit -m "feat(front): add logout button and lockout message; fix CORS config javadoc"
```

---

### Task 4: 이력서·포트폴리오 문장 수정 (A1–A6)

**Files (바탕화면 `이력서 및 포트폴리오` 폴더):**
- Create: `이력서_v27.docx` (`이력서_v26.docx` 복사 후 수정)
- Create: `포트폴리오_v23.docx` (`포트폴리오_v22.docx` 복사 후 수정)

**Interfaces:**
- Consumes: Task 1·2의 동작(409, 5회/15분, 429). 반드시 Task 1·2 커밋 뒤에 진행한다.

방법: `anthropic-skills:docx` 스킬로 아래 문단의 텍스트만 바꾸고 서식(글꼴·굵기·글머리)은 그대로 둔다. 문단 번호는 `word/document.xml`을 `</w:p>` 기준으로 나눴을 때의 순번이다. 작업 전에 원문이 아래 "기존 시작"과 같은지 확인하고, 다르면 멈추고 사용자에게 묻는다.

- [ ] **Step 1: 이력서 69번째 문단 (A2)**
  - 기존 시작: `담당  백엔드 단독 — 서버와 DB 배포 파이프라인, …`
  - 새 문장: `담당  팀 단계: 백엔드 단독 — 서버와 DB 배포 파이프라인, 도메인 API, ML·LLM·RAG 서버 연동 / 개인 단계: 백엔드와 연결 서버(Python)·전화 발신 서버의 서버 간 인증 보강`

- [ ] **Step 2: 이력서 76번째 문단 (A2·A5)**
  - 기존 시작: `공개 API와 서버끼리만 쓰는 내부 콜백 API가 …`
  - 바꿀 부분 1: 문단 맨 앞에 `(해커톤 이후 개인 작업) ` 추가
  - 바꿀 부분 2: `키가 없거나 32자보다 짧으면` → `내부 API 키가 32자, JWT 비밀키가 32바이트(256비트)보다 짧거나 비어 있으면`

- [ ] **Step 3: 이력서 78번째 문단 (A2)**
  - 기존 시작: `전화 발신 서버는 요청에 담긴 주소로 …`
  - 바꿀 부분: 문단 맨 앞에 `(해커톤 이후 개인 작업, 연결 서버·전화 발신 서버 코드 직접 수정) ` 추가

- [ ] **Step 4: 이력서 80번째 문단 (A3·A4)** — 문단 전체 교체

`(해커톤 이후 개인 작업) 관리자 API가 인증 없이 열려 있어 누구나 어르신의 이름·전화번호·주소를 조회하고 실제 전화까지 실행할 수 있었습니다. 관리자 화면이 백엔드와 다른 주소에서 뜨는 정적 파일이라, 쿠키를 쓰면 교차 출처 쿠키 설정과 CSRF 방어가 따로 필요해 요청 헤더로 보내는 토큰(JWT) 방식으로 로그인을 만들었습니다. 토큰은 탭을 닫으면 사라지는 sessionStorage에 두고 1시간 뒤 만료되게 했습니다. 없는 아이디와 틀린 비밀번호에 같은 응답을 돌려주고 비밀번호 해시 비교도 똑같이 한 번씩 수행해 처리 시간 차이를 줄였고, 같은 아이디로 15분 안에 5번 틀리면 15분 동안 로그인을 막아 무차별 대입을 차단했습니다.`

- [ ] **Step 5: 이력서 82번째 문단 (A6)**
  - 기존 끝: `…DB 유니크 제약으로 관리해 이미 처리한 요청은 다시 저장하지 않도록 했습니다.`
  - 새 끝: `…DB 유니크 제약으로 관리해 이미 처리한 요청은 409로 거절했습니다. 두 요청이 동시에 들어와 사전 조회를 함께 통과해도 유니크 제약 위반을 409로 바꿔, 500 오류 없이 한 건만 저장됩니다.`

- [ ] **Step 6: 포트폴리오 57번째 문단 (A1·A3·A5)** — 문단 전체 교체

`/internal 체인은 서버끼리만 아는 API 키를 요구합니다. 브라우저에서 부를 경로가 아니므로 CORS 허용도 두지 않았습니다. CORS는 브라우저가 다른 출처의 응답을 읽지 못하게 하는 규칙일 뿐 서버 간 호출이나 curl은 막지 못하므로, 실제 차단은 API 키가 합니다. 키는 응답 시간으로 추측할 수 없도록 상수 시간으로 비교하고, 새 키와 이전 키를 함께 받아 서버를 멈추지 않고 교체할 수 있게 했습니다. /api 체인은 관리자 JWT(로그인 후 받는 서명된 출입증)를 요구합니다. 관리자 화면은 백엔드와 다른 주소에서 뜨는 정적 파일이라, 쿠키를 쓰면 교차 출처 쿠키 설정과 CSRF 방어가 따로 필요합니다. 그래서 요청 헤더로 토큰을 보내고, 토큰은 탭을 닫으면 사라지는 sessionStorage에 두며 1시간 뒤 만료되게 했습니다. 서버에서 개별 토큰을 즉시 폐기하는 기능은 없어, 유출이 의심되면 JWT 비밀키를 바꿔 모든 토큰을 한 번에 무효화합니다. 또 내부 API 키가 32자, JWT 비밀키가 32바이트(HS256 키 길이 256비트)보다 짧거나 비어 있으면 서버가 시작되지 않게 해, 설정을 빠뜨린 채 배포되는 일을 막았습니다.`

- [ ] **Step 7: 검증** — 두 새 파일에서 텍스트를 뽑아 바뀐 문장을 확인하고, 옛 표현이 남지 않았는지 본다.

Run:
```bash
cd "/c/Users/ParkMinHyun/Desktop/이력서 및 포트폴리오" && for f in 이력서_v27.docx 포트폴리오_v23.docx; do echo "== $f"; unzip -p "$f" word/document.xml | sed -e 's#</w:p>#\n#g' -e 's/<[^>]*>//g' | grep -c -E "CORS\(다른 사이트에서의 호출 허용 규칙\)를 껐|같은 처리 시간을|32자보다 짧으면|다시 저장하지 않도록"; done
```
Expected: 두 파일 모두 `0`

Word로 두 파일을 열어 줄바꿈·페이지 넘침이 없는지 눈으로 확인한다. 이력서가 한 페이지를 넘으면 사용자에게 알린다.

---

## Self-Review 결과

- A1 → Task 3(주석) + Task 4 Step 6 / A2 → Task 4 Step 1–4 / A3 → Task 3(로그아웃) + Task 4 Step 4·6, 즉시 폐기는 "하지 않는 것"에 근거와 함께 명시 / A4 → Task 2 + Task 3(문구) + Task 4 Step 4 / A5 → Task 4 Step 2·6, 코드 유지 근거 명시 / A6 → Task 1 + Task 4 Step 5.
- 이름 일관성: `LoginAttemptLimiter.MAX_FAILURES/WINDOW`, `ErrorCode.TOO_MANY_LOGIN_ATTEMPTS`, 코드 문자열 `AUTH_TOO_MANY_ATTEMPTS`를 Task 2·3·4에서 같은 이름으로 썼다.
- A2의 대회 기간·담당 범위는 git 기록(연결 서버 보안 커밋 2026-11-03~04, 작성자 pure77)으로만 확인했다. 대회 중에 한 일과 섞이지 않았는지는 사용자가 최종 확인한다.
