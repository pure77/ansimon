# 이력서용 개선 로드맵 (2026-09-09)

목표: 노션 "이력서 고칠거 및 개선" 항목 4개를 **최단 시간**에 구현하면서, 이력서·포트폴리오에
"문제 → 해결 → 수치"로 쓸 수 있는 형태로 만든다.

## 0. 현재 코드 상태 (계획의 근거)

| 항목 | 현재 상태 | 근거 파일 |
| --- | --- | --- |
| TMAP 지오코딩 | 등록·수정마다 TMAP 동기 호출. 캐시·재시도·서킷브레이커·대체 제공자 없음. 주소가 같아도 재호출 | `elderly/infra/TmapGeocodingClient.java`, `elderly/application/ElderlyService.java:61` |
| 내부 API 보안 | `/internal/v1/**` 3개 컨트롤러에 인증 없음. Spring Security 미사용. 커넥션 서버가 보내는 `Idempotency-Key` 헤더는 백엔드가 읽지 않음 (`externalCallId`만 사용) | `contact/api/ContactController.java:43`, `WebClientConfig.java` |
| ML 폴백 | 직전 스냅샷 + `stale` 플래그는 구현됨. ML이 죽어 있어도 화면 진입마다 매번 ML을 다시 때림(서킷 없음). 사전 예열 스케줄러 없음(`global/scheduler` 비어 있음) | `risk/application/RiskService.java:57-83` |
| LLM/RAG 비용 | care-run은 120초 동기 블로킹. 같은 지역·같은 위험등급·같은 날이면 안내문이 거의 동일한데 매 통화마다 LLM 생성. 파이썬 쪽 캐시는 `lru_cache(maxsize=1)` 하나 | `guidance/infra/client/ConnectionClient.java`, `ansimon-connection/rag/pipeline.py:55` |
| 관측성 | Actuator health/info만 노출. Micrometer 메트릭·외부 호출 지표 없음 | `application.yml`, `build.gradle` |

관측성이 없으면 "호출 n% 감소" 같은 수치를 이력서에 못 쓴다. 그래서 메트릭을 **먼저** 넣고 나머지를 붙인다.

## 1. 우선순위와 일정 (총 7 작업일)

| 순서 | 작업 | 예상 | 이력서 가치 | 이유 |
| --- | --- | --- | --- | --- |
| P0 | Micrometer 메트릭 + Prometheus 엔드포인트 + k6 부하 스크립트 | 0.5일 | 수치의 원천 | 이후 모든 항목의 before/after를 재는 도구 |
| P1 | 지오코딩: 캐시 → 서킷브레이커 → 대체 제공자 | 2일 | 최상 | 노션 첫 항목. 비용·장애 두 질문에 한 번에 답함 |
| P2 | 내부 API 인증 (API 키 + HMAC 서명 + 재전송 방지) | 1일 | 상 | "분리했다"에서 "왜 분리했고 어떻게 지켰다"로 격상 |
| P3 | LLM 안내문 캐시 + care-run 중복 호출 차단 | 1.5일 | 상 | AI 비용 절감은 면접에서 반드시 나오는 질문 |
| P4 | ML 서킷브레이커 + 새벽 사전 예열 스케줄러 | 0.5일 | 중 | P1의 서킷브레이커를 재사용하므로 거의 공짜 |
| P5 | 수치 정리, README 아키텍처 그림, 이력서 문장 확정 | 1일 | 필수 | 안 하면 앞 6일이 이력서에 안 남음 |

> 시간이 3일밖에 없으면 P0 → P1(캐시+서킷까지) → P2 순으로 자른다. 이 셋만으로도 노션 항목 1·2가 완성된다.

---

## 2. P0. 메트릭 기반 마련 (0.5일)

**할 일**
1. `build.gradle`에 `io.micrometer:micrometer-registry-prometheus` 추가, `management.endpoints.web.exposure.include`에 `prometheus,metrics` 추가.
2. `WebClientConfig.build()`의 필터에서 `Timer`를 기록해 외부 서비스별(`tmap`, `ml`, `connection`) 호출 수·지연·실패율을 남긴다. 태그: `service`, `outcome`.
3. `scripts/k6/elderly-register.js`: 노인 등록 API를 1,000건 호출. 주소 풀은 200개로 고정해 **의도적으로 중복률 80%**를 만든다(같은 아파트 단지 어르신들이 현실이기도 함).

