# 대시보드 축소 · 통화기록 조회 · 어르신 상세화면 설계

작성일 2026-08-19 · 대상 저장소 `ansimon-backend`, `ansimon_front_end`

## 1. 목적

안심온 콘솔에서 목업으로 채워져 있던 영역을 걷어내고, 실제 데이터가 있는 두 가지 —
**어르신 목록**과 **통화 기록** — 만 남긴다. 통화 기록은 지금 조회 API가 없어
상세화면에서 샘플로 표시되고 있으므로, 이번에 조회 경로를 백엔드에 만들어 화면과 연결한다.

끝난 뒤의 상태:

- 대시보드는 카드 두 개(어르신 목록 · 통화 기록)로 구성된다.
- 대시보드와 노인 관리 목록 양쪽에서 어르신을 클릭하면 같은 상세화면으로 간다.
- 상세화면은 프로필 · 대응계획 · 통화기록을 실제 데이터로 보여주고, 통화내용과 요약을 수정할 수 있다.
- 화면에서 "다시 예측" 버튼이 사라져도 자동 통화(care-run)가 깨지지 않는다.

## 2. 현재 상태

| 영역 | 현재 |
|---|---|
| `index.html` | 히어로(폭염 예측·ML 위험도·체감온도 리본), 어르신 목록, 오늘 전화 42통, 통화 기록, 발신 진행, 무더위쉼터, 상세 모달 |
| `elderly.html` | 목록 → `elderly-detail.html?id=` 링크 (이미 동작) |
| `elderly-detail.html` | 프로필 조회·수정·삭제(실 API), 통화기록(**목업 폴백**), 대응계획(**localStorage**), care-run 실행(실 API) |
| 통화기록 API | `PATCH` / `DELETE /api/v1/contact/observations/{id}` 만 존재. **목록 조회 GET 없음** |
| 대응계획 API | 없음. `InterventionPlan`은 통화 결과 콜백이 저장만 하고 읽는 경로가 없다 |
| 위험도 | `POST /internal/v1/risk/forecast` 를 히어로 버튼이 수동 호출. 스냅샷이 없으면 care-run이 `RESOURCE_NOT_FOUND` 로 실패 |

`index.html` 상단 주석이 밝히듯 `heat` / `calls` / `flow` / `shelters` 는 모두 목업이다.

## 3. 설계 결정

### 3.1 ML 위험도는 지역 단위 그대로 표시한다

ML API는 `GET /v1/forecast?region=서울&date=` 형태로 **지역·날짜당 점수 하나**를 돌려주며
나이·기저질환 같은 개인 특성을 입력받지 않는다(`heatwave_ml_model-main/api.py`).
따라서 어르신별 위험도는 만들지 않고, 지역 점수를 각 행에 동일하게 표시한다.

모든 행이 같은 숫자를 다는 것이 오해를 낳지 않도록, 목록 카드 헤더에
`서울 지역 예측 · 모델 heatwave-xgb-v1+illness-xgb-v1 · 생성 08:00` 을 한 번 명시한다.

### 3.2 대응계획은 통화기록 응답에 실어 보낸다

`InterventionPlan`은 `ContactService.registerCallOutcome` 이 `ContactJob`·`CallObservation`과
**같은 트랜잭션에서 함께** 만든다. 계획만 있고 통화가 없는 상태는 존재하지 않는다.
그러므로 대응계획 전용 엔드포인트를 따로 두지 않고 통화기록 항목에 계획 문구를 동봉한다.
엔드포인트가 하나 줄고, 상세화면의 통화기록 로드가 한 번의 호출로 끝난다.

대응계획은 **읽기 전용**이다. 지금의 localStorage 편집 기능은 제거한다.

### 3.3 위험도 스냅샷은 백엔드가 보장한다

히어로 삭제로 수동 트리거가 사라지므로, 조회 시점에 오늘자 스냅샷을 보장하는
읽기 API를 만든다. 부수 효과로 care-run의 전제조건이 항상 충족된다.

## 4. 백엔드 설계

### 4.1 통화기록 목록 조회

```
GET /api/v1/contact/observations
```

| 파라미터 | 타입 | 기본 | 설명 |
|---|---|---|---|
| `elderlyId` | Long | 없음 | 지정 시 해당 어르신만 |
| `date` | LocalDate | 없음 | 지정 시 그 날짜(Asia/Seoul) 종료분만 |
| `status` | ContactStatus | 없음 | 통화 결과 상태 필터 |
| `page` / `size` | int | 0 / 20 | `@PageableDefault(size = 20)` |

