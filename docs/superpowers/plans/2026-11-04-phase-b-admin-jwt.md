# Phase B — 관리자 로그인 + JWT Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/api/**`(어르신 개인정보 조회·수정, 실제 전화 실행)를 로그인한 관리자만 쓸 수 있게 한다.

**Architecture:**
- 백엔드는 `admin_account` 테이블과 `POST /api/v1/auth/login`을 추가한다. 로그인에 성공하면 HS256 JWT를 발급한다.
- `/api/**` 체인은 Spring Security OAuth2 Resource Server로 토큰을 검증한다. 1차의 `/internal/**` 체인(@Order 1)은 그대로 둔다.
- 순서: `/internal/**`(내부 키) → `/api/**`(JWT) → 나머지(공개: actuator health, swagger).
- 프론트는 `assets/api.js`에서 토큰을 `sessionStorage`에 두고 모든 요청에 붙인다. 401을 받으면 `login.html`로 보낸다.

**Tech Stack:** Spring Boot 4.1, Spring Security 7 (oauth2-resource-server, Nimbus JOSE), Flyway(MySQL / 테스트는 H2 MySQL 모드), 정적 HTML/JS

**Spec:** `docs/superpowers/plans/2026-11-04-security-roadmap.md` §Phase B, §실행 순서와 이유

## Global Constraints

- **JWT**
  - 알고리즘은 `HS256`, 비밀키는 `ansimon.auth.jwt-secret`이다(env `ANSIMON_JWT_SECRET`). UTF-8로 **32바이트 이상**이어야 하고, 아니면 기동에 실패한다.
  - 클레임: `iss=ansimon-backend`, `sub=<loginId>`, `iat`, `exp`, `scope=admin`.
  - 유효기간은 `ansimon.auth.access-token-ttl`이고 기본값은 `1h`다. 리프레시 토큰은 없다.
- **인가:** `/api/**`는 `SCOPE_admin` 권한이 필요하다. 다만 `POST /api/v1/auth/login`과 모든 `OPTIONS`(CORS preflight)는 예외다.
- **오류 응답**
  - 인증 실패는 기존 `JsonAuthenticationEntryPoint`가 처리한다(401 `GLOBAL_UNAUTHORIZED`).
  - 아이디·비밀번호가 틀리면 401 `AUTH_INVALID_CREDENTIALS`이고 메시지는 `"Login ID or password is incorrect."`다. 아이디가 없을 때와 비밀번호가 틀릴 때 응답이 **완전히 같아야** 한다.
- **비밀번호**
  - `PasswordEncoderFactories.createDelegatingPasswordEncoder()`(bcrypt)로 저장한다.
  - 없는 아이디로 로그인해도 해시 비교를 한 번 수행해, 응답 시간이 비슷하게 나오게 한다.
- **계정 생성:** 가입 API는 없다. `ADMIN_BOOTSTRAP_LOGIN_ID`·`ADMIN_BOOTSTRAP_PASSWORD`가 둘 다 있고 `admin_account`가 비어 있을 때만 첫 계정을 만든다. 비밀번호가 12자 미만이면 기동에 실패한다.
- **로그 금지:** 비밀번호와 토큰은 로그에 남기지 않는다. `LoginRequest.toString()`은 비밀번호를 가린다.
- **코드 스타일**
  - 기존 관례를 따른다: 패키지 `com.nmdw.ansimon.<도메인>.{api,application,domain,dto,infra}`, 컨트롤러 반환 `ApiResponse<T>`, 예외 `BusinessException(ErrorCode)`, 엔티티는 `BaseTimeEntity` 상속과 Lombok.
  - 모든 public 클래스에 2~3줄 한국어 Javadoc을 단다. 기존 파일과 같은 톤이다.
- **명령어**
  - 테스트: `cd ansimon-backend && export JAVA_TOOL_OPTIONS="-Djdk.net.unixdomain.tmpdir=C:/gtmp" && ./gradlew test`. 기준선은 113개 통과다.
  - 이 머신은 `JAVA_TOOL_OPTIONS` 없이는 Gradle 루프백 연결에 실패한다.
- **테스트 범위:** 단순 DTO, record, 설정 클래스에는 따로 TDD 테스트를 쓰지 않는다. 동작이 있는 클래스만 테스트한다.

---

## File Structure

| 파일 | 책임 |
|---|---|
| `build.gradle` | 리소스 서버 스타터 추가 |
| `src/main/resources/db/migration/mysql/V4__create_admin_account.sql` | 관리자 계정 테이블 |
| `global/security/AuthProperties.java` | `ansimon.auth.*` 바인딩 + 비밀키 검증 |
| `global/security/AdminBootstrapProperties.java` | `ansimon.auth.bootstrap-admin.*` 바인딩 |
| `global/security/JwtConfig.java` | `JwtEncoder`/`JwtDecoder`/`PasswordEncoder` 빈 |
| `global/security/SecurityConfig.java` | `/api/**` JWT 체인 추가, 공개 체인 축소 |
| `global/error/ErrorCode.java` | `INVALID_CREDENTIALS` |
| `auth/domain/AdminAccount.java` | 엔티티 |
| `auth/infra/AdminAccountRepository.java` | `findByLoginId` |
| `auth/application/AccessTokenIssuer.java` | JWT 발급 |
| `auth/application/AuthService.java` | 로그인(시간차 방어 포함) |
| `auth/application/AdminBootstrap.java` | 첫 계정 생성(`ApplicationRunner`) |
| `auth/dto/LoginRequest.java`, `auth/dto/LoginResponse.java` | 요청/응답 |
| `auth/api/AuthController.java` | `POST /api/v1/auth/login` |
| `application*.yml`, `.env.example` | 설정 |
| `ansimon_front_end/login.html`, `assets/api.js`, `index.html`, `elderly-detail.html`, `README.md` | 프론트 |

(경로 앞부분 `ansimon-backend/src/main/java/com/nmdw/ansimon/`는 생략했다. 테스트는 `src/test/java/com/nmdw/ansimon/` 아래 같은 패키지에 둔다.)

---

### Task 1: 설정·키 빈과 `/api/**` JWT 체인

이 작업이 끝나면 `/api/**`가 모두 401이 된다. 기존 컨트롤러 테스트도 같은 작업에서 고쳐야 빌드가 초록이 된다.

**Files:**
- Modify: `ansimon-backend/build.gradle`
- Create: `global/security/AuthProperties.java`, `global/security/AdminBootstrapProperties.java`, `global/security/JwtConfig.java`
- Modify: `global/security/SecurityConfig.java`
- Modify: `src/test/resources/application.yml`, `src/main/resources/application-local.yml`, `src/main/resources/application-prod.yml`, `ansimon-backend/.env.example`
- Create test: `global/security/AdminApiSecurityTest.java`, `global/security/AuthPropertiesTest.java`
- Modify tests: `global/security/InternalApiSecurityTest.java`, `elderly/api/ElderlyControllerTest.java`, `contact/api/CallObservationControllerTest.java`, `guidance/api/GuidanceControllerTest.java`

