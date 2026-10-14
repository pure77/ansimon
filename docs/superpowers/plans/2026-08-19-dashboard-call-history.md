# 대시보드 축소 · 통화기록 조회 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 대시보드를 어르신 목록·통화 기록 두 카드로 줄이고, 통화기록 조회 API를 만들어 목업을 실제 데이터로 교체한다.

**Architecture:** 백엔드에 통화기록 페이징 조회와 현재 위험도 조회 두 엔드포인트를 추가한다. 대응계획은 통화기록 응답에 동봉해 별도 엔드포인트를 만들지 않는다. 프론트는 정적 HTML 3종 중 `index.html`에서 목업 영역을 삭제하고 `elderly-detail.html`의 목업 폴백을 걷어낸다.

**Tech Stack:** Spring Boot 3 / Spring Data JPA / Jackson(tools.jackson) / 정적 HTML + vanilla JS

**Spec:** `docs/superpowers/specs/2026-08-19-dashboard-call-history-design.md`

## Global Constraints

- 응답 포맷은 `ApiResponse<T>` (`{success, data, error}`), 목록은 `PageResponse<T>`를 감싼다.
- 시간대는 Asia/Seoul. 저장·전송은 `Instant`(UTC), 날짜 경계 계산만 KST.
- `ContactStatus`·`TriState`는 평범한 enum이라 JSON·쿼리파라미터 모두 **대문자**다. (`ConsentStatus`·`RiskLevel`만 `EnumCode`로 소문자.)
- 주석과 사용자 노출 문구는 한국어. 기존 파일의 주석 밀도와 어투를 따른다.
- 프론트는 빌드 도구 없는 정적 HTML이다. 모듈 시스템·번들러를 도입하지 않는다.
- **검증 최소화 모드**: 새 자동 테스트를 작성하지 않는다. 각 태스크는 `./gradlew build`(기존 테스트 포함) 또는 브라우저 확인으로 끝낸다.

**저장소 주의:** `ansimon-backend`와 `ansimon_front_end`는 **각각 별도 git 저장소**다. 커밋은 해당 저장소 디렉터리 안에서 실행한다. 루트 `ansimon_total`은 저장소가 아니다.

---

### Task 1: 통화기록 목록 조회 API

**Files:**
- Create: `ansimon-backend/src/main/java/com/nmdw/ansimon/contact/dto/CallObservationListResponse.java`
- Modify: `ansimon-backend/src/main/java/com/nmdw/ansimon/contact/infra/CallObservationRepository.java`
- Modify: `ansimon-backend/src/main/java/com/nmdw/ansimon/contact/application/CallObservationService.java`
- Modify: `ansimon-backend/src/main/java/com/nmdw/ansimon/contact/api/CallObservationController.java`

**Interfaces:**
- Consumes: 기존 `CallObservation`, `ContactJob`, `InterventionPlan`, `PageResponse`, `ApiResponse`.
- Produces: `GET /api/v1/contact/observations` → `ApiResponse<PageResponse<CallObservationListResponse>>`. Task 3·4의 프론트가 이 계약에 의존한다.

- [ ] **Step 1: 응답 DTO 생성**

`CallObservationListResponse.java` 전체 내용:

```java
package com.nmdw.ansimon.contact.dto;

import com.nmdw.ansimon.contact.domain.ContactStatus;
import com.nmdw.ansimon.contact.domain.TriState;
import io.swagger.v3.oas.annotations.media.Schema;

import java.math.BigDecimal;
import java.time.Instant;

/**
 * 통화 기록 목록 한 줄에 해당하는 응답입니다.
 * 목록 화면은 어르신 이름과 그 통화의 대응계획 문구까지 함께 보여주므로
 * 단건 교정 응답({@link CallObservationResponse})과 필드 구성이 다릅니다.
 */
@Schema(description = "통화 기록 목록 항목")
public record CallObservationListResponse(
        @Schema(description = "통화 결과 식별자", example = "5") Long id,
        @Schema(description = "전화 작업 식별자", example = "1") Long contactJobId,
        @Schema(description = "어르신 식별자", example = "10") Long elderlyId,
        @Schema(description = "어르신 이름", example = "김안심") String elderlyName,
        @Schema(description = "통화 결과 상태", example = "ANSWERED") ContactStatus contactStatus,
        @Schema(description = "쉼터 이동 의향", example = "YES") TriState shelterIntent,
        @Schema(description = "혼자 이동 가능 여부", example = "NO") TriState canMoveAlone,
        @Schema(description = "도움 필요 여부", example = "YES") TriState helpNeeded,
        @Schema(description = "증상 언급 여부", example = "YES") TriState symptomMentioned,
        @Schema(description = "통화 내용과 조치 내용 요약") String summary,
        @Schema(description = "요약 신뢰도", example = "0.9100") BigDecimal confidence,
        @Schema(description = "통화 종료 시각", example = "2026-08-18T02:30:00Z") Instant endedAt,
        @Schema(description = "이 통화의 조치 방안") String actionGuidance,
        @Schema(description = "쉼터 안내 문구") String shelterRecommendationText
) {
}
```

