# 내부 API 서비스 간 인증 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 경로로만 나뉘어 있던 외부 공개 API(`/api/v1/**`)와 내부 콜백 API(`/internal/v1/**`)에 실제로 다른 보안 정책을 적용한다. 백엔드 → 연결 서버, 연결 서버 → 백엔드 양방향 호출에 서비스 간 Bearer 키 인증을 건다.

**Architecture:** 백엔드에 Spring Security를 도입하고 `SecurityFilterChain`을 경로별로 두 개 둔다. 내부 체인(`/internal/**`, `@Order(1)`)은 다음 정책을 적용한다.
- `InternalApiKeyFilter`가 Bearer 키를 상수 시간 비교로 검증하고, 실패하면 401 `ApiResponse`를 반환한다.
- CORS는 끈다.
- 키 목록을 지원해 무중단으로 키를 교체할 수 있다.

공개 체인(나머지 전부, `@Order(2)`)은 기존 동작(무인증)을 유지하고, CORS를 `/api/**`에만 허용한다. 연결 서버(aiohttp)에는 미들웨어로 같은 수준의 Bearer 검증을 넣는다.

**Tech Stack:** Spring Boot 4.1 / Spring Security 7 / Jackson 3(`tools.jackson`) / JUnit 5 + MockMvc, Python 3 + aiohttp(연결 서버, 자체 테스트 하네스 `test_connection.py`).

**Spec:** 별도 spec 문서 없음. 설계 결정은 아래 "배경과 결정"에 정리했다.

## 배경과 결정

- 현재 상태: Spring Security 의존성이 없다. `/internal/v1/contact/results`, `/internal/v1/guidance/care-runs/{id}`, `/internal/v1/risk/forecast`를 누구나 호출할 수 있다. CORS도 `/**` 전체에 열려 있다.
- 연결 서버(`ansimon-connection/backend_client.py`, `voice/report.py`)는 이미 `ANSIMON_BACKEND_TOKEN`을 Bearer로 보낸다. **백엔드가 검증하지 않았을 뿐**이다.
- 백엔드는 연결 서버를 호출할 때 이미 `Authorization: Bearer ${CONNECTION_API_KEY}`를 붙인다(`WebClientConfig`). **연결 서버 `server.py`가 검증하지 않았을 뿐**이다.
- 이번 범위에서 `/api/v1/**` 관리자 인증(JWT)은 제외한다. 공개 체인은 `permitAll`을 유지한다.
- 연결 서버의 `/internal/**`(전화 모듈 콜백)은 `ANSIMON_BACKEND_TOKEN`으로 검증한다. 전화 모듈은 콜백 주소가 백엔드든 연결 서버든 같은 토큰을 붙이기 때문이다. 결과적으로 "내부 콜백을 받는 쪽은 모두 같은 콜백 토큰으로 검증한다"는 규칙이 된다.

| 호출 방향 | 보내는 쪽 설정 | 받는 쪽 검증 설정 |
|---|---|---|
| 연결 서버 → 백엔드 `/internal/**` | `ANSIMON_BACKEND_TOKEN` | `INTERNAL_API_KEYS` (같은 값 포함) |
| 전화 모듈 → 연결 서버 `/internal/**` | `ANSIMON_BACKEND_TOKEN` | `ANSIMON_BACKEND_TOKEN` |
| 백엔드 → 연결 서버 `/v1/**` | `CONNECTION_API_KEY` | `CONNECTION_API_KEY` |

## Global Constraints

- 내부 API 키는 32자 이상이어야 한다. 생성 예: `openssl rand -hex 32`.
- 키 비교는 반드시 상수 시간으로 한다. Java는 `MessageDigest.isEqual`, Python은 `hmac.compare_digest`를 쓴다. `equals`나 `==`는 금지한다.
- 인증 실패 응답은 기존 공통 포맷 `{success:false, data:null, error:{code, message, details}}`를 따른다. 백엔드 코드는 `GLOBAL_UNAUTHORIZED`다.
- 키가 설정되지 않은 경우 동작:
  - 백엔드: 기동에 실패해야 한다(fail-fast).
  - 연결 서버: 해당 경로 요청에 503을 반환한다(fail-closed).
- `InternalApiKeyFilter`는 **Spring 빈으로 등록하지 않는다.** `@Component`를 붙이면 Boot가 서블릿 필터로 자동 등록해 모든 경로에 적용된다. `SecurityConfig` 안에서 `new`로 생성한다.
- 코드 주석과 Javadoc은 기존 스타일(한국어, 클래스 Javadoc 3줄 내외)을 따른다.
- git 저장소 루트는 `ansimon_total/`이다. gradle 명령은 `ansimon-backend/`, python 명령은 `ansimon-connection/`에서 실행한다.

## File Structure

**백엔드 (`ansimon-backend/`)**