**결과물**: 개선 전 기준선 수치 1장 (TMAP 호출 수, p95 지연, 실패율).

---

## 3. P1. 지오코딩 서드파티 문제 해결 (2일)

노션 질문 두 개에 정확히 대응한다.

### 3-1. "트래픽이 늘어 비용이 문제라면" → 캐시 + 불필요 호출 제거 (1일)

**빠른 승리 (30분)**: `ElderlyService.update()`는 주소가 바뀌지 않아도 `hasText(address)`면 재호출한다.
기존 주소와 같으면 지오코딩을 건너뛴다. 이것만으로 수정 요청의 TMAP 호출이 대부분 사라진다.

**주소 캐시 (반나절)**
- Flyway `V4__create_geocode_cache.sql`:
  `geocode_cache(id, normalized_address VARCHAR(255) UNIQUE, latitude, longitude, region_code, provider, created_at)`
- 정규화 규칙: 공백 압축, 괄호 안 참고항목 제거, 소문자. `AddressNormalizer` 유틸 + 단위 테스트.
- `CachedGeocodingClient implements GeocodingClient` (데코레이터): DB 캐시 조회 → 없으면 위임 → 결과 저장.
  `ElderlyService`는 인터페이스만 보므로 코드 변경 없음. **이 점이 계층 분리의 효과라고 이력서에 쓴다.**
- L1 메모리 캐시는 Caffeine으로 감싸도 되지만, 트래픽 규모상 DB 캐시만으로 충분. 필요하면 나중에.

**호출 예산(선택, 1시간)**: `ansimon.external.tmap.daily-quota` 설정과 카운터. 예산 90%를 넘으면 경고 로그, 100%면 대체 제공자로 즉시 전환.

### 3-2. "TMAP 자체가 죽으면" → 서킷브레이커 + 대체 제공자 + 지연 처리 (1일)

**서킷브레이커 (반나절)**
- Spring Boot 4.1 = Spring Framework 7. `@Retryable`(스프링 내장, `@EnableResilientMethods`)로 일시 오류 재시도 1회.
- 서킷브레이커는 `io.github.resilience4j:resilience4j-circuitbreaker` **코어 라이브러리만** 직접 사용한다.
  `resilience4j-spring-boot3` 자동설정은 Boot 4 호환이 불확실하므로 붙이지 않는다.
  `CircuitBreakerRegistry` 빈 하나를 `global/resilience`에 두고 `tmap`, `ml` 이름으로 인스턴스를 꺼내 쓴다.
- 설정: 실패율 50%, 슬라이딩 윈도 10회, OPEN 유지 30초. 상태 변화는 Micrometer 게이지로 노출.

**대체 제공자 (반나절)**
- `VWorldGeocodingClient`: 국토교통부 VWorld 지오코더. 무료이고 응답에 **법정동코드가 바로 포함**되어 TMAP처럼 리버스 지오코딩 2차 호출이 필요 없다(호출 수 절반).
  대안: 카카오 로컬 API. 팀이 키를 이미 갖고 있으면 그걸 쓴다.
- `FailoverGeocodingClient`: TMAP 서킷이 OPEN이거나 예외면 VWorld로. 두 제공자의 좌표 소수점 7자리 정규화는 기존 `GeocodingResult`에서 이미 맞춰져 있음.
- 최종 체인: `Cached → Failover(Tmap ⇄ VWorld)`. 캐시에 `provider` 컬럼을 두어 어느 제공자 결과인지 추적.

**지연 처리(선택, +1일, 시간 없으면 생략)**
- 둘 다 죽었을 때 등록 자체가 막히는 게 맞는지 결정해야 한다. 현재 `latitude/longitude`가 `nullable=false`라 좌표 없이 저장이 불가능하다.
- 하려면: `geocode_status(DONE|PENDING)` 컬럼 추가, 좌표 nullable, 5분 주기 스케줄러가 PENDING을 재시도.
  쉼터 거리 계산·care-run이 좌표를 전제로 하므로 PENDING 프로필은 그 흐름에서 제외해야 한다. 영향 범위가 커서 **선택 항목**.
  이력서에서는 "설계상 트레이드오프를 검토했고, 등록 차단 대신 지연 처리로 갈 경우의 영향 범위를 문서화했다"로만 써도 충분하다.