- [ ] **Step 2: 리포지토리에 페이징 조회 추가**

`CallObservationRepository.java`에 import와 메서드를 더한다. 기존 `existsByContactJobId`는 그대로 둔다.

```java
package com.nmdw.ansimon.contact.infra;

import com.nmdw.ansimon.contact.domain.CallObservation;
import com.nmdw.ansimon.contact.domain.ContactStatus;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.Instant;

public interface CallObservationRepository extends JpaRepository<CallObservation, Long> {

    boolean existsByContactJobId(Long contactJobId);

    /**
     * 목록 화면이 어르신 이름과 대응계획 문구까지 한 번에 그리므로 연관 엔티티를 fetch join으로 함께 읽습니다.
     * 조건은 모두 선택 항목이라 null이면 필터를 걸지 않습니다.
     */
    @Query(value = """
            select o from CallObservation o
            join fetch o.contactJob j
            join fetch j.elderly e
            join fetch j.interventionPlan p
            where (:elderlyId is null or e.id = :elderlyId)
              and (:status is null or o.contactStatus = :status)
              and (:from is null or o.endedAt >= :from)
              and (:to is null or o.endedAt < :to)
            order by o.endedAt desc
            """,
            countQuery = """
            select count(o) from CallObservation o
            where (:elderlyId is null or o.contactJob.elderly.id = :elderlyId)
              and (:status is null or o.contactStatus = :status)
              and (:from is null or o.endedAt >= :from)
              and (:to is null or o.endedAt < :to)
            """)
    Page<CallObservation> search(@Param("elderlyId") Long elderlyId,
                                 @Param("status") ContactStatus status,
                                 @Param("from") Instant from,
                                 @Param("to") Instant to,
                                 Pageable pageable);
}
```

- [ ] **Step 3: 서비스에 조회 메서드 추가**

`CallObservationService.java`를 아래 내용으로 교체한다. 기존 `update`·`delete`·`findById`는 그대로 유지하고 조회 경로만 더한 형태다.