| 파일 | 변경 | 책임 |
|---|---|---|
| `build.gradle` | Modify | security starter, security-test starter 추가 |
| `src/main/java/com/nmdw/ansimon/global/error/ErrorCode.java` | Modify | `UNAUTHORIZED` 추가 |
| `src/main/java/com/nmdw/ansimon/global/security/InternalApiProperties.java` | Create | `ansimon.internal.api-keys` 바인딩과 검증(공백 제거, 비어 있음 금지, 32자 이상) |
| `src/main/java/com/nmdw/ansimon/global/security/InternalApiKeyFilter.java` | Create | Bearer 키 상수 시간 검증 후 인증 객체 설정 |
| `src/main/java/com/nmdw/ansimon/global/security/JsonAuthenticationEntryPoint.java` | Create | 401을 공통 `ApiResponse` JSON으로 응답 |
| `src/main/java/com/nmdw/ansimon/global/security/SecurityConfig.java` | Create | 내부 체인과 공개 체인 두 개 정의 |
| `src/main/java/com/nmdw/ansimon/global/config/CorsConfig.java` | Modify | `WebMvcConfigurer`를 `CorsConfigurationSource` 빈(`/api/**`만 허용)으로 교체 |
| `src/main/resources/application-local.yml`, `application-prod.yml` | Modify | `ansimon.internal.api-keys`, prod의 `CONNECTION_API_KEY` 필수화 |
| `src/test/resources/application.yml` | Modify | 테스트용 키 2개(current, previous) |
| `.env.example` | Modify | `INTERNAL_API_KEYS` 안내 |
| `src/test/java/com/nmdw/ansimon/global/security/InternalApiPropertiesTest.java` | Create | 프로퍼티 검증 단위 테스트 |
| `src/test/java/com/nmdw/ansimon/global/security/InternalApiSecurityTest.java` | Create | 체인 동작 MockMvc 테스트 |
| `src/test/java/com/nmdw/ansimon/global/error/ErrorCodeTest.java` | Modify | `UNAUTHORIZED` 단언 추가 |
| 기존 `@WebMvcTest` 5개 | Modify | `@Import(SecurityConfig.class)` 추가, internal 호출에 키 헤더 추가 |

**연결 서버 (`ansimon-connection/`)**

| 파일 | 변경 | 책임 |
|---|---|---|
| `server.py` | Modify | `require_bearer` 미들웨어 |
| `backend_client.py` | Modify | 토큰 없이 전송하지 않음(fail-loud) |
| `test_connection.py` | Modify | 인증 테스트 3개 |
| `.env.example` | Modify | `CONNECTION_API_KEY` 항목과 토큰 설명 |

---

### Task 1: 내부 API 키 설정 타입과 401 오류 코드

이 태스크에서는 아직 security 의존성을 추가하지 않는다. 의존성을 넣는 순간 기존 WebMvc 테스트가 기본 보안 설정 때문에 깨지므로 Task 2에서 한꺼번에 처리한다.

**Files:**
- Modify: `ansimon-backend/src/main/java/com/nmdw/ansimon/global/error/ErrorCode.java`
- Modify: `ansimon-backend/src/test/java/com/nmdw/ansimon/global/error/ErrorCodeTest.java`
- Create: `ansimon-backend/src/main/java/com/nmdw/ansimon/global/security/InternalApiProperties.java`
- Test: `ansimon-backend/src/test/java/com/nmdw/ansimon/global/security/InternalApiPropertiesTest.java`

**Interfaces:**
- Produces:
  - `ErrorCode.UNAUTHORIZED`: code `"GLOBAL_UNAUTHORIZED"`, `HttpStatus.UNAUTHORIZED`, message `"Authentication is required."`
  - `record InternalApiProperties(List<String> apiKeys)`: prefix `ansimon.internal`. `apiKeys()`는 trim된, 비어 있지 않은, 32자 이상 키만 담은 불변 리스트다.

- [ ] **Step 1: 실패하는 테스트 작성**

`ErrorCodeTest.exposesStableNamespacedCodesWithTheirPublicHttpStatuses()` 마지막 단언 뒤에 다음을 추가한다.

```java
        assertThat(ErrorCode.UNAUTHORIZED.code()).isEqualTo("GLOBAL_UNAUTHORIZED");
        assertThat(ErrorCode.UNAUTHORIZED.status()).isEqualTo(HttpStatus.UNAUTHORIZED);
```

`InternalApiPropertiesTest.java`를 새로 만든다.

```java
package com.nmdw.ansimon.global.security;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class InternalApiPropertiesTest {

    private static final String KEY = "test-internal-key-current-0000000000";

    @Test
    void trimsKeysAndDropsBlankEntries() {
        InternalApiProperties properties = new InternalApiProperties(List.of("  " + KEY + "  ", "", "   "));

        assertThat(properties.apiKeys()).containsExactly(KEY);
    }

    @Test
    void refusesToStartWithoutAnyKey() {
        assertThatThrownBy(() -> new InternalApiProperties(null))
                .isInstanceOf(IllegalStateException.class);
        assertThatThrownBy(() -> new InternalApiProperties(List.of(" ")))
                .isInstanceOf(IllegalStateException.class);
    }

    @Test
    void refusesKeysShorterThan32Characters() {
        assertThatThrownBy(() -> new InternalApiProperties(List.of("short-key")))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("32");
    }
}
```

- [ ] **Step 2: 테스트를 실행해 실패하는지 확인**

Run: `cd ansimon-backend && ./gradlew test --tests "*ErrorCodeTest" --tests "*InternalApiPropertiesTest"`
Expected: 컴파일 실패 (`UNAUTHORIZED`, `InternalApiProperties` 없음)

- [ ] **Step 3: 최소 구현**

`ErrorCode.java`의 `CONFLICT(...)` 줄 아래에 다음을 추가한다.

```java
    UNAUTHORIZED("GLOBAL_UNAUTHORIZED", HttpStatus.UNAUTHORIZED, "Authentication is required."),
```

`InternalApiProperties.java`:

```java
package com.nmdw.ansimon.global.security;

import java.util.List;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.util.StringUtils;

/**
 * 서버끼리만 호출하는 {@code /internal/**} API가 받아들일 Bearer 키 목록을 설정에서 바인딩합니다.
 * 키를 목록으로 받아 새 키와 이전 키를 잠시 함께 허용하므로, 호출하는 서버의 키를 무중단으로 교체할 수 있습니다.
 * 키가 하나도 없거나 32자보다 짧으면 생성 시점에 실패시켜, 인증이 빠진 채 서버가 뜨는 일을 막습니다.
 */
@ConfigurationProperties(prefix = "ansimon.internal")
public record InternalApiProperties(
        List<String> apiKeys
) {

    private static final int MIN_KEY_LENGTH = 32;

    public InternalApiProperties {
        List<String> keys = apiKeys == null ? List.of() : apiKeys.stream()
                .filter(StringUtils::hasText)
                .map(String::trim)
                .toList();
        if (keys.isEmpty()) {
            throw new IllegalStateException("ansimon.internal.api-keys must contain at least one key");
        }
        if (keys.stream().anyMatch(key -> key.length() < MIN_KEY_LENGTH)) {
            throw new IllegalStateException("ansimon.internal.api-keys entries must be at least 32 characters");
        }
        apiKeys = keys;
    }
}
```

- [ ] **Step 4: 테스트를 실행해 통과하는지 확인**

Run: `cd ansimon-backend && ./gradlew test --tests "*ErrorCodeTest" --tests "*InternalApiPropertiesTest"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ansimon-backend/src/main/java/com/nmdw/ansimon/global/error/ErrorCode.java ansimon-backend/src/test/java/com/nmdw/ansimon/global/error/ErrorCodeTest.java ansimon-backend/src/main/java/com/nmdw/ansimon/global/security/InternalApiProperties.java ansimon-backend/src/test/java/com/nmdw/ansimon/global/security/InternalApiPropertiesTest.java
git commit -m "feat(security): add internal API key properties and UNAUTHORIZED error code"
```

---

### Task 2: 경로별 SecurityFilterChain과 내부 API 키 인증

security 의존성을 추가하면 기존 `@WebMvcTest`가 Boot 기본 보안 설정 때문에 401로 깨진다. 그래서 의존성, 체인, CORS 이전, 기존 테스트 수정을 하나의 태스크로 묶는다.

**Files:**
- Modify: `ansimon-backend/build.gradle`
- Create: `ansimon-backend/src/main/java/com/nmdw/ansimon/global/security/InternalApiKeyFilter.java`
- Create: `ansimon-backend/src/main/java/com/nmdw/ansimon/global/security/JsonAuthenticationEntryPoint.java`
- Create: `ansimon-backend/src/main/java/com/nmdw/ansimon/global/security/SecurityConfig.java`
- Modify: `ansimon-backend/src/main/java/com/nmdw/ansimon/global/config/CorsConfig.java` (전체 교체)
- Modify: `ansimon-backend/src/main/resources/application-local.yml`, `application-prod.yml`
- Modify: `ansimon-backend/src/test/resources/application.yml`
- Modify: `ansimon-backend/.env.example`
- Test: `ansimon-backend/src/test/java/com/nmdw/ansimon/global/security/InternalApiSecurityTest.java`
- Modify (테스트): `contact/api/ContactControllerTest.java`, `contact/api/CallObservationControllerTest.java`, `elderly/api/ElderlyControllerTest.java`, `global/converter/EnumCodeConverterFactoryTest.java`, `global/error/GlobalExceptionHandlerTest.java` (모두 `src/test/java/com/nmdw/ansimon/` 아래)

**Interfaces:**
- Consumes: Task 1의 `InternalApiProperties.apiKeys()`, `ErrorCode.UNAUTHORIZED`
- Produces:
  - `SecurityConfig`: `@Import(CorsConfig.class)`를 포함한다. 테스트는 `@Import(SecurityConfig.class)` 하나로 보안과 CORS를 모두 얻는다.
  - 빈 `CorsConfigurationSource corsConfigurationSource`: `/api/**`에만 등록된다.
  - 내부 인증 성공 시 principal은 `"internal-service"`, 권한은 `ROLE_INTERNAL`이다.

- [ ] **Step 1: 의존성과 테스트 키 설정 추가**

`build.gradle`의 `dependencies`에 다음 두 줄을 추가한다.

```groovy
    implementation 'org.springframework.boot:spring-boot-starter-security'
```
```groovy
    testImplementation 'org.springframework.boot:spring-boot-starter-security-test'
```

`spring-boot-starter-security-test`가 resolve되지 않으면 `testImplementation 'org.springframework.security:spring-security-test'`로 바꾼다. 확인 명령: `./gradlew dependencies --configuration testRuntimeClasspath | grep security`

`src/test/resources/application.yml` 끝에 다음을 추가한다. 이 파일은 main의 `application.yml`을 가리므로 여기에 꼭 넣어야 한다.

```yaml
ansimon:
  internal:
    api-keys:
      - test-internal-key-current-0000000000
      - test-internal-key-previous-000000000
```

- [ ] **Step 2: 실패하는 보안 테스트 작성**

`InternalApiSecurityTest.java`:

```java
package com.nmdw.ansimon.global.security;

import com.nmdw.ansimon.global.response.ApiResponse;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpHeaders;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.options;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(controllers = InternalApiSecurityTest.ProbeController.class)
@Import({InternalApiSecurityTest.ProbeController.class, SecurityConfig.class})
class InternalApiSecurityTest {

    private static final String CURRENT_KEY = "test-internal-key-current-0000000000";
    private static final String PREVIOUS_KEY = "test-internal-key-previous-000000000";
    private static final String ADMIN_ORIGIN = "http://localhost:5500";

    @Autowired
    private MockMvc mockMvc;

    @Test
    void rejectsInternalCallWithoutCredentials() throws Exception {
        mockMvc.perform(post("/internal/v1/probe"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.error.code").value("GLOBAL_UNAUTHORIZED"));
    }

    @Test
    void rejectsInternalCallWithWrongKey() throws Exception {
        mockMvc.perform(post("/internal/v1/probe")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer wrong-key-wrong-key-wrong-key-0000"))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void rejectsInternalCallWithNonBearerScheme() throws Exception {
        mockMvc.perform(post("/internal/v1/probe")
                        .header(HttpHeaders.AUTHORIZATION, "Basic " + CURRENT_KEY))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void acceptsBothCurrentAndPreviousKeysDuringRotation() throws Exception {
        mockMvc.perform(post("/internal/v1/probe")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + CURRENT_KEY))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data").value("internal"));
        mockMvc.perform(post("/internal/v1/probe")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + PREVIOUS_KEY))
                .andExpect(status().isOk());
    }

    @Test
    void leavesPublicApiOpenWithoutCredentials() throws Exception {
        mockMvc.perform(get("/api/v1/probe"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data").value("public"));
    }

    @Test
    void doesNotGrantCorsToBrowsersOnInternalApi() throws Exception {
        mockMvc.perform(options("/internal/v1/probe")
                        .header(HttpHeaders.ORIGIN, ADMIN_ORIGIN)
                        .header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, "POST"))
                .andExpect(header().doesNotExist(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN));
    }

    @Test
    void grantsCorsToTheAdminFrontendOnPublicApi() throws Exception {
        mockMvc.perform(options("/api/v1/probe")
                        .header(HttpHeaders.ORIGIN, ADMIN_ORIGIN)
                        .header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, "GET"))
                .andExpect(status().isOk())
                .andExpect(header().string(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN, ADMIN_ORIGIN));
    }

    @RestController
    static class ProbeController {
        @PostMapping("/internal/v1/probe") ApiResponse<String> internal() { return ApiResponse.success("internal"); }
        @GetMapping("/api/v1/probe") ApiResponse<String> publicApi() { return ApiResponse.success("public"); }
    }
}
```

- [ ] **Step 3: 테스트를 실행해 실패하는지 확인**

Run: `cd ansimon-backend && ./gradlew test --tests "*InternalApiSecurityTest"`
Expected: 컴파일 실패 (`SecurityConfig` 없음)

- [ ] **Step 4: 필터, 엔트리포인트, 체인 구현**

`InternalApiKeyFilter.java`:

```java
package com.nmdw.ansimon.global.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.HttpHeaders;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContext;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.List;

/**
 * {@code /internal/**} 요청의 {@code Authorization: Bearer} 키를 설정된 키 목록과 비교해 내부 서비스로 인증합니다.
 * 비교는 {@link MessageDigest#isEqual}로 하고 모든 키를 끝까지 비교해, 응답 시간으로 키를 추측할 수 없게 합니다.
 * 키가 맞지 않으면 아무것도 설정하지 않고 넘기며, 거절 응답은 체인의 인가 단계와 {@link JsonAuthenticationEntryPoint}가 만듭니다.
 * 빈으로 등록하면 서블릿 필터로 모든 경로에 자동 적용되므로 {@link SecurityConfig}에서만 생성합니다.
 */
public class InternalApiKeyFilter extends OncePerRequestFilter {

    private static final String BEARER_PREFIX = "Bearer ";
    private static final String PRINCIPAL = "internal-service";

    private final List<byte[]> acceptedKeys;

    public InternalApiKeyFilter(InternalApiProperties properties) {
        this.acceptedKeys = properties.apiKeys().stream()
                .map(key -> key.getBytes(StandardCharsets.UTF_8))
                .toList();
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        String header = request.getHeader(HttpHeaders.AUTHORIZATION);
        if (header != null && header.startsWith(BEARER_PREFIX)
                && matchesAnyKey(header.substring(BEARER_PREFIX.length()).trim())) {
            SecurityContext context = SecurityContextHolder.createEmptyContext();
            context.setAuthentication(UsernamePasswordAuthenticationToken.authenticated(
                    PRINCIPAL, null, List.of(new SimpleGrantedAuthority("ROLE_INTERNAL"))));
            SecurityContextHolder.setContext(context);
        }
        chain.doFilter(request, response);
    }

    private boolean matchesAnyKey(String presented) {
        byte[] candidate = presented.getBytes(StandardCharsets.UTF_8);
        boolean matched = false;
        for (byte[] key : acceptedKeys) {
            matched |= MessageDigest.isEqual(key, candidate);
        }
        return matched;
    }
}
```

`JsonAuthenticationEntryPoint.java`:

```java
package com.nmdw.ansimon.global.security;

import com.nmdw.ansimon.global.error.ErrorCode;
import com.nmdw.ansimon.global.response.ApiResponse;
import com.nmdw.ansimon.global.response.ErrorResponse;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.MediaType;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.web.AuthenticationEntryPoint;
import tools.jackson.databind.json.JsonMapper;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Map;

/**
 * 인증되지 않은 내부 API 요청에 401을 공통 {@link ApiResponse} 실패 형식으로 응답합니다.
 * 보안 필터는 컨트롤러 밖에서 동작해 {@code GlobalExceptionHandler}가 처리하지 못하므로, 같은 오류 계약을 여기서 직접 씁니다.
 * 키가 없는지 틀렸는지는 구분하지 않아, 호출자가 거절 사유로 키를 추측하지 못하게 합니다.
 */
public class JsonAuthenticationEntryPoint implements AuthenticationEntryPoint {

    private final JsonMapper jsonMapper;

    public JsonAuthenticationEntryPoint(JsonMapper jsonMapper) {
        this.jsonMapper = jsonMapper;
    }

    @Override
    public void commence(HttpServletRequest request, HttpServletResponse response, AuthenticationException exception)
            throws IOException {
        ErrorCode errorCode = ErrorCode.UNAUTHORIZED;
        response.setStatus(errorCode.status().value());
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        jsonMapper.writeValue(response.getOutputStream(), ApiResponse.failure(
                new ErrorResponse(errorCode.code(), errorCode.message(), Map.of())));
    }
}
```