**테스트**
- `CachedGeocodingClientTest`: 캐시 히트 시 위임 호출 0회.
- `FailoverGeocodingClientTest`: TMAP 예외 → VWorld 호출, 서킷 OPEN → TMAP 호출 없음.
- 기존 `TmapGeocodingClientTest`는 유지.

**k6 재측정**: 같은 스크립트로 TMAP 호출 수·p95 비교. 중복률 80% 시나리오면 호출 수 80% 내외 감소가 나온다.

---

## 4. P2. 내부 콜백 API 보호 (1일)

**설계**
- `spring-boot-starter-security` 추가. `SecurityFilterChain` 두 개:
  `/internal/**`는 `InternalApiKeyFilter` 통과 필수, `/api/v1/**`·Swagger·health는 현행 유지(permitAll).
- 1단계(반나절): `X-Internal-Api-Key` 헤더, `MessageDigest.isEqual`로 상수 시간 비교. 실패는 기존 `ApiResponse` 형식 401.
- 2단계(반나절): HMAC-SHA256 서명. `X-Timestamp` + 본문 해시를 서명하고, 5분 밖 타임스탬프는 거부(재전송 공격 차단).
  이미 `Idempotency-Key`가 있으니 "재전송은 서명으로 막고, 중복은 멱등키로 막는다"는 두 겹 구조가 된다.
- 커넥션 서버 `backend_client.py`에 헤더 추가(10줄). 키는 Railway 환경변수 `INTERNAL_API_KEY`.

**부수 정리(1시간)**
- `ContactController.registerCallOutcome`에서 `Idempotency-Key` 헤더를 읽어 `externalCallId`와 함께 기록한다. 헤더가 오는데 무시하는 현재 상태를 면접에서 지적받을 수 있다.
- `ContactService:70`의 `existsByIdempotencyKey → save`는 동시 요청 시 레이스가 있다. `uk_contact_idempotency_key` 유니크 제약이 이미 있으니 `DataIntegrityViolationException`을 잡아 409로 바꾸는 방어를 추가한다(`ElderlyService.delete`에 같은 패턴이 이미 있음).

**테스트**: 키 없음 401, 잘못된 키 401, 오래된 타임스탬프 401, 정상 201, `/api/v1/**`는 키 없이 200.

---

## 5. P3. LLM·RAG 비용 절감 캐시 (1.5일)

노션 메모: "무더위 안내는 이미 아는 내용이니 호출을 줄이자". 맞는 관찰이고, 어디를 캐시할지가 핵심이다.

**캐시 가능한 것과 불가능한 것을 나눈다**
- 캐시 가능: `actionGuidance`(지역·위험등급·날짜·피크시간대가 같으면 동일), 쉼터 추천 문장(가장 가까운 쉼터 id가 같으면 동일), RAG 검색 결과(질의가 같으면 동일 청크).
- 캐시 불가: 실제 통화, 통화 요약, 3상태 판정. 어르신마다 다르므로 절대 캐시하지 않는다.
  이 구분 자체가 이력서 문장이 된다.

**구현 위치: 커넥션 서버(파이썬) rag 계층 (1일)**
- `rag/pipeline.py`에 `PlanCache`: 키 = `(region_code, risk_level, target_date, peak_bucket, nearest_shelter_id)`, 값 = 안내문 + 쉼터 문장 + `evidenceDocumentIds`.
  저장소는 SQLite 파일(`rag/out/plan_cache.db`)이면 충분. TTL은 당일 자정까지.
- RAG 검색 캐시: 질의 문자열 해시 → 청크 id 목록. 임베딩 API 호출도 함께 줄어든다.
- 캐시 히트 시에도 `evidence_verifier` 검증은 저장 시점에 이미 통과했으므로 재검증 생략. 히트/미스 카운터를 로그와 `/metrics`로 노출.