```java
package com.nmdw.ansimon.contact.application;

import com.nmdw.ansimon.contact.domain.CallObservation;
import com.nmdw.ansimon.contact.domain.ContactStatus;
import com.nmdw.ansimon.contact.dto.CallObservationListResponse;
import com.nmdw.ansimon.contact.dto.CallObservationResponse;
import com.nmdw.ansimon.contact.dto.CallObservationUpdateRequest;
import com.nmdw.ansimon.contact.infra.CallObservationRepository;
import com.nmdw.ansimon.global.error.BusinessException;
import com.nmdw.ansimon.global.error.ErrorCode;
import com.nmdw.ansimon.global.response.PageResponse;
import com.nmdw.ansimon.guidance.domain.InterventionPlan;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;

/**
 * 저장된 통화 결과를 조회하고, 담당자가 교정하거나 삭제하는 유스케이스를 담당하는 애플리케이션 서비스입니다.
 * 후속 지원 업무 판단이 이 판정값에 의존하므로, LLM이 잘못 판단한 항목을 사람이 바로잡을 수 있게 합니다.
 */
@Service
@Transactional
public class CallObservationService {

    private static final ZoneId ASIA_SEOUL = ZoneId.of("Asia/Seoul");

    private final CallObservationRepository repository;
    private final ObjectMapper objectMapper;

    public CallObservationService(CallObservationRepository repository, ObjectMapper objectMapper) {
        this.repository = repository;
        this.objectMapper = objectMapper;
    }

    /**
     * date를 주면 그 날짜(Asia/Seoul)에 끝난 통화만 봅니다. 대시보드는 오늘을, 상세화면은 날짜 없이 전체를 봅니다.
     */
    @Transactional(readOnly = true)
    public PageResponse<CallObservationListResponse> search(Long elderlyId, ContactStatus status,
                                                            LocalDate date, Pageable pageable) {
        Instant from = date == null ? null : date.atStartOfDay(ASIA_SEOUL).toInstant();
        Instant to = date == null ? null : date.plusDays(1).atStartOfDay(ASIA_SEOUL).toInstant();
        return PageResponse.from(repository.search(elderlyId, status, from, to, pageable).map(this::toListResponse));
    }

    public CallObservationResponse update(Long id, CallObservationUpdateRequest request) {
        CallObservation observation = findById(id);
        observation.correct(
                StringUtils.hasText(request.summary()) ? request.summary() : observation.getSummary(),
                request.shelterIntent() != null ? request.shelterIntent() : observation.getShelterIntent(),
                request.canMoveAlone() != null ? request.canMoveAlone() : observation.getCanMoveAlone(),
                request.helpNeeded() != null ? request.helpNeeded() : observation.getHelpNeeded(),
                request.symptomMentioned() != null ? request.symptomMentioned() : observation.getSymptomMentioned());
        return CallObservationResponse.from(observation);
    }

    public void delete(Long id) {
        repository.delete(findById(id));
    }

    private CallObservation findById(Long id) {
        return repository.findById(id)
                .orElseThrow(() -> new BusinessException(ErrorCode.RESOURCE_NOT_FOUND));
    }

    private CallObservationListResponse toListResponse(CallObservation observation) {
        InterventionPlan plan = observation.getContactJob().getInterventionPlan();
        JsonNode guidance = readGuidance(plan.getGuidanceJson());
        return new CallObservationListResponse(
                observation.getId(),
                observation.getContactJob().getId(),
                observation.getContactJob().getElderly().getId(),
                observation.getContactJob().getElderly().getDisplayName(),
                observation.getContactStatus(),
                observation.getShelterIntent(),
                observation.getCanMoveAlone(),
                observation.getHelpNeeded(),
                observation.getSymptomMentioned(),
                observation.getSummary(),
                observation.getConfidence(),
                observation.getEndedAt(),
                text(guidance, "actionGuidance"),
                text(guidance, "shelterRecommendationText"));
    }

    /**
     * 오래된 데이터 한 건의 형식이 어긋나더라도 목록 전체가 실패하면 안 되므로, 파싱 실패는 빈 값으로 넘어갑니다.
     */
    private JsonNode readGuidance(String guidanceJson) {
        if (!StringUtils.hasText(guidanceJson)) {
            return null;
        }
        try {
            return objectMapper.readTree(guidanceJson);
        } catch (RuntimeException exception) {
            return null;
        }
    }

    private String text(JsonNode node, String field) {
        if (node == null || !node.hasNonNull(field)) {
            return null;
        }
        return node.get(field).asString();
    }
}
```

주의: 이 프로젝트는 `tools.jackson`(Jackson 3) 계열을 쓴다. `asString()`이 없다는 컴파일 오류가 나면 `asText()`로 바꾼다.

- [ ] **Step 4: 컨트롤러에 GET 추가**

`CallObservationController.java`의 클래스 본문 맨 위(생성자 바로 아래)에 아래 메서드를 넣고, import를 더한다.

추가할 import:

```java
import com.nmdw.ansimon.contact.domain.ContactStatus;
import com.nmdw.ansimon.contact.dto.CallObservationListResponse;
import com.nmdw.ansimon.global.response.PageResponse;
import io.swagger.v3.oas.annotations.enums.ParameterIn;
import org.springdoc.core.annotations.ParameterObject;
import org.springframework.data.domain.Pageable;
import org.springframework.data.web.PageableDefault;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;

import java.time.LocalDate;
```

추가할 메서드:

```java
    @Operation(summary = "통화 결과 목록 조회",
            description = "저장된 통화 결과를 최신순으로 조회합니다. "
                    + "elderlyId를 주면 해당 어르신만, date를 주면 그 날짜(Asia/Seoul)에 끝난 통화만 봅니다.")
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "조회 성공"),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "400", description = "조회 조건 또는 페이지 요청값 오류")
    })
    @GetMapping
    public ApiResponse<PageResponse<CallObservationListResponse>> list(
            @Parameter(description = "어르신 식별자", example = "10", in = ParameterIn.QUERY)
            @RequestParam(required = false) Long elderlyId,
            @Parameter(description = "통화 결과 상태", example = "ANSWERED", in = ParameterIn.QUERY)
            @RequestParam(required = false) ContactStatus status,
            @Parameter(description = "통화 종료 날짜(Asia/Seoul)", example = "2026-08-19", in = ParameterIn.QUERY)
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate date,
            @ParameterObject
            @PageableDefault(size = 20) Pageable pageable) {
        return ApiResponse.success(callObservationService.search(elderlyId, status, date, pageable));
    }
```