**Interfaces:**
- Produces:
  - `record AuthProperties(String jwtSecret, Duration accessTokenTtl, String issuer)`. 생성 시 검증하며, 기본값은 `accessTokenTtl=1h`, `issuer="ansimon-backend"`이다.
  - `record AdminBootstrapProperties(String loginId, String password)`
  - 빈: `JwtEncoder`, `JwtDecoder`(HS256, issuer 검증), `PasswordEncoder`(delegating)
  - JWT 권한은 `scope=admin` 클레임에서 오며 `SCOPE_admin`이 된다.

- [ ] **Step 1: 의존성 추가**

`build.gradle`의 `implementation 'org.springframework.boot:spring-boot-starter-security'` 아래에 추가:

```groovy
    implementation 'org.springframework.boot:spring-boot-starter-security-oauth2-resource-server'
```

Run: `./gradlew dependencies --configuration runtimeClasspath | grep -i "oauth2-jose\|nimbus"`
Expected: `spring-security-oauth2-jose`와 `nimbus-jose-jwt`가 보인다.

Spring Boot 4에서 스타터 이름이 바뀌었다. 이 이름으로 해석이 실패하면 예전 이름 `spring-boot-starter-oauth2-resource-server`로 바꾸고, 어느 쪽을 썼는지 보고서에 적는다.

- [ ] **Step 2: Write the failing tests**

`src/test/resources/application.yml`의 `ansimon:` 아래(`internal:`과 같은 깊이)에 추가:

```yaml
  auth:
    jwt-secret: test-jwt-secret-0000000000000000000000
    access-token-ttl: 1h
```

Create `src/test/java/com/nmdw/ansimon/global/security/AuthPropertiesTest.java`:

```java
package com.nmdw.ansimon.global.security;

import org.junit.jupiter.api.Test;

import java.time.Duration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class AuthPropertiesTest {

    private static final String SECRET = "test-jwt-secret-0000000000000000000000";

    @Test
    void rejectsMissingOrShortSecret() {
        assertThatThrownBy(() -> new AuthProperties(null, null, null))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("jwt-secret");
        assertThatThrownBy(() -> new AuthProperties("short-secret", null, null))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("32 bytes");
    }

    @Test
    void appliesDefaultsForTtlAndIssuer() {
        AuthProperties properties = new AuthProperties("  " + SECRET + "  ", null, " ");

        assertThat(properties.jwtSecret()).isEqualTo(SECRET);
        assertThat(properties.accessTokenTtl()).isEqualTo(Duration.ofHours(1));
        assertThat(properties.issuer()).isEqualTo("ansimon-backend");
    }

    @Test
    void rejectsNonPositiveTtl() {
        assertThatThrownBy(() -> new AuthProperties(SECRET, Duration.ZERO, null))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("access-token-ttl");
    }
}
```

Create `src/test/java/com/nmdw/ansimon/global/security/AdminApiSecurityTest.java`:

```java
package com.nmdw.ansimon.global.security;

import com.nmdw.ansimon.global.response.ApiResponse;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpHeaders;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.JwsHeader;
import org.springframework.security.oauth2.jwt.JwtClaimsSet;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.JwtEncoderParameters;
import org.springframework.security.oauth2.jwt.NimbusJwtEncoder;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;

import com.nimbusds.jose.jwk.source.ImmutableSecret;

import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.time.Instant;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.options;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(controllers = AdminApiSecurityTest.ProbeController.class)
@Import({AdminApiSecurityTest.ProbeController.class, SecurityConfig.class})
class AdminApiSecurityTest {

    private static final String ADMIN_ORIGIN = "http://localhost:5500";
    private static final String INTERNAL_KEY = "test-internal-key-current-0000000000";

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private JwtEncoder jwtEncoder;

    @Test
    void rejectsAdminApiWithoutToken() throws Exception {
        mockMvc.perform(get("/api/v1/probe"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.error.code").value("GLOBAL_UNAUTHORIZED"));
    }

    @Test
    void rejectsMalformedToken() throws Exception {
        mockMvc.perform(get("/api/v1/probe").header(HttpHeaders.AUTHORIZATION, "Bearer not-a-jwt"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.error.code").value("GLOBAL_UNAUTHORIZED"));
    }

    @Test
    void acceptsValidAdminToken() throws Exception {
        String token = token(jwtEncoder, "ansimon-backend", Instant.now().plusSeconds(600));

        mockMvc.perform(get("/api/v1/probe").header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data").value("admin"));
    }

    @Test
    void rejectsExpiredToken() throws Exception {
        String token = token(jwtEncoder, "ansimon-backend", Instant.now().minusSeconds(600));

        mockMvc.perform(get("/api/v1/probe").header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void rejectsTokenSignedWithAnotherSecret() throws Exception {
        JwtEncoder foreign = new NimbusJwtEncoder(new ImmutableSecret<>(new SecretKeySpec(
                "another-secret-0000000000000000000000".getBytes(StandardCharsets.UTF_8), "HmacSHA256")));
        String token = token(foreign, "ansimon-backend", Instant.now().plusSeconds(600));

        mockMvc.perform(get("/api/v1/probe").header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void rejectsTokenFromAnotherIssuer() throws Exception {
        String token = token(jwtEncoder, "someone-else", Instant.now().plusSeconds(600));

        mockMvc.perform(get("/api/v1/probe").header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void leavesLoginOpenWithoutToken() throws Exception {
        mockMvc.perform(post("/api/v1/auth/login"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data").value("login"));
    }

    @Test
    void grantsCorsPreflightToTheAdminFrontendWithoutToken() throws Exception {
        mockMvc.perform(options("/api/v1/probe")
                        .header(HttpHeaders.ORIGIN, ADMIN_ORIGIN)
                        .header(HttpHeaders.ACCESS_CONTROL_REQUEST_METHOD, "GET")
                        .header(HttpHeaders.ACCESS_CONTROL_REQUEST_HEADERS, "authorization"))
                .andExpect(status().isOk())
                .andExpect(header().string(HttpHeaders.ACCESS_CONTROL_ALLOW_ORIGIN, ADMIN_ORIGIN));
    }

    @Test
    void adminTokenDoesNotOpenInternalApi() throws Exception {
        String token = token(jwtEncoder, "ansimon-backend", Instant.now().plusSeconds(600));

        mockMvc.perform(post("/internal/v1/probe").header(HttpHeaders.AUTHORIZATION, "Bearer " + token))
                .andExpect(status().isUnauthorized());
        mockMvc.perform(post("/internal/v1/probe").header(HttpHeaders.AUTHORIZATION, "Bearer " + INTERNAL_KEY))
                .andExpect(status().isOk());
    }

    @Test
    void internalKeyDoesNotOpenAdminApi() throws Exception {
        mockMvc.perform(get("/api/v1/probe").header(HttpHeaders.AUTHORIZATION, "Bearer " + INTERNAL_KEY))
                .andExpect(status().isUnauthorized());
    }

    @Test
    void leavesNonApiPathsPublic() throws Exception {
        mockMvc.perform(get("/probe-public"))
                .andExpect(status().isOk());
    }

    private static String token(JwtEncoder encoder, String issuer, Instant expiresAt) {
        JwtClaimsSet claims = JwtClaimsSet.builder()
                .issuer(issuer)
                .subject("admin")
                .issuedAt(expiresAt.minusSeconds(3600))
                .expiresAt(expiresAt)
                .claim("scope", "admin")
                .build();
        return encoder.encode(JwtEncoderParameters.from(JwsHeader.with(MacAlgorithm.HS256).build(), claims))
                .getTokenValue();
    }

    @RestController
    static class ProbeController {
        @GetMapping("/api/v1/probe") ApiResponse<String> admin() { return ApiResponse.success("admin"); }
        @PostMapping("/api/v1/auth/login") ApiResponse<String> login() { return ApiResponse.success("login"); }
        @PostMapping("/internal/v1/probe") ApiResponse<String> internal() { return ApiResponse.success("internal"); }
        @GetMapping("/probe-public") ApiResponse<String> open() { return ApiResponse.success("public"); }
    }
}
```