정렬은 `endedAt` 내림차순으로 고정한다. 호출자가 정렬을 바꿀 이유가 없고,
고정하면 fetch join 쿼리가 단순해진다.

- 대시보드: `?date=<오늘>&page=0&size=20`
- 상세화면: `?elderlyId=<id>&page=0&size=20` (날짜 제한 없음)

대시보드가 보내는 `<오늘>`은 브라우저 로컬 날짜가 아니라 **Asia/Seoul 기준 날짜**로 계산한다
(`Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Seoul" })`). 담당자가 다른 시간대에서 열어도
백엔드의 날짜 해석과 어긋나지 않는다.

응답은 `ApiResponse<PageResponse<CallObservationListResponse>>`.

```java
public record CallObservationListResponse(
        Long id,
        Long contactJobId,
        Long elderlyId,
        String elderlyName,
        ContactStatus contactStatus,
        TriState shelterIntent,
        TriState canMoveAlone,
        TriState helpNeeded,
        TriState symptomMentioned,
        String summary,
        BigDecimal confidence,
        Instant endedAt,
        String actionGuidance,
        String shelterRecommendationText
) {}
```

기존 `CallObservationResponse`(PATCH 응답)는 그대로 둔다. 목록은 어르신 이름과
계획 문구가 더 필요하고 `transcriptRef`는 필요 없으므로 별도 레코드로 나눈다.

**구현**

`CallObservationRepository`에 페이징 조회를 추가한다.

```java
@Query("""
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
```

`join fetch` 로 `contactJob → elderly`, `contactJob → interventionPlan` 을 한 번에 끌어와
목록 렌더링에서 N+1이 나지 않게 한다. count 쿼리는 fetch join 없이 따로 준다.

`date`는 서비스에서 Asia/Seoul 기준 `[자정, 다음날 자정)` Instant 구간으로 바꾼다.
경계 계산이 화면 숫자를 좌우하므로 서비스 테스트로 못 박는다.

`guidanceJson`은 `{"actionGuidance": ..., "shelterRecommendationText": ...}` 형태의
JSON 문자열이다(`ContactService.toPlan`). 서비스에서 `ObjectMapper`로 파싱해 두 필드로 푼다.
**파싱 실패는 예외를 던지지 않고 두 필드를 `null`로 둔다** — 옛 데이터 한 건 때문에
목록 조회 전체가 죽으면 안 된다.

`CallObservationService`에 `search(...)` 를 추가하고 `@Transactional(readOnly = true)` 를 건다.
클래스 레벨이 쓰기 트랜잭션이므로 메서드 레벨에서 덮어쓴다.

### 4.2 현재 위험도 조회

```
GET /api/v1/risk/current?region=서울
```

동작:

1. `RegionCodes.siDoCodeForName(region)` 으로 시도 코드를 얻는다.
2. 그 코드의 최신 스냅샷을 찾는다.
3. `generatedAt` 이 오늘(Asia/Seoul) 안이면 그대로 반환한다.
4. 아니면 `RiskService.forecast` 를 호출해 새로 만들고 반환한다.
5. 4가 외부 서비스 오류로 실패했는데 과거 스냅샷이 있으면, 그 스냅샷을 `stale = true` 로 반환한다.
6. 과거 스냅샷도 없으면 예외를 그대로 올린다 → 기존 `EXTERNAL_SERVICE_*` 매핑(502/504)을 탄다.

응답은 `RiskForecastResponse` 에 `stale` 만 더한 `CurrentRiskResponse` 로 낸다.
기존 `RiskForecastResponse` 는 `POST /internal/v1/risk/forecast` 가 계속 쓴다.

리포지토리에 조회 메서드를 하나 더한다.

```java
Optional<RiskSnapshot> findTopByRegionCodeAndGeneratedAtGreaterThanEqualOrderByGeneratedAtDesc(
        String regionCode, Instant from);
```

경로가 `/api/v1/...` 인 이유: 프론트가 직접 부르는 공개 조회다.
`/internal/v1/risk/forecast` 는 수동 트리거로 그대로 남긴다.

### 4.3 건드리지 않는 것

`PATCH` / `DELETE /api/v1/contact/observations/{id}` 는 이미 동작하며 상세화면이 그대로 쓴다.
`ContactService`, `GuidanceService`, 노인 CRUD API는 변경하지 않는다.

## 5. 프론트 설계

### 5.1 `index.html`

**삭제**