- [ ] **Step 5: 빌드로 검증**

```bash
cd ansimon-backend && ./gradlew build
```

기대: BUILD SUCCESSFUL. JPQL이 잘못되면 스프링 컨텍스트 로딩 단계에서 기존 테스트가 실패하므로 여기서 잡힌다.

`:elderlyId is null` 에서 `Could not determine type for parameter` 오류가 나면, 해당 조건 세 개를 `(:elderlyId is null or ...)` 대신 `(cast(:elderlyId as java.lang.Long) is null or ...)` 형태로 바꾼다.

- [ ] **Step 6: 커밋**

```bash
cd ansimon-backend && git add -A && git commit -m "feat: 통화 결과 목록 조회 API 추가"
```

---

### Task 2: 현재 위험도 조회 API

**Files:**
- Create: `ansimon-backend/src/main/java/com/nmdw/ansimon/risk/dto/CurrentRiskResponse.java`
- Create: `ansimon-backend/src/main/java/com/nmdw/ansimon/risk/api/CurrentRiskController.java`
- Modify: `ansimon-backend/src/main/java/com/nmdw/ansimon/risk/infra/RiskSnapshotRepository.java`
- Modify: `ansimon-backend/src/main/java/com/nmdw/ansimon/risk/application/RiskService.java`

**Interfaces:**
- Consumes: 기존 `RiskService.forecast(RiskForecastRequest)`, `RiskSnapshot`, `RegionCodes`.
- Produces: `GET /api/v1/risk/current?region=서울` → `ApiResponse<CurrentRiskResponse>`. Task 3의 위험도 칩이 이 계약에 의존한다.

- [ ] **Step 1: 응답 DTO 생성**

`CurrentRiskResponse.java` 전체 내용:

```java
package com.nmdw.ansimon.risk.dto;

import com.nmdw.ansimon.risk.domain.RiskLevel;
import com.nmdw.ansimon.risk.domain.RiskSnapshot;
import io.swagger.v3.oas.annotations.media.Schema;

import java.math.BigDecimal;
import java.time.Instant;

/**
 * 화면이 지금 쓸 위험도 값입니다.
 * ML 호출이 실패해 지난 예측을 대신 내보낼 때는 stale이 true가 되고, 화면은 값이 오래되었음을 밝힙니다.
 */
@Schema(description = "현재 위험도")
public record CurrentRiskResponse(
        @Schema(description = "위험도 스냅샷 식별자", example = "12") Long id,
        @Schema(description = "행정구역 코드", example = "11000") String regionCode,
        @Schema(description = "위험도 점수", example = "0.8200") BigDecimal riskScore,
        @Schema(description = "위험 등급", example = "high") RiskLevel riskLevel,
        @Schema(description = "대상 시작 시각") Instant targetStartAt,
        @Schema(description = "대상 종료 시각") Instant targetEndAt,
        @Schema(description = "피크 시작 시각") Instant peakStartAt,
        @Schema(description = "피크 종료 시각") Instant peakEndAt,
        @Schema(description = "모델 버전", example = "heatwave-xgb-v1+illness-xgb-v1") String modelVersion,
        @Schema(description = "생성 시각") Instant generatedAt,
        @Schema(description = "오늘 예측이 아니라 지난 예측을 대신 내보냈는지", example = "false") boolean stale
) {
    public static CurrentRiskResponse of(RiskSnapshot snapshot, boolean stale) {
        return new CurrentRiskResponse(snapshot.getId(), snapshot.getRegionCode(), snapshot.getRiskScore(),
                snapshot.getRiskLevel(), snapshot.getTargetStartAt(), snapshot.getTargetEndAt(),
                snapshot.getPeakStartAt(), snapshot.getPeakEndAt(), snapshot.getModelVersion(),
                snapshot.getGeneratedAt(), stale);
    }
}
```

- [ ] **Step 2: 리포지토리에 오늘자 조회 추가**

`RiskSnapshotRepository.java`에 메서드 하나를 더한다. 기존 메서드는 그대로 둔다.

```java
    Optional<RiskSnapshot> findTopByRegionCodeAndGeneratedAtGreaterThanEqualOrderByGeneratedAtDesc(
            String regionCode, Instant from);
```

파일 상단에 `import java.time.Instant;`를 더한다.

- [ ] **Step 3: 서비스에 current 추가**

`RiskService.java`의 `forecast` 메서드 바로 위에 아래 메서드를 넣고, 클래스 상단 필드 옆에 리포지토리 접근은 이미 있으므로 추가 주입은 없다.