**백엔드 쪽 (반나절)**
- `GuidanceService.triggerCareRun` 전에 같은 `elderlyId + riskSnapshotId`로 `ContactJob`이 이미 있으면 409. 담당자가 버튼을 두 번 눌러 통화가 두 번 나가는 사고와 LLM 비용을 동시에 막는다.
- `ConnectionClient`에도 `Idempotency-Key`(`elderlyId:riskSnapshotId:HEAT_PREVENTION_CALL`)를 백엔드가 직접 붙여 보낸다. 지금은 커넥션 서버가 임의 생성하므로 백엔드가 중복을 판단할 근거가 없다.

**측정**: 같은 지역 어르신 50명 care-run 시나리오에서 LLM 생성 호출 수 before/after. 지역·등급이 같으면 50회 → 1~3회로 줄어든다.

---

## 6. P4. ML 서킷브레이커 + 사전 예열 (0.5일)

- `RiskService.current()`는 ML이 죽어 있어도 화면 진입마다 ML을 다시 호출한다. P1의 `CircuitBreakerRegistry`에서 `ml` 인스턴스를 꺼내 `MlClient.forecast`를 감싼다. OPEN이면 즉시 폴백으로 가서 화면 응답이 타임아웃(5초)만큼 느려지는 문제가 사라진다.
- `global/scheduler/RiskPrewarmScheduler`: 매일 06:00 KST에 시·도별 `forecast()`를 미리 호출. 담당자가 출근했을 때 `stale=false` 스냅샷이 준비돼 있고, ML 호출이 요청 스레드에서 스케줄러 스레드로 옮겨간다.
- `CurrentRiskResponse`에 `generatedAt` 기준 `staleMinutes`를 추가해 화면이 "몇 시간 전 예측"인지 표시할 수 있게 한다.

---

## 7. P5. 이력서·포트폴리오 정리 (1일)

1. k6 before/after 표 1장, Grafana 또는 Prometheus 스크린샷 1장.
2. README에 외부 연동 회복탄력성 그림: `Controller → Service → GeocodingClient(인터페이스) → Cached → Failover → Tmap|VWorld`.
3. `docs/adr/` 폴더에 결정 기록 3개: 지오코딩 대체 제공자 선택, 내부 API 서명 방식, 캐시 가능 경계. 각 1페이지.

### 이력서 문장 초안 (수치는 측정 후 교체)

- **노인 프로필 API + 지오코딩**: TMAP 지오코딩을 캐시·서킷브레이커·VWorld 대체 제공자 3단으로 감싸 중복 주소 80% 시나리오에서 외부 호출 **n% 감소**, TMAP 장애 시에도 등록 성공률 **100%** 유지. 계층 분리 덕에 서비스 코드 수정 없이 데코레이터만 추가.
- **내부 API 분리·보호**: `/internal/v1/**` 콜백에 HMAC-SHA256 서명 + 타임스탬프 검증(재전송 차단)과 `Idempotency-Key` 유니크 제약(중복 차단)을 결합해 두 겹 방어. 동시 요청 레이스는 DB 제약으로 최종 차단.
- **ML 연동**: 서킷브레이커로 ML 장애 시 응답 지연 **5s → ms 단위**, 새벽 사전 예열로 요청 스레드에서 ML 호출 제거, `stale` 플래그·경과 시간으로 화면에 데이터 신선도 표시.
- **LLM·RAG 비용**: 안내문은 지역·등급·날짜 단위로 캐시하고 통화 요약은 캐시하지 않는 경계를 정의해 같은 지역 50명 통화 시 LLM 생성 호출 **50 → n회**. care-run 중복 트리거는 백엔드 멱등키로 사전 차단.

---

## 8. 체크리스트

- [ ] P0 메트릭 + k6 기준선
- [ ] P1-a update 시 동일 주소 스킵
- [ ] P1-b geocode_cache + CachedGeocodingClient
- [ ] P1-c CircuitBreakerRegistry + TMAP 적용
- [ ] P1-d VWorldGeocodingClient + FailoverGeocodingClient
- [ ] P1 k6 재측정
- [ ] P2 API 키 필터 → HMAC 서명 → 커넥션 서버 헤더 추가
- [ ] P2 Idempotency-Key 헤더 기록 + 레이스 방어
- [ ] P3 PlanCache(파이썬) + 검색 캐시
- [ ] P3 care-run 중복 차단 + 백엔드가 Idempotency-Key 전송
- [ ] P4 ML 서킷 + 예열 스케줄러
- [ ] P5 수치표·그림·ADR·이력서 문장