`SecurityConfig.java`:

```java
package com.nmdw.ansimon.global.security;

import com.nmdw.ansimon.global.config.CorsConfig;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.core.annotation.Order;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.AnonymousAuthenticationFilter;
import org.springframework.web.cors.CorsConfigurationSource;
import tools.jackson.databind.json.JsonMapper;

/**
 * 외부 공개 API와 서버 간 내부 API에 서로 다른 보안 정책을 적용하는 두 개의 필터 체인을 정의합니다.
 * {@code /internal/**} 체인이 먼저 매칭되어 Bearer 키 인증을 강제하고 CORS를 꺼 브라우저 호출을 막으며,
 * 나머지 요청은 공개 체인이 받아 {@code /api/**}에만 관리자 프론트엔드 CORS를 허용합니다.
 */
@Configuration
@EnableWebSecurity
@EnableConfigurationProperties(InternalApiProperties.class)
@Import(CorsConfig.class)
public class SecurityConfig {

    @Bean
    @Order(1)
    public SecurityFilterChain internalApiSecurityFilterChain(
            HttpSecurity http, InternalApiProperties internalApiProperties, JsonMapper jsonMapper) throws Exception {
        return statelessApi(http)
                .securityMatcher("/internal/**")
                .cors(AbstractHttpConfigurer::disable)
                .addFilterBefore(new InternalApiKeyFilter(internalApiProperties), AnonymousAuthenticationFilter.class)
                .exceptionHandling(exceptions -> exceptions
                        .authenticationEntryPoint(new JsonAuthenticationEntryPoint(jsonMapper)))
                .authorizeHttpRequests(authorize -> authorize.anyRequest().hasRole("INTERNAL"))
                .build();
    }

    @Bean
    @Order(2)
    public SecurityFilterChain publicApiSecurityFilterChain(
            HttpSecurity http, CorsConfigurationSource corsConfigurationSource) throws Exception {
        return statelessApi(http)
                .cors(cors -> cors.configurationSource(corsConfigurationSource))
                .authorizeHttpRequests(authorize -> authorize.anyRequest().permitAll())
                .build();
    }

    private static HttpSecurity statelessApi(HttpSecurity http) throws Exception {
        return http
                .csrf(AbstractHttpConfigurer::disable)
                .httpBasic(AbstractHttpConfigurer::disable)
                .formLogin(AbstractHttpConfigurer::disable)
                .logout(AbstractHttpConfigurer::disable)
                .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS));
    }
}
```

`CorsConfig.java` 전체를 교체한다. MVC의 `/**` 매핑을 없애고, 보안 체인이 쓰는 `/api/**` 전용 소스로 바꾼다.

```java
package com.nmdw.ansimon.global.config;

import java.util.List;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

/**
 * 관리자 프론트엔드가 다른 출처에서 외부 공개 API({@code /api/**})를 호출할 수 있도록 CORS 정책을 한곳에서 정의합니다.
 * 허용 출처는 {@link CorsProperties}가 설정에서 읽어오며, 이 소스는 공개 보안 체인에만 연결되어 {@code /internal/**}에는 적용되지 않습니다.
 * 인증 쿠키를 쓰지 않으므로 자격 증명 전송은 허용하지 않습니다.
 */
@Configuration
@EnableConfigurationProperties(CorsProperties.class)
public class CorsConfig {

    @Bean
    public CorsConfigurationSource corsConfigurationSource(CorsProperties corsProperties) {
        CorsConfiguration configuration = new CorsConfiguration();
        configuration.setAllowedOrigins(List.copyOf(corsProperties.getAllowedOrigins()));
        configuration.setAllowedMethods(List.of("GET", "POST", "PATCH", "DELETE", "OPTIONS"));
        configuration.setAllowedHeaders(List.of("*"));
        configuration.setAllowCredentials(false);
        configuration.setMaxAge(3600L);

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/api/**", configuration);
        return source;
    }
}
```

- [ ] **Step 5: 보안 테스트가 통과하는지 확인**

Run: `cd ansimon-backend && ./gradlew test --tests "*InternalApiSecurityTest"`
Expected: 7개 PASS

`rejectsInternalCallWithoutCredentials`가 200으로 실패하면 MockMvc에 security 필터가 붙지 않은 것이다. Step 1의 security-test 의존성이 resolve됐는지 다시 확인한다.

- [ ] **Step 6: 기존 WebMvc 테스트 수정**

전체 테스트를 먼저 돌려 깨지는 지점을 확인한다.

Run: `cd ansimon-backend && ./gradlew test`
Expected: 기존 `@WebMvcTest` 5개 클래스가 401로 FAIL (Boot 기본 보안 설정이 적용된 상태)

아래 5개 파일의 `@Import`에 `SecurityConfig.class`를 추가하고, `import com.nmdw.ansimon.global.security.SecurityConfig;`도 추가한다.