추가할 import:

```java
import com.nmdw.ansimon.global.error.ExternalServiceException;
import com.nmdw.ansimon.risk.dto.CurrentRiskResponse;
import java.util.Optional;
```

추가할 메서드:

```java
    /**
     * 화면이 부를 때마다 오늘자 예측이 있는지 확인하고, 없으면 한 번 만들어 둡니다.
     * 예방 전화(care-run)가 최신 위험도 스냅샷을 전제로 하므로, 담당자가 예측 버튼을 누르지 않아도 동작해야 합니다.
     */
    public CurrentRiskResponse current(String region) {
        String regionName = StringUtils.hasText(region) ? region : DEFAULT_REGION;
        String regionCode = RegionCodes.siDoCodeForName(regionName);
        Instant todayStart = LocalDate.now(ASIA_SEOUL).atStartOfDay(ASIA_SEOUL).toInstant();

        Optional<RiskSnapshot> today = riskSnapshotRepository
                .findTopByRegionCodeAndGeneratedAtGreaterThanEqualOrderByGeneratedAtDesc(regionCode, todayStart);
        if (today.isPresent()) {
            return CurrentRiskResponse.of(today.get(), false);
        }

        try {
            forecast(new RiskForecastRequest(regionName));
        } catch (ExternalServiceException exception) {
            // ML이 죽었다고 화면 전체가 빈손이 되면 안 되므로, 지난 예측이라도 있으면 오래되었다고 밝히고 내보냅니다.
            RiskSnapshot previous = riskSnapshotRepository
                    .findTopByRegionCodeOrderByGeneratedAtDesc(regionCode)
                    .orElseThrow(() -> exception);
            return CurrentRiskResponse.of(previous, true);
        }

        RiskSnapshot created = riskSnapshotRepository
                .findTopByRegionCodeOrderByGeneratedAtDesc(regionCode)
                .orElseThrow(() -> new BusinessException(ErrorCode.RESOURCE_NOT_FOUND));
        return CurrentRiskResponse.of(created, false);
    }
```

`ExternalServiceException`이 `RuntimeException`이 아니거나 이름이 다르면, 잡는 타입을 `RuntimeException`으로 넓히고 `BusinessException`은 다시 던지도록 바꾼다.

- [ ] **Step 4: 컨트롤러 생성**

`CurrentRiskController.java` 전체 내용:

```java
package com.nmdw.ansimon.risk.api;

import com.nmdw.ansimon.global.response.ApiResponse;
import com.nmdw.ansimon.risk.application.RiskService;
import com.nmdw.ansimon.risk.dto.CurrentRiskResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.enums.ParameterIn;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * 화면이 지금 쓸 위험도를 돌려주는 공개 조회 API입니다.
 * 수동 예측 트리거는 {@code /internal/v1/risk/forecast}에 그대로 남아 있습니다.
 */
@Tag(name = "위험도", description = "화면이 표시할 현재 위험도를 조회합니다.")
@RestController
@RequestMapping("/api/v1/risk")
public class CurrentRiskController {

    private final RiskService riskService;

    public CurrentRiskController(RiskService riskService) {
        this.riskService = riskService;
    }

    @Operation(summary = "현재 위험도 조회",
            description = "오늘자 예측이 없으면 ML에 한 번 요청해 만들어 둡니다. region을 생략하면 서울로 봅니다.")
    @GetMapping("/current")
    public ApiResponse<CurrentRiskResponse> current(
            @Parameter(description = "지역명", example = "서울", in = ParameterIn.QUERY)
            @RequestParam(required = false) String region) {
        return ApiResponse.success(riskService.current(region));
    }
}
```

- [ ] **Step 5: 빌드하고 커밋**

```bash
cd ansimon-backend && ./gradlew build && git add -A && git commit -m "feat: 현재 위험도 조회 API 추가"
```

---

### Task 3: 대시보드 축소

**Files:**
- Modify: `ansimon_front_end/index.html`

**Interfaces:**
- Consumes: Task 1의 `GET /api/v1/contact/observations`, Task 2의 `GET /api/v1/risk/current`, 기존 `GET /api/v1/elderly`.
- Produces: 없음 (화면).

- [ ] **Step 1: 마크업 삭제**

`index.html`의 `<body>` 안에서 아래를 통째로 지운다.