`InternalApiSecurityTest.java`도 고친다. 1차의 "`/api`는 열려 있다"는 전제가 이제 틀렸고, 같은 내용은 `AdminApiSecurityTest`가 다룬다.
- `leavesPublicApiOpenWithoutCredentials()` 메서드를 지운다.
- `grantsCorsToTheAdminFrontendOnPublicApi()` 메서드를 지운다.
- `ProbeController`에서 `@GetMapping("/api/v1/probe")` 줄을 지운다.
- 쓰지 않게 된 `get` import를 지운다.

- [ ] **Step 3: Run tests to verify they fail**

Run: `./gradlew test --tests "com.nmdw.ansimon.global.security.*"`
Expected: 컴파일 실패. `AuthProperties`와 `JwtEncoder` 빈이 없다.

- [ ] **Step 4: Implement properties**

Create `global/security/AuthProperties.java`:

```java
package com.nmdw.ansimon.global.security;

import java.nio.charset.StandardCharsets;
import java.time.Duration;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.util.StringUtils;

/**
 * 관리자 콘솔 JWT의 서명 비밀키, 유효기간, 발급자를 설정에서 바인딩합니다.
 * HS256은 키 길이가 곧 강도이므로 32바이트 미만이면 생성 시점에 실패시켜, 약한 키로 서버가 뜨는 일을 막습니다.
 */
@ConfigurationProperties(prefix = "ansimon.auth")
public record AuthProperties(
        String jwtSecret,
        Duration accessTokenTtl,
        String issuer
) {

    private static final int MIN_SECRET_BYTES = 32;
    private static final Duration DEFAULT_TTL = Duration.ofHours(1);
    private static final String DEFAULT_ISSUER = "ansimon-backend";

    public AuthProperties {
        if (!StringUtils.hasText(jwtSecret)) {
            throw new IllegalStateException("ansimon.auth.jwt-secret must be set");
        }
        jwtSecret = jwtSecret.trim();
        if (jwtSecret.getBytes(StandardCharsets.UTF_8).length < MIN_SECRET_BYTES) {
            throw new IllegalStateException("ansimon.auth.jwt-secret must be at least 32 bytes");
        }
        accessTokenTtl = accessTokenTtl == null ? DEFAULT_TTL : accessTokenTtl;
        if (accessTokenTtl.isZero() || accessTokenTtl.isNegative()) {
            throw new IllegalStateException("ansimon.auth.access-token-ttl must be positive");
        }
        issuer = StringUtils.hasText(issuer) ? issuer.trim() : DEFAULT_ISSUER;
    }
}
```

Create `global/security/AdminBootstrapProperties.java`:

```java
package com.nmdw.ansimon.global.security;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * 관리자 계정이 하나도 없을 때 한 번만 만들 첫 계정의 아이디와 비밀번호를 바인딩합니다.
 * 가입 API를 두지 않으므로 운영자는 배포 환경변수로만 첫 계정을 만들 수 있습니다.
 */
@ConfigurationProperties(prefix = "ansimon.auth.bootstrap-admin")
public record AdminBootstrapProperties(
        String loginId,
        String password
) {

    @Override
    public String toString() {
        return "AdminBootstrapProperties[loginId=" + loginId + ", password=****]";
    }
}
```

- [ ] **Step 5: Implement JwtConfig**

Create `global/security/JwtConfig.java`:

```java
package com.nmdw.ansimon.global.security;

import com.nimbusds.jose.jwk.source.ImmutableSecret;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.crypto.factory.PasswordEncoderFactories;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.JwtValidators;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.oauth2.jwt.NimbusJwtEncoder;

import javax.crypto.SecretKey;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;

/**
 * 관리자 JWT를 서명·검증하는 HS256 인코더/디코더와 비밀번호 해시 인코더를 등록합니다.
 * 디코더는 서명과 만료뿐 아니라 발급자도 검사해, 같은 키를 쓰는 다른 시스템의 토큰을 받아들이지 않습니다.
 */
@Configuration
@EnableConfigurationProperties({AuthProperties.class, AdminBootstrapProperties.class})
public class JwtConfig {

    @Bean
    public JwtEncoder jwtEncoder(AuthProperties authProperties) {
        return new NimbusJwtEncoder(new ImmutableSecret<>(signingKey(authProperties)));
    }

    @Bean
    public JwtDecoder jwtDecoder(AuthProperties authProperties) {
        NimbusJwtDecoder decoder = NimbusJwtDecoder.withSecretKey(signingKey(authProperties))
                .macAlgorithm(MacAlgorithm.HS256)
                .build();
        decoder.setJwtValidator(JwtValidators.createDefaultWithIssuer(authProperties.issuer()));
        return decoder;
    }

    @Bean
    public PasswordEncoder passwordEncoder() {
        return PasswordEncoderFactories.createDelegatingPasswordEncoder();
    }

    private static SecretKey signingKey(AuthProperties authProperties) {
        return new SecretKeySpec(authProperties.jwtSecret().getBytes(StandardCharsets.UTF_8), "HmacSHA256");
    }
}
```

- [ ] **Step 6: Implement the security chains**

`SecurityConfig.java`:
- `@Import(CorsConfig.class)`를 `@Import({CorsConfig.class, JwtConfig.class})`로 바꾼다.
- 클래스 Javadoc을 다음으로 바꾼다:

```java
/**
 * 서버 간 내부 API, 관리자 API, 그 밖의 공개 경로에 서로 다른 보안 정책을 적용하는 세 개의 필터 체인을 정의합니다.
 * {@code /internal/**}는 Bearer 내부 키, {@code /api/**}는 관리자 JWT를 요구하며 관리자 프론트엔드 CORS는 이 체인에만 허용합니다.
 * 로그인과 CORS preflight만 토큰 없이 통과하고, 나머지 경로(헬스체크·API 문서)는 공개 체인이 받습니다.
 */
```