| 파일 | 변경 전 | 변경 후 |
|---|---|---|
| `contact/api/ContactControllerTest.java` | `@Import(GlobalExceptionHandler.class)` | `@Import({GlobalExceptionHandler.class, SecurityConfig.class})` |
| `contact/api/CallObservationControllerTest.java` | `@Import(GlobalExceptionHandler.class)` | `@Import({GlobalExceptionHandler.class, SecurityConfig.class})` |
| `elderly/api/ElderlyControllerTest.java` | `@Import(GlobalExceptionHandler.class)` | `@Import({GlobalExceptionHandler.class, SecurityConfig.class})` |
| `global/converter/EnumCodeConverterFactoryTest.java` | `@Import(EnumCodeConverterFactoryTest.TestController.class)` | `@Import({EnumCodeConverterFactoryTest.TestController.class, SecurityConfig.class})` |
| `global/error/GlobalExceptionHandlerTest.java` | `@Import(GlobalExceptionHandlerTest.TestController.class)` | `@Import({GlobalExceptionHandlerTest.TestController.class, SecurityConfig.class})` |

`ContactControllerTest.java`는 internal 엔드포인트를 호출하므로 키 헤더도 붙인다. 클래스 필드 위에 상수를 추가한다.

```java
    private static final String INTERNAL_AUTHORIZATION = "Bearer test-internal-key-current-0000000000";
```

`mockMvc.perform(post("/internal/v1/contact/results")` 4곳(54, 67, 77, 91행 부근) 모두에서 바로 다음 줄에 다음을 넣는다.

```java
                        .header("Authorization", INTERNAL_AUTHORIZATION)
```

예시:

```java
        mockMvc.perform(post("/internal/v1/contact/results")
                        .header("Authorization", INTERNAL_AUTHORIZATION)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(ANSWERED_OUTCOME))
```

- [ ] **Step 7: 실행 환경 설정**

`application-local.yml`의 `ansimon:` 블록 맨 아래(`connection:` 블록 뒤, 같은 들여쓰기)에 다음을 추가한다.

```yaml
  internal:
    # 연결 서버의 ANSIMON_BACKEND_TOKEN 과 같은 값. 쉼표로 여러 개를 주면 키 교체 중 이전 키도 받는다.
    api-keys: ${INTERNAL_API_KEYS:local-dev-internal-key-change-me-0000}
```

`application-prod.yml`의 `ansimon:` 블록 맨 아래에 다음을 추가한다. 기본값이 없으므로 env가 빠지면 기동에 실패한다.

```yaml
  internal:
    api-keys: ${INTERNAL_API_KEYS}
```

`application-prod.yml`의 `ansimon.external.connection.api-key`는 `${CONNECTION_API_KEY:}`에서 `${CONNECTION_API_KEY}`로 바꾼다. 연결 서버가 이제 키 없는 호출을 거절하기 때문이다.

`ansimon-backend/.env.example`의 `CONNECTION_API_KEY=` 줄 아래에 다음을 추가한다.

```
# /internal/** 호출을 허용할 키 (32자 이상, openssl rand -hex 32). 연결 서버의 ANSIMON_BACKEND_TOKEN 과 같은 값.
# 교체할 때는 "새키,이전키" 로 잠시 둘 다 넣었다가, 연결 서버를 새 키로 바꾼 뒤 이전 키를 지운다.
INTERNAL_API_KEYS=
```

- [ ] **Step 8: 전체 테스트 통과 확인**

Run: `cd ansimon-backend && ./gradlew test`
Expected: 전체 PASS. `AnsimonApplicationTests`도 test yml의 키로 컨텍스트가 정상 기동된다.

- [ ] **Step 9: Commit**

```bash
git add ansimon-backend/build.gradle ansimon-backend/.env.example ansimon-backend/src
git commit -m "feat(security): enforce API key auth on /internal/** with path-specific security chains"
```

---

### Task 3: 연결 서버 인바운드 Bearer 검증

**Files:**
- Modify: `ansimon-connection/server.py` (import 영역, `app()` 함수)
- Modify: `ansimon-connection/test_connection.py` (`if __name__ == "__main__":` 바로 위에 테스트 추가)
- Modify: `ansimon-connection/.env.example`

**Interfaces:**
- Consumes: 환경변수 `CONNECTION_API_KEY`(`/v1/**`용), `ANSIMON_BACKEND_TOKEN`(`/internal/**`용)
- Produces:
  - `server.require_bearer`: aiohttp 미들웨어. `/health`는 공개한다.
  - 키 미설정 시 503 `AUTH_NOT_CONFIGURED`, 불일치 시 401 `UNAUTHORIZED`

- [ ] **Step 1: 실패하는 테스트 작성**

`test_connection.py`의 `if __name__ == "__main__":` 바로 위에 다음을 추가한다. 환경변수를 통째로 저장했다가 복원한다. `import server`가 `.env`를 읽어 환경을 바꾸기 때문에, 다른 테스트를 오염시키지 않도록 하는 장치다.