- `<div class="src-banner" id="src-banner" ...>` 한 줄
- `<!-- ══ 히어로 ══ -->` 부터 `</section>` 까지 (`<section class="hero reveal">` 전체 — 헤드라인, `#ml-risk` 카드, `#figs`, `.ribbon-head`, `<figure class="ribbon">`)
- `<!-- ══ 어두운 카드: 오늘 전화 42통 ══ -->` 부터 그 `</section>` 까지 (`<section class="card dark c5">`)
- `<!-- ══ 발신 진행 + 쉼터 ══ -->` 부터 그 `</section>` 까지 (`<section class="card c4">`)
- `<div class="modal" id="elder-modal" ...>` 부터 그 `</div>` 까지 (모달 전체)

남는 것: `<nav>`, `<div class="grid">` 안의 "1차 대시보드" 카드와 "통화 기록" 카드, `<footer class="foot">`, `<div class="toast" id="toast">`.

- [ ] **Step 2: 통화 기록 카드 헤더 정리**

"통화 기록" 카드의 `<div class="end">` 안 버튼 두 개(`전체 42건`, `CSV`)를 지우고 상태 필터와 페이지 버튼으로 바꾼다.

```html
        <div class="end">
          <select id="obs-status" aria-label="통화 상태 필터">
            <option value="">전체 상태</option>
            <option value="ANSWERED">응답 완료</option>
            <option value="UNCONFIRMED">미응답</option>
            <option value="COMPLETED">완료</option>
            <option value="ACTION_REQUIRED">조치 필요</option>
          </select>
          <button class="pill-btn" id="obs-prev" type="button">이전</button>
          <span class="mono" id="obs-page" style="font-size:12px;color:var(--ink-3)">—</span>
          <button class="pill-btn" id="obs-next" type="button">다음</button>
        </div>
```

- [ ] **Step 3: 어르신 목록 카드 헤더에 위험도 출처 한 줄 추가**

"1차 대시보드" 카드 헤더의 `<p>` 바로 아래에 넣는다.

```html
          <p class="mono" id="risk-source" style="font-size:11.5px;color:var(--ink-3)">위험도 불러오는 중…</p>
```

- [ ] **Step 4: 스크립트 교체**

`<script>` 블록에서 아래를 지운다: `MOCK.today` / `MOCK.heat` / `MOCK.calls` / `MOCK.flow` / `MOCK.shelters`, `MOCK_ONLY`, `SOURCE` · `markSource` · 출처 배너 렌더, 리본·점그리드·플로우·쉼터·figs 렌더 함수, ML 위험도 렌더와 `#ml-refresh` 핸들러, 모달 열기·닫기 관련 전부.

남기고 고칠 것: `API_BASE`, `ENDPOINTS`, 어르신 목록 로드·렌더, care-run 실행. `ENDPOINTS`를 아래로 바꾼다.

```javascript
const ENDPOINTS = {
  elders      : "/api/v1/elderly?page=0&size=50&sort=id,desc",
  currentRisk : "/api/v1/risk/current",
  observations: (params)=>`/api/v1/contact/observations?${params.toString()}`,
  careRun     : (elderlyId)=>`/internal/v1/guidance/care-runs/${encodeURIComponent(elderlyId)}`,
};
```

그리고 아래 코드를 스크립트 끝부분(어르신 목록 로드 다음)에 넣는다.