- 기존 `publicApiSecurityFilterChain`(@Order(2))을 지우고 다음 두 빈으로 바꾼다:

```java
    @Bean
    @Order(2)
    public SecurityFilterChain adminApiSecurityFilterChain(
            HttpSecurity http, CorsConfigurationSource corsConfigurationSource, JsonMapper jsonMapper) throws Exception {
        JsonAuthenticationEntryPoint entryPoint = new JsonAuthenticationEntryPoint(jsonMapper);
        return statelessApi(http)
                .securityMatcher("/api/**")
                .cors(cors -> cors.configurationSource(corsConfigurationSource))
                .oauth2ResourceServer(resourceServer -> resourceServer
                        .jwt(Customizer.withDefaults())
                        .authenticationEntryPoint(entryPoint))
                .exceptionHandling(exceptions -> exceptions.authenticationEntryPoint(entryPoint))
                .authorizeHttpRequests(authorize -> authorize
                        .requestMatchers(HttpMethod.OPTIONS, "/api/**").permitAll()
                        .requestMatchers(HttpMethod.POST, "/api/v1/auth/login").permitAll()
                        .anyRequest().hasAuthority("SCOPE_admin"))
                .build();
    }

    @Bean
    @Order(3)
    public SecurityFilterChain publicSecurityFilterChain(HttpSecurity http) throws Exception {
        return statelessApi(http)
                .cors(AbstractHttpConfigurer::disable)
                .authorizeHttpRequests(authorize -> authorize.anyRequest().permitAll())
                .build();
    }
```

- import 추가: `org.springframework.http.HttpMethod`, `org.springframework.security.config.Customizer`.

- [ ] **Step 7: 설정 파일**

`application-local.yml`의 `internal:` 블록 아래(같은 깊이)에 추가:

```yaml
  auth:
    # 로컬 전용 기본값. 운영은 ANSIMON_JWT_SECRET 필수 (openssl rand -hex 32).
    jwt-secret: ${ANSIMON_JWT_SECRET:local-dev-jwt-secret-change-me-00000000}
    access-token-ttl: ${ANSIMON_ACCESS_TOKEN_TTL:1h}
    bootstrap-admin:
      login-id: ${ADMIN_BOOTSTRAP_LOGIN_ID:}
      password: ${ADMIN_BOOTSTRAP_PASSWORD:}
```

`application-prod.yml`의 `internal:` 블록 아래:

```yaml
  auth:
    jwt-secret: ${ANSIMON_JWT_SECRET}
    access-token-ttl: ${ANSIMON_ACCESS_TOKEN_TTL:1h}
    bootstrap-admin:
      login-id: ${ADMIN_BOOTSTRAP_LOGIN_ID:}
      password: ${ADMIN_BOOTSTRAP_PASSWORD:}
```

`ansimon-backend/.env.example`의 `INTERNAL_API_KEYS=` 아래:

```
# 관리자 JWT 서명 키. 32바이트 이상 (openssl rand -hex 32). 바꾸면 발급된 토큰이 모두 무효가 된다.
ANSIMON_JWT_SECRET=
ANSIMON_ACCESS_TOKEN_TTL=1h
# admin_account 가 비어 있을 때만 첫 관리자를 만든다. 계정이 생긴 뒤에는 지워도 된다. 비밀번호 12자 이상.
ADMIN_BOOTSTRAP_LOGIN_ID=
ADMIN_BOOTSTRAP_PASSWORD=
```

- [ ] **Step 8: 기존 `/api` 컨트롤러 테스트에 관리자 토큰 붙이기**

다음 세 파일에서 `mockMvc.perform(...)`으로 보내는 **모든** 요청 빌더 끝에 `.with(admin())`를 붙인다:
- `elderly/api/ElderlyControllerTest.java`
- `contact/api/CallObservationControllerTest.java`
- `guidance/api/GuidanceControllerTest.java`

`ContactControllerTest`는 `/internal`이라 그대로 둔다.

예시:

```java
mockMvc.perform(post("/api/v1/elderly")
                .with(admin())
                .contentType(MediaType.APPLICATION_JSON)
                .content(body))
```

각 테스트 클래스 맨 아래에 헬퍼를 추가한다:

```java
    private static RequestPostProcessor admin() {
        return jwt().authorities(new SimpleGrantedAuthority("SCOPE_admin"));
    }
```

필요한 import:

```java
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.test.web.servlet.request.RequestPostProcessor;

import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `./gradlew test`
Expected: `BUILD SUCCESSFUL`. 테스트 수는 113 − 2(지운 테스트) + 3(`AuthPropertiesTest`) + 11(`AdminApiSecurityTest`) = **125**다.

Run: `./gradlew test --tests "*AdminApiSecurityTest" --info | grep -i "Using generated security password"`
Expected: 출력 없음. `JwtDecoder` 빈이 있으니 기본 사용자가 생기면 안 된다. 출력이 있으면 보고서에 적는다(1차의 이월 항목 "generated-password 로그 노이즈").

- [ ] **Step 10: Commit**

```bash
git add ansimon-backend/build.gradle ansimon-backend/.env.example ansimon-backend/src
git commit -m "feat(security): require admin JWT on /api/** via resource server chain"
```

---

### Task 2: 관리자 계정, 로그인 API, 첫 계정 생성

**Files:**
- Create: `src/main/resources/db/migration/mysql/V4__create_admin_account.sql`
- Create: `auth/domain/AdminAccount.java`, `auth/infra/AdminAccountRepository.java`
- Create: `auth/application/AccessTokenIssuer.java`, `auth/application/AuthService.java`, `auth/application/AdminBootstrap.java`
- Create: `auth/dto/LoginRequest.java`, `auth/dto/LoginResponse.java`, `auth/api/AuthController.java`
- Modify: `global/error/ErrorCode.java`
- Test: `auth/application/AuthServiceTest.java`, `auth/application/AdminBootstrapTest.java`, `auth/api/AuthControllerTest.java`

**Interfaces:**
- Consumes (Task 1): 빈 `JwtEncoder`·`PasswordEncoder`, `AuthProperties`(`accessTokenTtl()`, `issuer()`), `AdminBootstrapProperties`(`loginId()`, `password()`)
- Produces:
  - `ErrorCode.INVALID_CREDENTIALS("AUTH_INVALID_CREDENTIALS", HttpStatus.UNAUTHORIZED, "Login ID or password is incorrect.")`
  - `AdminAccount.create(String loginId, String passwordHash)`, `getLoginId()`, `getPasswordHash()`, `getLastLoginAt()`, `recordLogin(Instant)`
  - `AdminAccountRepository.findByLoginId(String) -> Optional<AdminAccount>`
  - `AccessTokenIssuer.issue(String subject) -> IssuedToken(String value, long expiresInSeconds)`
  - `AuthService.login(LoginRequest) -> LoginResponse`
  - `record LoginRequest(String loginId, String password)`, `record LoginResponse(String accessToken, String tokenType, long expiresIn)`
  - HTTP `POST /api/v1/auth/login` → `{success:true, data:{accessToken, tokenType:"Bearer", expiresIn:3600}}`

- [ ] **Step 1: Write the failing tests**

Create `src/test/java/com/nmdw/ansimon/auth/application/AuthServiceTest.java`:

```java
package com.nmdw.ansimon.auth.application;