```python
@contextlib.contextmanager
def env(**values):
    saved = dict(os.environ)
    for k, v in values.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(saved)


async def _auth_client():
    from aiohttp.test_utils import TestClient, TestServer
    import server
    return TestClient(TestServer(server.app()))


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@at("연결 서버: 백엔드가 부르는 /v1/** 는 CONNECTION_API_KEY 로만 통과한다")
async def _():
    with env(CONNECTION_API_KEY="conn-key-0000000000000000000000000000",
             ANSIMON_BACKEND_TOKEN="callback-key-000000000000000000000000"):
        async with await _auth_client() as c:
            assert (await c.get("/health")).status == 200
            assert (await c.post("/v1/care-runs", data="x")).status == 401
            assert (await c.post("/v1/care-runs", data="x", headers=bearer("wrong"))).status == 401
            r = await c.post("/v1/care-runs", data="x",
                             headers={"Authorization": "Basic conn-key-0000000000000000000000000000"})
            assert r.status == 401
            r = await c.post("/v1/care-runs", data="x",
                             headers=bearer("callback-key-000000000000000000000000"))
            assert r.status == 401, "콜백 토큰으로는 /v1 을 못 부른다"
            # 인증은 통과하고 본문 검증에서 막힌다 → 전화를 걸지 않는다
            r = await c.post("/v1/care-runs", data="x",
                             headers=bearer("conn-key-0000000000000000000000000000"))
            assert r.status == 400, r.status
            assert (await r.json())["error"]["code"] == "BAD_REQUEST"


@at("연결 서버: 전화 모듈 콜백 /internal/** 은 ANSIMON_BACKEND_TOKEN 으로만 통과한다")
async def _():
    with env(CONNECTION_API_KEY="conn-key-0000000000000000000000000000",
             ANSIMON_BACKEND_TOKEN="callback-key-000000000000000000000000"):
        async with await _auth_client() as c:
            path = "/internal/v1/contact-jobs/1/observation"
            r = await c.post(path, data="x")
            assert r.status == 401
            assert (await r.json())["error"]["code"] == "UNAUTHORIZED"
            r = await c.post(path, data="x", headers=bearer("conn-key-0000000000000000000000000000"))
            assert r.status == 401
            r = await c.post(path, data="x", headers=bearer("callback-key-000000000000000000000000"))
            assert r.status == 400, r.status


@at("연결 서버: 키가 설정되지 않으면 열어두지 않고 503 으로 막는다")
async def _():
    with env(CONNECTION_API_KEY=None, ANSIMON_BACKEND_TOKEN=None):
        async with await _auth_client() as c:
            # server import 시 load_dotenv 가 키를 다시 채울 수 있으므로 import 후에 지운다
            os.environ.pop("CONNECTION_API_KEY", None)
            os.environ.pop("ANSIMON_BACKEND_TOKEN", None)
            r = await c.post("/v1/care-runs", data="x", headers=bearer("anything"))
            assert r.status == 503
            assert (await r.json())["error"]["code"] == "AUTH_NOT_CONFIGURED"
            assert (await c.get("/health")).status == 200
```

- [ ] **Step 2: 테스트를 실행해 실패하는지 확인**

Run: `cd ansimon-connection && python test_connection.py`
Expected: 새 테스트 3개가 "실패"로 출력되고 exit 1. 인증이 없어서 401 대신 400이 나온다.

- [ ] **Step 3: 미들웨어 구현**

`server.py`의 `import asyncio` 아래에 `import hmac`를 추가한다. `PORT = ...` 줄 아래에는 다음을 추가한다.

```python
# 인증 없이 열어 두는 경로. 나머지는 전부 Bearer 키가 맞아야 한다.
PUBLIC_PATHS = {"/health"}
```

`fail()` 함수 정의 바로 아래에 다음을 추가한다.

```python
def _expected_token(path: str) -> str:
    """경로별로 받아들일 키. 요청마다 읽어 키 교체가 재시작 없이 반영되게 한다.

    /internal/** 은 전화 모듈 콜백이다. 전화 모듈은 콜백 주소가 백엔드든 여기든
    ANSIMON_BACKEND_TOKEN 을 붙이므로 같은 키로 검증한다. /v1/** 은 백엔드가
    CONNECTION_API_KEY 로 부른다.
    """
    name = "ANSIMON_BACKEND_TOKEN" if path.startswith("/internal/") else "CONNECTION_API_KEY"
    return (os.getenv(name) or "").strip()


@web.middleware
async def require_bearer(request: web.Request, handler):
    if request.path in PUBLIC_PATHS:
        return await handler(request)
    expected = _expected_token(request.path)
    if not expected:
        # 키를 안 넣었다고 문을 열어두지 않는다
        return fail("AUTH_NOT_CONFIGURED", "서버 인증 키가 설정되지 않았습니다.", 503)
    header = request.headers.get("Authorization", "")
    presented = header[len("Bearer "):].strip() if header.startswith("Bearer ") else ""
    # compare_digest: 응답 시간으로 키를 한 글자씩 맞혀보는 공격을 막는다
    if not presented or not hmac.compare_digest(presented.encode(), expected.encode()):
        return fail("UNAUTHORIZED", "인증이 필요합니다.", 401)
    return await handler(request)
```

`app()`의 `a = web.Application()`을 다음으로 바꾼다.

```python
    a = web.Application(middlewares=[require_bearer])
```

모듈 docstring의 경로 목록 아래에 다음 한 줄을 추가한다.

```
인증: /health 외에는 Authorization: Bearer 필수 — /v1/** 은 CONNECTION_API_KEY, /internal/** 은 ANSIMON_BACKEND_TOKEN.
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd ansimon-connection && python test_connection.py`
Expected: 전부 통과, exit 0

- [ ] **Step 5: .env.example 정리**

`ansimon-connection/.env.example`의 `ANSIMON_BACKEND_TOKEN=` 줄 위에 다음 주석을 넣는다.

```
# 백엔드 /internal/** 와 이 서버 /internal/** (전화 모듈 콜백) 이 함께 쓰는 콜백 토큰.
# 백엔드 INTERNAL_API_KEYS 에 같은 값이 있어야 한다. 32자 이상 (openssl rand -hex 32).
```

`BACKEND_TIMEOUT_SEC=15` 줄 아래에는 다음을 추가한다.

```
# 백엔드가 이 서버 /v1/** 를 부를 때 쓰는 키. 백엔드 CONNECTION_API_KEY 와 같은 값.
CONNECTION_API_KEY=
```

- [ ] **Step 6: Commit**

```bash
git add ansimon-connection/server.py ansimon-connection/test_connection.py ansimon-connection/.env.example
git commit -m "feat(connection): require bearer auth on /v1 and /internal routes"
```

---

### Task 4: 연결 서버 → 백엔드 전송 시 토큰 필수화