```javascript
/* ── 오늘 날짜: 브라우저 시간대가 아니라 서울 기준으로 잡습니다 ── */
function seoulToday(){
  return new Intl.DateTimeFormat("en-CA", { timeZone:"Asia/Seoul" }).format(new Date());
}

/* ── 현재 위험도 ──
   지역 단위 예측이라 모든 어르신이 같은 값을 답니다. 그래서 헤더에 출처를 한 번 밝힙니다. */
let currentRisk = null;
async function loadRisk(){
  try{
    currentRisk = await api.get(ENDPOINTS.currentRisk);
    const time = (iso)=> new Date(iso).toLocaleTimeString("ko-KR",{hour:"2-digit",minute:"2-digit"});
    $("#risk-source").textContent =
      `서울 지역 예측 ${currentRisk.riskScore} · 모델 ${currentRisk.modelVersion}`
      + ` · 피크 ${time(currentRisk.peakStartAt)}~${time(currentRisk.peakEndAt)}`
      + (currentRisk.stale ? " · 지난 예측입니다" : "");
  }catch(error){
    currentRisk = null;
    $("#risk-source").textContent = "위험도 예측을 불러오지 못했습니다.";
  }
  renderRiskChips();
}
function renderRiskChips(){
  const label = currentRisk ? `${currentRisk.riskScore} ${currentRisk.riskLevel}` : "예측 없음";
  const title = currentRisk ? `서울 지역 공통 예측값 · 피크 시간대 주의` : "";
  $$("[data-risk-chip]").forEach(chip => { chip.textContent = label; chip.title = title; });
}

/* ── 통화 기록 ── */
let obsPage = 0;
async function loadObservations(){
  const params = new URLSearchParams({ date: seoulToday(), page: String(obsPage), size: "20" });
  const status = $("#obs-status").value;
  if(status) params.set("status", status);
  const tbody = $("#rows");
  try{
    const data = await api.get(ENDPOINTS.observations(params));
    renderObservations(data);
  }catch(error){
    tbody.innerHTML = `<tr><td colspan="6">통화 기록을 불러오지 못했습니다. ${esc(error.message)}</td></tr>`;
    $("#obs-page").textContent = "—";
  }
}
function renderObservations(data){
  const rows = data.content || [];
  $("#obs-page").textContent = data.totalElements
    ? `${data.page + 1} / ${data.totalPages} · 총 ${data.totalElements}건` : "오늘 기록 없음";
  $("#obs-prev").disabled = data.page <= 0;
  $("#obs-next").disabled = data.page + 1 >= data.totalPages;
  if(!rows.length){
    $("#rows").innerHTML = '<tr><td colspan="6">오늘 통화 기록이 없습니다.</td></tr>';
    return;
  }
  $("#rows").innerHTML = rows.map(o => `
    <tr>
      <td><a href="./elderly-detail.html?id=${esc(o.elderlyId)}">${esc(o.elderlyName)}</a></td>
      <td>${esc(CONTACT_LABEL[o.contactStatus] || o.contactStatus)}</td>
      <td class="mono">${new Date(o.endedAt).toLocaleTimeString("ko-KR",{hour:"2-digit",minute:"2-digit"})}</td>
      <td>쉼터 ${esc(TRISTATE_LABEL[o.shelterIntent])} · 단독이동 ${esc(TRISTATE_LABEL[o.canMoveAlone])}
          · 도움 ${esc(TRISTATE_LABEL[o.helpNeeded])} · 증상 ${esc(TRISTATE_LABEL[o.symptomMentioned])}</td>
      <td>${esc(o.summary || "—")}</td>
      <td class="mono">${o.confidence ? Math.round(o.confidence * 100) + "%" : "—"}</td>
    </tr>`).join("");
}
$("#obs-status").addEventListener("change", ()=>{ obsPage = 0; loadObservations(); });
$("#obs-prev").addEventListener("click", ()=>{ if(obsPage > 0){ obsPage--; loadObservations(); } });
$("#obs-next").addEventListener("click", ()=>{ obsPage++; loadObservations(); });

loadRisk();
loadObservations();
```

- [ ] **Step 5: 어르신 행을 상세화면 링크로 바꾸기**

어르신 목록 렌더 함수에서 각 행이 모달을 열던 부분을 지우고, 이름을 상세 링크로 만들고 위험도 칩을 붙인다. 행 템플릿의 이름 칸과 우측을 아래 형태로 맞춘다.

```javascript
  `<li class="elder-row">
     <a class="elder-name" href="./elderly-detail.html?id=${esc(e.id)}">
       <span class="elder-av">${esc(avatarText(e.displayName))}</span>
       <b>${esc(e.displayName)}</b>
       <span>${esc(e.age ?? "—")}세 · ${esc(CONSENT_LABEL[e.consentStatus] || e.consentStatus)}</span>
     </a>
     <span class="risk-chip" data-risk-chip>—</span>
     <button class="pill-btn solid" type="button" data-action="call" data-id="${esc(e.id)}">자동 통화</button>
   </li>`
```

목록 렌더가 끝난 직후 `renderRiskChips();`를 호출한다. 자동 통화 버튼 핸들러에는 첫 줄에 `event.stopPropagation();`을 넣어 클릭이 링크로 번지지 않게 한다.

- [ ] **Step 6: 브라우저 확인**

백엔드를 띄운 뒤 `index.html`을 연다. 확인할 것: 카드가 두 개만 보인다 / 헤더에 위험도 출처 문구가 뜬다 / 어르신 이름 클릭 시 상세로 이동한다 / "자동 통화" 클릭 시 페이지 이동 없이 통화가 실행된다 / 통화 기록 다음·이전이 동작한다 / 콘솔에 오류가 없다.

- [ ] **Step 7: 커밋**

```bash
cd ansimon_front_end && git add -A && git commit -m "feat: 대시보드를 어르신 목록과 통화 기록 두 카드로 축소"
```