import com.nmdw.ansimon.auth.domain.AdminAccount;
import com.nmdw.ansimon.auth.dto.LoginRequest;
import com.nmdw.ansimon.auth.dto.LoginResponse;
import com.nmdw.ansimon.auth.infra.AdminAccountRepository;
import com.nmdw.ansimon.global.error.BusinessException;
import com.nmdw.ansimon.global.error.ErrorCode;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.security.crypto.factory.PasswordEncoderFactories;
import org.springframework.security.crypto.password.PasswordEncoder;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.spy;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class AuthServiceTest {

    private final AdminAccountRepository repository = mock(AdminAccountRepository.class);
    private final AccessTokenIssuer tokenIssuer = mock(AccessTokenIssuer.class);
    private final PasswordEncoder passwordEncoder = spy(PasswordEncoderFactories.createDelegatingPasswordEncoder());
    private AuthService authService;
    private AdminAccount admin;

    @BeforeEach
    void setUp() {
        authService = new AuthService(repository, tokenIssuer, passwordEncoder);
        admin = AdminAccount.create("admin", passwordEncoder.encode("correct-horse-battery"));
    }

    @Test
    void issuesBearerTokenAndRecordsLoginOnValidCredentials() {
        when(repository.findByLoginId("admin")).thenReturn(Optional.of(admin));
        when(tokenIssuer.issue("admin")).thenReturn(new AccessTokenIssuer.IssuedToken("jwt-value", 3600));

        LoginResponse response = authService.login(new LoginRequest("admin", "correct-horse-battery"));

        assertThat(response.accessToken()).isEqualTo("jwt-value");
        assertThat(response.tokenType()).isEqualTo("Bearer");
        assertThat(response.expiresIn()).isEqualTo(3600);
        assertThat(admin.getLastLoginAt()).isNotNull();
    }

    @Test
    void rejectsWrongPasswordWithoutIssuingToken() {
        when(repository.findByLoginId("admin")).thenReturn(Optional.of(admin));

        assertThatThrownBy(() -> authService.login(new LoginRequest("admin", "wrong-password")))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).errorCode())
                .isEqualTo(ErrorCode.INVALID_CREDENTIALS);
        verify(tokenIssuer, never()).issue(anyString());
        assertThat(admin.getLastLoginAt()).isNull();
    }

    @Test
    void rejectsUnknownLoginIdTheSameWayAndStillComparesAHash() {
        when(repository.findByLoginId("ghost")).thenReturn(Optional.empty());

        assertThatThrownBy(() -> authService.login(new LoginRequest("ghost", "whatever-password")))
                .isInstanceOf(BusinessException.class)
                .extracting(e -> ((BusinessException) e).errorCode())
                .isEqualTo(ErrorCode.INVALID_CREDENTIALS);
        // 응답 시간으로 계정 존재 여부가 드러나지 않도록 해시 비교는 항상 한 번 수행한다
        verify(passwordEncoder).matches(eq("whatever-password"), anyString());
        verify(tokenIssuer, never()).issue(anyString());
    }
}
```

`BusinessException`의 오류 코드 접근자는 `errorCode()`다.

Create `src/test/java/com/nmdw/ansimon/auth/application/AdminBootstrapTest.java`:

```java
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
```

Create `src/test/java/com/nmdw/ansimon/auth/api/AuthControllerTest.java`:

```java
package com.nmdw.ansimon.auth.api;