- `<section class="hero">` 전체 — 헤드라인, ML 위험도 카드, 체감온도 리본
- 어두운 카드 "오늘 전화 42통" (`.card.dark.c5`) — 점 그리드, 응답률, 다음 발신 안내
- "발신 진행 + 무더위쉼터" 카드 (`.card.c4`)
- 어르신 상세 모달 `#elder-modal` 전체
- 데이터 출처 배너 `#src-banner`
- 위 영역 전용 목업(`MOCK.heat` / `calls` / `flow` / `shelters` / `today`), 렌더 함수
  (리본·점 그리드·플로우·쉼터), 그리고 이들만 쓰던 CSS 규칙

**남김** — nav / 어르신 목록 / 통화 기록 / footer. 2단 그리드로 재배치한다.

**변경**

- 어르신 행 클릭 → `elderly-detail.html?id=<id>` 로 이동. 모달 경로를 없애
  `elderly.html` 과 진입 경로를 통일한다. 행의 "자동 통화" 버튼은 유지하고,
  버튼 클릭이 행 이동으로 번지지 않게 `stopPropagation` 한다.
- 각 행에 위험도 칩을 붙인다. 값은 `GET /api/v1/risk/current` 결과이며 전 행 동일하다.
  칩 툴팁에 피크 시간대(`peakStartAt`~`peakEndAt`)를 넣어, 히어로가 갖고 있던
  "오늘 몇 시가 위험한가"를 최소한만 남긴다.
- 통화 기록 테이블을 `GET /api/v1/contact/observations?date=<오늘>` 에 연결한다.
  페이지네이션과 상태 필터를 붙이고, "전체 42건" / "CSV" 같은 동작 없는 버튼은 지운다.

**로드 실패 처리** — 위험도 조회가 실패해도 목록과 통화기록은 정상 렌더한다.
칩만 "예측 없음"으로 두고, `stale = true` 면 생성 시각을 덧붙여 오래된 값임을 밝힌다.

### 5.2 `elderly-detail.html`

- 통화기록: `MOCK_OBS` 폴백과 `#obs-note` 경고 배너를 제거하고 실 API에 연결한다.
  실패는 목업으로 가리지 않고 오류 상태로 표시한다.
- 대응 계획: `PLAN_KEY` localStorage 저장·편집·삭제(`openPlanEdit` / `savePlanEdit` /
  `clearPlan` / `#plan-edit-form`)를 제거한다. 통화기록 응답의 `actionGuidance` ·
  `shelterRecommendationText` 를 읽기 전용으로 보여주고, 값이 없으면 빈 상태 문구를 둔다.
- 통화내용 · 처방 요약 수정: 기존 `PATCH` 경로와 인라인 편집 UI를 그대로 유지한다.
- care-run 실행 후 통화기록을 다시 부르는 기존 동작을 유지한다.

### 5.3 `elderly.html`

변경 없음. 이미 `elderly-detail.html?id=` 로 링크되어 있다(`elderly.html:230`).

## 6. 테스트

| 대상 | 확인할 것 |
|---|---|
| `CallObservationRepository` | 필터 조합(elderlyId / status / 날짜 구간)과 미지정 시 전체, `endedAt` 내림차순, 페이지 경계, fetch join으로 어르신·계획 접근 시 추가 쿼리 없음 |
| `CallObservationService.search` | `date` → Asia/Seoul 자정 경계 변환(전날 23:59와 당일 00:00 구분), `guidanceJson` 정상 파싱, 깨진 JSON일 때 두 필드가 `null`이고 예외가 없음 |
| `CallObservationController` | 200 응답의 페이지 형태, 잘못된 `status` 값에 400, 파라미터 전무 시 전체 조회 |
| `RiskService.current` | 오늘 스냅샷이 있으면 ML을 호출하지 않음, 없으면 호출 후 저장, ML 실패 + 과거 스냅샷 있으면 `stale = true` 반환, ML 실패 + 스냅샷 없으면 예외 전파 |
| `RiskController` | `/api/v1/risk/current` 200 응답 형태 |

DTO 레코드와 설정 클래스는 별도 테스트를 두지 않고 위 사용처 테스트로 커버한다.

프론트는 자동 테스트 없이 수동 확인한다: 대시보드 로드 → 카드 두 개만 표시,
어르신 클릭 → 상세 이동, 통화기록 페이지 넘김, 상세화면 요약 수정 후 재조회 시 반영,
백엔드를 끈 상태에서 화면이 오류 상태로 뜨고 목업으로 위장하지 않을 것.

## 7. 범위 밖

- 어르신별 개인 위험도 산출 (ML이 개인 특성을 받지 않음)
- 대응계획 수정 API
- 발신 진행 집계 · 무더위쉼터 · 체감온도 API (해당 화면을 삭제하므로 불필요)
- 통화기록 CSV 내보내기