지금은 토큰이 비어 있으면 헤더 없이 보낸다. 이제 백엔드가 401로 막으므로, 보내기 전에 명확한 오류를 낸다.

**Files:**
- Modify: `ansimon-connection/backend_client.py:36-37`
- Modify: `ansimon-connection/test_connection.py` (Task 3 테스트 아래에 추가)

**Interfaces:**
- Consumes: Task 3의 `env()` 헬퍼
- Produces: `backend_client.post_result()`는 `ANSIMON_BACKEND_BASE_URL`이 있고 토큰이 없으면 네트워크 호출 없이 `RuntimeError`를 던진다.

- [ ] **Step 1: 실패하는 테스트 작성**

```python
@at("백엔드 주소는 있는데 토큰이 없으면 보내지 않고 예외를 올린다")
async def _():
    # 127.0.0.1:9 (discard) — 실수로 전송을 시도해도 즉시 연결 거부로 끝난다
    with env(ANSIMON_BACKEND_BASE_URL="http://127.0.0.1:9", ANSIMON_BACKEND_TOKEN=None):
        try:
            await backend_client.post_result({"x": 1})
        except RuntimeError as e:
            assert "ANSIMON_BACKEND_TOKEN" in str(e), e
        else:
            raise AssertionError("토큰 없이 전송을 시도했다")
```

- [ ] **Step 2: 실패 확인**

Run: `cd ansimon-connection && python test_connection.py`
Expected: 새 테스트가 "실패"로 출력된다. `ClientConnectorError` 같은 연결 오류가 나며, 전송을 시도했다는 뜻이다.

- [ ] **Step 3: 구현**

`backend_client.py`에서 다음 부분을

```python
    if token := (os.getenv("ANSIMON_BACKEND_TOKEN") or "").strip():
        headers["Authorization"] = f"Bearer {token}"
```

아래로 바꾼다.

```python
    token = (os.getenv("ANSIMON_BACKEND_TOKEN") or "").strip()
    if not token:
        # 백엔드 /internal/** 은 키 없는 요청을 401 로 막는다. 보내기 전에 원인을 분명히 알린다.
        raise RuntimeError("ANSIMON_BACKEND_TOKEN 이 비어 있어 백엔드로 전송할 수 없습니다.")
    headers["Authorization"] = f"Bearer {token}"
```

- [ ] **Step 4: 통과 확인**

Run: `cd ansimon-connection && python test_connection.py`
Expected: 전부 통과, exit 0. 기존 "백엔드 주소가 없으면 전송하지 않고 본문만 출력한다" 테스트도 그대로 통과한다.

- [ ] **Step 5: Commit**

```bash
git add ansimon-connection/backend_client.py ansimon-connection/test_connection.py
git commit -m "feat(connection): refuse to post results to backend without a token"
```

---

### Task 5: 통합 확인과 배포 환경변수 반영

코드 변경은 없다. 로컬 수동 검증과 배포 체크리스트로 구성된다.

- [ ] **Step 1: 로컬 기동 후 수동 확인**

키를 생성한다.

```bash
openssl rand -hex 32
```

생성한 값을 `ansimon-backend`의 `INTERNAL_API_KEYS`와 `ansimon-connection/.env`의 `ANSIMON_BACKEND_TOKEN`에 같은 값으로 넣는다. 또 하나 생성한 값은 양쪽 `CONNECTION_API_KEY`에 같은 값으로 넣는다. 그 다음 백엔드(local 프로필)를 기동한다.

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8080/internal/v1/risk/forecast
```

Expected: `401`

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/actuator/health
```

Expected: `200`

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:7000/v1/care-runs -d x
```

Expected: `401` (연결 서버 기동 상태)

관리자 프론트(`:5500`)에서 대시보드 화면이 기존처럼 뜨는지도 확인한다. CORS가 `/api/**`로 좁아졌으므로 프론트가 `/api/**` 밖을 호출하고 있다면 여기서 드러난다.

- [ ] **Step 2: 배포 환경변수 체크리스트 (Railway, 수동)**

- 백엔드: `INTERNAL_API_KEYS`(신규), `CONNECTION_API_KEY`(prod 필수화됨)
- 연결 서버: `ANSIMON_BACKEND_TOKEN`(값 = 백엔드 `INTERNAL_API_KEYS` 중 하나), `CONNECTION_API_KEY`
- 전화 모듈(est_hackathon): `ANSIMON_BACKEND_TOKEN`(같은 값)
- 배포 순서:
  1. 환경변수를 먼저 등록한다.
  2. 연결 서버를 배포한다.
  3. 백엔드를 배포한다.
  - 백엔드를 먼저 배포하면 키 없는 연결 서버의 결과 전송이 401로 버려진다.

---

## Self-Review 결과

- 범위 대응:
  - 1단계(Spring Security, 경로별 체인, 상수 시간 비교, 키 목록 교체, fail-fast, CORS 분리, 토큰 필수화)는 Task 1, 2, 4에서 구현한다.
  - 2단계(backend → connection 검증)는 Task 3에서 구현한다.
- 이름 일관성:
  - `InternalApiProperties.apiKeys()`, `SecurityConfig`, `ErrorCode.UNAUTHORIZED`/`GLOBAL_UNAUTHORIZED`
  - 테스트 키 `test-internal-key-current-0000000000`(36자), `test-internal-key-previous-000000000`(36자)
  - 위 이름과 값은 Task 1, 2의 테스트와 yml에서 동일하게 쓴다.
- 범위 밖(의도적 제외): `/api/v1/**` 관리자 인증, HMAC 서명과 재전송 방어(3단계), Railway private networking(4단계), swagger 보호.