import com.nmdw.ansimon.auth.application.AuthService;
import com.nmdw.ansimon.auth.dto.LoginResponse;
import com.nmdw.ansimon.global.error.BusinessException;
import com.nmdw.ansimon.global.error.ErrorCode;
import com.nmdw.ansimon.global.error.GlobalExceptionHandler;
import com.nmdw.ansimon.global.security.SecurityConfig;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(AuthController.class)
@Import({GlobalExceptionHandler.class, SecurityConfig.class})
class AuthControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private AuthService authService;

    @Test
    void returnsBearerTokenWithoutRequiringAToken() throws Exception {
        when(authService.login(any())).thenReturn(new LoginResponse("jwt-value", "Bearer", 3600));

        mockMvc.perform(post("/api/v1/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"loginId\":\"admin\",\"password\":\"correct-horse-battery\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.accessToken").value("jwt-value"))
                .andExpect(jsonPath("$.data.tokenType").value("Bearer"))
                .andExpect(jsonPath("$.data.expiresIn").value(3600));
    }

    @Test
    void mapsBadCredentialsTo401() throws Exception {
        when(authService.login(any())).thenThrow(new BusinessException(ErrorCode.INVALID_CREDENTIALS));

        mockMvc.perform(post("/api/v1/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"loginId\":\"admin\",\"password\":\"wrong-password\"}"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.error.code").value("AUTH_INVALID_CREDENTIALS"));
    }

    @Test
    void rejectsBlankFieldsBeforeTouchingTheService() throws Exception {
        mockMvc.perform(post("/api/v1/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"loginId\":\"\",\"password\":\"\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error.code").value("GLOBAL_VALIDATION_ERROR"));
        verifyNoInteractions(authService);
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./gradlew test --tests "com.nmdw.ansimon.auth.*"`
Expected: 컴파일 실패. `auth` 패키지 클래스와 `ErrorCode.INVALID_CREDENTIALS`가 아직 없다.

- [ ] **Step 3: Migration, error code, entity, repository**

Create `src/main/resources/db/migration/mysql/V4__create_admin_account.sql`:

```sql
-- 관리자 콘솔 로그인 계정. 가입 API 는 없고 첫 계정은 ADMIN_BOOTSTRAP_* 환경변수로 한 번만 만든다.
CREATE TABLE admin_account (
    id BIGINT NOT NULL AUTO_INCREMENT,
    login_id VARCHAR(50) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    last_login_at DATETIME(6) NULL,
    created_at DATETIME(6) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uk_admin_account_login_id UNIQUE (login_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

`ErrorCode.java`의 `UNAUTHORIZED(...)` 바로 아래에 추가:

```java
    INVALID_CREDENTIALS("AUTH_INVALID_CREDENTIALS", HttpStatus.UNAUTHORIZED, "Login ID or password is incorrect."),
```

`ErrorCodeTest`는 개별 상수만 검사하므로 고칠 필요가 없다.

Create `auth/domain/AdminAccount.java`:

```java
package com.nmdw.ansimon.auth.domain;

import com.nmdw.ansimon.global.persistence.BaseTimeEntity;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.time.Instant;

/**
 * 관리자 콘솔에 로그인할 수 있는 운영자 계정입니다.
 * 비밀번호는 알고리즘 접두사가 붙은 해시로만 보관하며, 마지막 로그인 시각으로 사용 여부를 추적합니다.
 */
@Entity
@Table(name = "admin_account")
@Getter
@EqualsAndHashCode(of = "id", callSuper = false)
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class AdminAccount extends BaseTimeEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "login_id", nullable = false, length = 50, unique = true)
    private String loginId;

    @Column(name = "password_hash", nullable = false)
    private String passwordHash;

    @Column(name = "last_login_at")
    private Instant lastLoginAt;

    private AdminAccount(String loginId, String passwordHash) {
        this.loginId = loginId;
        this.passwordHash = passwordHash;
    }

    public static AdminAccount create(String loginId, String passwordHash) {
        return new AdminAccount(loginId, passwordHash);
    }

    public void recordLogin(Instant loggedInAt) {
        this.lastLoginAt = loggedInAt;
    }
}
```

Create `auth/infra/AdminAccountRepository.java`:

```java
package com.nmdw.ansimon.auth.infra;

import com.nmdw.ansimon.auth.domain.AdminAccount;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;

/**
 * {@link AdminAccount}를 로그인 아이디로 조회하는 Spring Data JPA 저장소입니다.
 */
public interface AdminAccountRepository extends JpaRepository<AdminAccount, Long> {

    Optional<AdminAccount> findByLoginId(String loginId);
}
```

- [ ] **Step 4: DTOs**

Create `auth/dto/LoginRequest.java`:

```java
package com.nmdw.ansimon.auth.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/**
 * 관리자 로그인 요청입니다. 비밀번호가 로그·예외 메시지로 새지 않도록 문자열 표현에서 가립니다.
 */
public record LoginRequest(
        @NotBlank @Size(max = 50) String loginId,
        @NotBlank @Size(max = 128) String password
) {

    @Override
    public String toString() {
        return "LoginRequest[loginId=" + loginId + ", password=****]";
    }
}
```

Create `auth/dto/LoginResponse.java`:

```java
package com.nmdw.ansimon.auth.dto;

/**
 * 로그인 성공 시 돌려주는 액세스 토큰과 토큰 종류, 남은 유효시간(초)입니다.
 */
public record LoginResponse(
        String accessToken,
        String tokenType,
        long expiresIn
) {
}
```

- [ ] **Step 5: Token issuer, service, bootstrap, controller**

Create `auth/application/AccessTokenIssuer.java`:

```java
package com.nmdw.ansimon.auth.application;

import com.nmdw.ansimon.global.security.AuthProperties;
import org.springframework.security.oauth2.jose.jws.MacAlgorithm;
import org.springframework.security.oauth2.jwt.JwsHeader;
import org.springframework.security.oauth2.jwt.JwtClaimsSet;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.JwtEncoderParameters;
import org.springframework.stereotype.Component;

import java.time.Instant;

/**
 * 로그인한 관리자에게 HS256 액세스 토큰을 발급합니다.
 * 토큰에는 발급자, 주체(로그인 아이디), 만료 시각, {@code scope=admin}만 담고 개인정보는 넣지 않습니다.
 */
@Component
public class AccessTokenIssuer {

    private final JwtEncoder jwtEncoder;
    private final AuthProperties authProperties;

    public AccessTokenIssuer(JwtEncoder jwtEncoder, AuthProperties authProperties) {
        this.jwtEncoder = jwtEncoder;
        this.authProperties = authProperties;
    }

    public IssuedToken issue(String subject) {
        Instant now = Instant.now();
        JwtClaimsSet claims = JwtClaimsSet.builder()
                .issuer(authProperties.issuer())
                .subject(subject)
                .issuedAt(now)
                .expiresAt(now.plus(authProperties.accessTokenTtl()))
                .claim("scope", "admin")
                .build();
        String value = jwtEncoder.encode(JwtEncoderParameters.from(JwsHeader.with(MacAlgorithm.HS256).build(), claims))
                .getTokenValue();
        return new IssuedToken(value, authProperties.accessTokenTtl().toSeconds());
    }

    public record IssuedToken(String value, long expiresInSeconds) {
    }
}
```

Create `auth/application/AuthService.java`:

```java
package com.nmdw.ansimon.auth.application;

import com.nmdw.ansimon.auth.domain.AdminAccount;
import com.nmdw.ansimon.auth.dto.LoginRequest;
import com.nmdw.ansimon.auth.dto.LoginResponse;
import com.nmdw.ansimon.auth.infra.AdminAccountRepository;
import com.nmdw.ansimon.global.error.BusinessException;
import com.nmdw.ansimon.global.error.ErrorCode;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.Optional;

/**
 * 관리자 아이디·비밀번호를 확인하고 액세스 토큰을 발급합니다.
 * 아이디가 없을 때도 같은 비용의 해시 비교를 수행하고 같은 오류를 돌려줘, 응답으로 계정 존재 여부가 드러나지 않게 합니다.
 */
@Service
public class AuthService {

    private final AdminAccountRepository adminAccountRepository;
    private final AccessTokenIssuer accessTokenIssuer;
    private final PasswordEncoder passwordEncoder;
    private final String dummyHash;

    public AuthService(AdminAccountRepository adminAccountRepository,
                       AccessTokenIssuer accessTokenIssuer,
                       PasswordEncoder passwordEncoder) {
        this.adminAccountRepository = adminAccountRepository;
        this.accessTokenIssuer = accessTokenIssuer;
        this.passwordEncoder = passwordEncoder;
        this.dummyHash = passwordEncoder.encode("ansimon-timing-equalizer");
    }

    @Transactional
    public LoginResponse login(LoginRequest request) {
        Optional<AdminAccount> account = adminAccountRepository.findByLoginId(request.loginId().trim());
        String hash = account.map(AdminAccount::getPasswordHash).orElse(dummyHash);
        boolean matches = passwordEncoder.matches(request.password(), hash);
        if (account.isEmpty() || !matches) {
            throw new BusinessException(ErrorCode.INVALID_CREDENTIALS);
        }
        AdminAccount admin = account.get();
        admin.recordLogin(Instant.now());
        AccessTokenIssuer.IssuedToken token = accessTokenIssuer.issue(admin.getLoginId());
        return new LoginResponse(token.value(), "Bearer", token.expiresInSeconds());
    }
}
```

Create `auth/application/AdminBootstrap.java`:

```java
package com.nmdw.ansimon.auth.application;

import com.nmdw.ansimon.auth.domain.AdminAccount;
import com.nmdw.ansimon.auth.infra.AdminAccountRepository;
import com.nmdw.ansimon.global.security.AdminBootstrapProperties;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

/**
 * 관리자 계정이 하나도 없을 때 환경변수로 받은 첫 계정을 한 번만 만듭니다.
 * 계정이 이미 있으면 아무것도 하지 않으므로, 배포 후 환경변수를 지우지 않아도 비밀번호가 덮어써지지 않습니다.
 */
@Component
public class AdminBootstrap implements ApplicationRunner {

    private static final Logger log = LoggerFactory.getLogger(AdminBootstrap.class);
    private static final int MIN_PASSWORD_LENGTH = 12;

    private final AdminAccountRepository adminAccountRepository;
    private final PasswordEncoder passwordEncoder;
    private final AdminBootstrapProperties properties;

    public AdminBootstrap(AdminAccountRepository adminAccountRepository,
                          PasswordEncoder passwordEncoder,
                          AdminBootstrapProperties properties) {
        this.adminAccountRepository = adminAccountRepository;
        this.passwordEncoder = passwordEncoder;
        this.properties = properties;
    }

    @Override
    public void run(ApplicationArguments args) {
        if (adminAccountRepository.count() > 0) {
            return;
        }
        if (!StringUtils.hasText(properties.loginId()) || !StringUtils.hasText(properties.password())) {
            log.warn("No admin account exists. Set ADMIN_BOOTSTRAP_LOGIN_ID and ADMIN_BOOTSTRAP_PASSWORD to create one.");
            return;
        }
        if (properties.password().length() < MIN_PASSWORD_LENGTH) {
            throw new IllegalStateException("ADMIN_BOOTSTRAP_PASSWORD must be at least 12 characters");
        }
        String loginId = properties.loginId().trim();
        adminAccountRepository.save(AdminAccount.create(loginId, passwordEncoder.encode(properties.password())));
        log.info("Created the first admin account '{}'.", loginId);
    }
}
```

(프로젝트는 `@Slf4j` 대신 `LoggerFactory.getLogger`를 쓴다 — `WebClientErrorMapper`와 같은 방식.)

Create `auth/api/AuthController.java`:

```java
package com.nmdw.ansimon.auth.api;

import com.nmdw.ansimon.auth.application.AuthService;
import com.nmdw.ansimon.auth.dto.LoginRequest;
import com.nmdw.ansimon.auth.dto.LoginResponse;
import com.nmdw.ansimon.global.response.ApiResponse;
import io.swagger.v3.oas.annotations.Operation;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 관리자 콘솔 로그인 API입니다. 토큰 없이 호출할 수 있는 유일한 {@code /api/**} 엔드포인트입니다.
 */
@RestController
@RequestMapping("/api/v1/auth")
public class AuthController {

    private final AuthService authService;

    public AuthController(AuthService authService) {
        this.authService = authService;
    }

    @Operation(summary = "관리자 로그인", description = "아이디·비밀번호를 확인하고 Bearer 액세스 토큰을 발급합니다.")
    @PostMapping("/login")
    public ApiResponse<LoginResponse> login(@Valid @RequestBody LoginRequest request) {
        return ApiResponse.success(authService.login(request));
    }
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `./gradlew test`
Expected: `BUILD SUCCESSFUL`, 125 + 3 + 4 + 3 = **135**개 테스트.

`AnsimonApplicationTests`(컨텍스트 로드)가 V4 마이그레이션과 `AdminBootstrap`(경고 로그만)까지 함께 검증한다.

- [ ] **Step 7: Commit**

```bash
git add ansimon-backend/src
git commit -m "feat(auth): add admin accounts, login endpoint, and first-admin bootstrap"
```

---

### Task 3: 관리자 프론트 로그인과 토큰 전송

**Files:**
- Create: `ansimon_front_end/login.html`
- Modify: `ansimon_front_end/assets/api.js`
- Modify: `ansimon_front_end/index.html` (`postCareRun`, 약 1032행)
- Modify: `ansimon_front_end/elderly-detail.html` (약 416행)
- Modify: `ansimon_front_end/README.md`

**Interfaces:**
- Consumes: `POST /api/v1/auth/login` → `data.accessToken`
- Produces (전역 함수, `api.js`): `getToken()`, `setToken(token)`, `clearToken()`, `authHeaders() -> object`, `redirectToLogin()`

- [ ] **Step 1: `assets/api.js`**

`API_BASE` 정의 아래에 추가:

```js
/* ── 관리자 토큰 ──
   sessionStorage: 탭을 닫으면 사라진다. 공용 PC 에 로그인이 남지 않게 localStorage 를 쓰지 않는다. */
const TOKEN_KEY = "ansimon.accessToken";
const IS_LOGIN_PAGE = /(^|\/)login\.html$/.test(location.pathname);

function getToken() { try { return sessionStorage.getItem(TOKEN_KEY); } catch { return null; } }
function setToken(token) { try { sessionStorage.setItem(TOKEN_KEY, token); } catch {} }
function clearToken() { try { sessionStorage.removeItem(TOKEN_KEY); } catch {} }
function authHeaders() { const t = getToken(); return t ? { Authorization: `Bearer ${t}` } : {}; }

/* 다른 사이트로 튕기는 오픈 리다이렉트를 막기 위해, 돌아올 곳은 같은 폴더의 .html 만 허용한다. */
function redirectToLogin() {
  clearToken();
  const here = location.pathname.split("/").pop() + location.search;
  location.href = `login.html?next=${encodeURIComponent(here)}`;
}

if (!IS_LOGIN_PAGE && !getToken()) redirectToLogin();
```

`apiRequest`의 `headers`에 `...authHeaders(),`를 추가하고, `response.status === 204` 검사 **앞에** 401 처리를 추가한다:

```js
async function apiRequest(path, { method = "GET", body } = {}) {
  const response = await fetch(API_BASE + path, {
    method,
    headers: {
      Accept: "application/json",
      ...authHeaders(),
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (response.status === 401 && !IS_LOGIN_PAGE) {
    redirectToLogin();
    throw Object.assign(new Error("로그인이 필요합니다."), { status: 401 });
  }
  if (response.status === 204) return null;
```

(이하 기존 코드 그대로)

파일 끝에 로그아웃 버튼을 추가한다. 세 화면이 공유하는 `.nav-end`가 있으면 그 안에 붙는다:

```js
/* ── 로그아웃 (nav 오른쪽) ── */
document.addEventListener("DOMContentLoaded", () => {
  const navEnd = $(".nav-end");
  if (!navEnd || IS_LOGIN_PAGE) return;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "pill-btn";
  button.textContent = "로그아웃";
  button.addEventListener("click", () => { clearToken(); location.href = "login.html"; });
  navEnd.appendChild(button);
});
```

(`pill-btn`은 `theme.css`의 보조 버튼, `pill-btn solid`는 주 버튼이다.)

- [ ] **Step 2: `login.html`**

Create `ansimon_front_end/login.html`:

```html
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>안심온 · 관리자 로그인</title>
  <link rel="stylesheet" href="./assets/theme.css" />
  <style>
    .login-wrap { min-height: 100vh; display: grid; place-items: center; padding: 16px; }
    .login-card { width: 100%; max-width: 360px; display: grid; gap: 12px; }
    .login-card input { width: 100%; }
    .login-error { min-height: 1.2em; color: var(--danger, #c0392b); font-size: 14px; }
  </style>
</head>
<body>
  <main class="login-wrap">
    <form class="card login-card" id="login-form" novalidate>
      <h1>안심온 관리자</h1>
      <label>아이디 <input id="login-id" name="loginId" autocomplete="username" required maxlength="50" /></label>
      <label>비밀번호 <input id="password" name="password" type="password" autocomplete="current-password" required maxlength="128" /></label>
      <p class="login-error" id="login-error" role="alert"></p>
      <button class="pill-btn solid" type="submit" id="login-submit">로그인</button>
    </form>
  </main>
  <div id="toast"></div>
<script src="./assets/api.js"></script>
<script>
  clearToken();   // 만료된 토큰이 로그인 요청에 붙어 401 이 나는 것을 막는다

  function safeNext() {
    const next = new URLSearchParams(location.search).get("next") || "";
    return /^[a-z0-9-]+\.html(\?[^#]*)?$/i.test(next) ? next : "index.html";
  }

  $("#login-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const loginId = $("#login-id").value.trim();
    const password = $("#password").value;
    if (!loginId || !password) { $("#login-error").textContent = "아이디와 비밀번호를 입력하세요."; return; }
    $("#login-submit").disabled = true;
    $("#login-error").textContent = "";
    try {
      const data = await api.post("/api/v1/auth/login", { loginId, password });
      setToken(data.accessToken);
      location.href = safeNext();
    } catch (err) {
      $("#login-error").textContent = err.code === "AUTH_INVALID_CREDENTIALS"
        ? "아이디 또는 비밀번호가 올바르지 않습니다."
        : `로그인할 수 없습니다 (${err.message}).`;
    } finally {
      $("#login-submit").disabled = false;
    }
  });
</script>
</body>
</html>
```

(`card`와 `pill-btn solid`는 `theme.css`에 있는 클래스다.)

- [ ] **Step 3: 직접 `fetch`하는 두 곳**

`index.html`의 `postCareRun` 안, `fetch(API_BASE + ENDPOINTS.careRun(elderlyId), {...})`의 `headers`에 `...authHeaders(),`를 추가한다. `const payload = await response.json()...` 줄 **앞에** 다음을 추가한다:

```js
          if (response.status === 401) { redirectToLogin(); return; }
```

`return` 대신 오류를 던지는 편이 그 함수의 기존 오류 흐름에 맞으면 `throw new Error("로그인이 필요합니다.")`로 쓴다. 이때도 `redirectToLogin()`은 먼저 부른다.

`elderly-detail.html` 약 416행의 `fetch(...)`도 같은 방식으로 고친다:
- `headers: { Accept: "application/json", "Content-Type": "application/json", ...authHeaders() }`
- `const payload = ...` 앞에 `if (response.status === 401) { redirectToLogin(); return; }`

남은 직접 호출이 없는지 확인한다:

Run: `grep -n "fetch(" ansimon_front_end/*.html ansimon_front_end/assets/*.js`
Expected: `api.js`의 `apiRequest`, `index.html`의 `postCareRun`, `elderly-detail.html`의 care-run, 이렇게 세 곳만 나온다. 세 곳 모두 `authHeaders()`를 쓴다.

- [ ] **Step 4: README**

`ansimon_front_end/README.md`의 `## 실행` 섹션 끝에 추가:

```markdown
### 로그인

모든 화면은 관리자 로그인이 필요합니다. 토큰이 없으면 `login.html`로 이동하고, 로그인하면 원래 화면으로 돌아옵니다.
토큰은 `sessionStorage`에 보관되어 탭을 닫으면 사라집니다. 첫 관리자 계정은 백엔드 환경변수
`ADMIN_BOOTSTRAP_LOGIN_ID` / `ADMIN_BOOTSTRAP_PASSWORD`로 만듭니다(계정이 하나도 없을 때 한 번).
```

`## 연결된 API` 표 맨 위에 다음 행을 추가한다: `| 로그인 | `POST /api/v1/auth/login` (토큰 없이 호출, 나머지는 모두 `Authorization: Bearer`) |`

- [ ] **Step 5: 수동 확인**

정적 파일이라 자동 테스트가 없다. 다음을 확인한다:

1. `node --check ansimon_front_end/assets/api.js`가 문법 오류 없이 끝난다(Node가 있으면).
2. 로컬 백엔드를 띄울 수 있으면(MySQL 필요):
   - `ADMIN_BOOTSTRAP_LOGIN_ID=admin ADMIN_BOOTSTRAP_PASSWORD=<12자 이상>`으로 기동한다.
   - `python -m http.server 5500`으로 프론트를 띄운다.
   - 다음을 차례로 확인한다:
     - (a) `index.html`에 들어가면 `login.html?next=index.html`로 이동한다.
     - (b) 틀린 비밀번호를 넣으면 안내 문구가 나온다.
     - (c) 로그인하면 대시보드가 데이터를 불러온다.
     - (d) 로그아웃하면 다시 로그인 화면이 나온다.
     - (e) `login.html?next=https://evil.example`로 로그인하면 `index.html`로 간다.
3. 백엔드를 띄울 수 없으면 그렇다고 보고서에 적는다. 1차의 Task 5와 같은 이월 항목이다.

- [ ] **Step 6: Commit**

```bash
git add ansimon_front_end
git commit -m "feat(front): add admin login page and send bearer token on every API call"
```

---

## 배포 체크리스트 (Phase B 머지 후)

1. Railway 백엔드에 다음을 등록한다:
   - `ANSIMON_JWT_SECRET`(`openssl rand -hex 32`)
   - `ADMIN_BOOTSTRAP_LOGIN_ID`
   - `ADMIN_BOOTSTRAP_PASSWORD`(12자 이상, 비밀번호 관리자에 보관)
2. 백엔드를 배포한다. 로그에 `Created the first admin account`가 한 번 찍히는지 확인한다. 이후 `ADMIN_BOOTSTRAP_PASSWORD`는 지워도 된다.
3. 프론트를 배포한다. 배포 전 프론트로는 아무것도 볼 수 없으니, 백엔드와 같은 창에 올린다.
4. `curl <백엔드>/api/v1/elderly`가 401을 돌려주는지, 로그인 후 받은 토큰으로 200을 돌려주는지 확인한다.

## 남은 과제 (이번 범위 밖)

- 로그인 시도 제한(아이디·IP별 실패 횟수와 잠금). 지금은 bcrypt 비용만이 속도를 늦춘다.
- 역할 분리(조회 전용 / 전화 실행). 필요해지면 `scope`에 값을 추가하고 `hasAuthority`를 경로별로 나눈다.
- 토큰 즉시 폐기(로그아웃해도 토큰은 만료 전까지 유효하다). 짧은 TTL로 보완한다.
- 비밀번호 변경 API.