---

### Task 4: 상세화면 목업 제거

**Files:**
- Modify: `ansimon_front_end/elderly-detail.html`

**Interfaces:**
- Consumes: Task 1의 `GET /api/v1/contact/observations`, 기존 `PATCH`/`DELETE /api/v1/contact/observations/{id}`.
- Produces: 없음 (화면).

- [ ] **Step 1: 통화기록 목업 폴백 제거**

`MOCK_OBS` 상수와 `usingMockObs` 변수, `#obs-note` 경고 배너 요소를 지운다. `loadObservations`를 아래로 교체한다.

```javascript
let observations = [];
async function loadObservations(){
  const box = $("#obs-list");
  try{
    const data = await api.get(`/api/v1/contact/observations?elderlyId=${encodeURIComponent(elderlyId)}&page=0&size=20`);
    observations = data.content || [];
  }catch(error){
    observations = [];
    box.innerHTML = `<div class="empty-state">통화 기록을 불러오지 못했습니다. ${esc(error.message)}</div>`;
    renderPlan();
    return;
  }
  renderObservations();
  adoptBackendPlan();
}
```

- [ ] **Step 2: 대응계획을 읽기 전용으로**

아래를 지운다: `PLAN_KEY`, `loadLocalPlan`, `saveLocalPlan`, `clearLocalPlan`, `openPlanEdit`, `savePlanEdit`, `clearPlan`, 그리고 `#btn-plan-edit` · `#plan-cancel` · `#plan-save` · `#btn-plan-clear` 핸들러 네 개. 마크업에서도 `#plan-edit-form`과 위 버튼 네 개를 지운다.

`currentPlan` 초기화와 `renderPlan`을 아래로 바꾼다.

```javascript
/* ── 대응 계획: 통화 결과 콜백이 저장한 값을 읽기만 합니다 ── */
let currentPlan = null;

function adoptBackendPlan(){
  const latest = observations.find(o => o.actionGuidance);
  currentPlan = latest ? {
    actionGuidance: latest.actionGuidance,
    shelterRecommendationText: latest.shelterRecommendationText || "",
  } : null;
  renderPlan();
}

function renderPlan(){
  const has = !!currentPlan;
  $("#plan-empty").hidden = has;
  $("#plan-guidance-box").hidden = !has;
  $("#plan-shelter-box").hidden = !has;
  if(has){
    $("#plan-guidance").textContent = currentPlan.actionGuidance || "—";
    $("#plan-shelter").textContent = currentPlan.shelterRecommendationText || "—";
  }
}
renderPlan();
```

`#plan-empty`의 문구를 "아직 통화가 없어 대응 계획이 만들어지지 않았습니다. 자동 통화를 실행하면 생성됩니다."로 바꾼다.

- [ ] **Step 3: 통화기록 카드 문구 정리**

카드 설명에서 "요약과 판정 항목을 바로 교정할 수 있습니다."는 그대로 두고, 삭제한 경고 배너 자리를 비운다. 요약 수정·삭제 UI(`saveObservation`, `deleteObservation`, `#obs-list` 클릭 핸들러)는 손대지 않는다.

- [ ] **Step 4: 브라우저 확인**

`elderly-detail.html?id=<실제 id>`를 연다. 확인할 것: 통화 기록이 실제 데이터로 뜬다 / "요약 수정" → 저장 후 값이 반영된다 / 대응 계획이 읽기 전용으로 뜨고 편집 버튼이 없다 / 통화가 없는 어르신은 빈 상태 문구가 뜬다 / 콘솔에 오류가 없다.

- [ ] **Step 5: 커밋**

```bash
cd ansimon_front_end && git add -A && git commit -m "feat: 상세화면 통화기록을 실 API에 연결하고 대응계획을 읽기 전용으로 전환"
```

---

## 검증 최소화로 남은 위험

의뢰에 따라 새 자동 테스트를 두지 않았다. 아래 세 가지는 이번에 검증되지 않은 채로 나간다. 여유가 생기면 이 순서로 테스트를 채우는 것을 권한다.

1. **KST 날짜 경계** — 대시보드가 자정 전후로 엉뚱한 날의 기록을 보여줄 수 있다. (`CallObservationService.search`)
2. **`guidanceJson` 파싱 폴백** — 깨진 JSON에서 목록 전체가 500으로 죽지 않는지 확인되지 않았다.
3. **ML 실패 시 stale 폴백** — `RiskService.current`의 예외 분기는 실제로 실행해 본 적이 없다.
