# 안심온 프론트엔드

폭염 예방 돌봄 콘솔. 빌드 도구 없이 정적 HTML/CSS/JS로만 동작합니다.

## 화면

| 파일 | 화면 | 백엔드 연동 |
|---|---|---|
| `index.html` | 통합 대시보드 | ML 위험도, 어르신 목록, 안심 돌봄 실행 |
| `elderly.html` | 노인 관리 (목록·등록·수정·삭제) | 전부 실 API |
| `elderly-detail.html` | 노인 상세 (프로필, 조치 방안, 통화 기록) | 프로필 CRUD, 안심 돌봄 실행, 통화결과 수정·삭제 |

`assets/theme.css`는 세 화면이 공유하는 디자인 시스템, `assets/api.js`는 공통 fetch·토스트 헬퍼입니다.

## 실행

정적 서버로 띄웁니다 (`file://`로 열면 CORS 때문에 API 호출이 막힙니다).

```bash
python -m http.server 5500
```

그다음 `http://localhost:5500/index.html`을 엽니다.

백엔드 주소는 기본값이 `http://localhost:8080`이며, 다르면 쿼리스트링으로 바꿉니다(`?api=`는 `localhost`/`127.0.0.1`에서만 동작하고, 그 외 호스트에서는 무시됩니다).

```
http://localhost:5500/index.html?api=http://localhost:8099
```

운영 배포 시에는 `assets/config.js`에 백엔드 주소를 넣습니다(`window.ANSIMON_API_BASE`).

### 로그인

모든 화면은 관리자 로그인이 필요합니다. 토큰이 없으면 `login.html`로 이동하고, 로그인하면 원래 화면으로 돌아옵니다.
토큰은 `sessionStorage`에 보관되어 탭을 닫으면 사라집니다. 첫 관리자 계정은 백엔드 환경변수
`ADMIN_BOOTSTRAP_LOGIN_ID` / `ADMIN_BOOTSTRAP_PASSWORD`로 만듭니다(계정이 하나도 없을 때 한 번).
배포 시 `assets/config.js`의 백엔드 주소를 설정하세요. 운영 호스트에서는 `?api=`가 무시됩니다.

## 연결된 API

| 기능 | 엔드포인트 |
|---|---|
| 로그인 | `POST /api/v1/auth/login` (토큰 없이 호출, 나머지는 모두 `Authorization: Bearer`) |
| 노인 목록 | `GET /api/v1/elderly?page&size&sort&regionCode&consentStatus` |
| 노인 등록 | `POST /api/v1/elderly` |
| 노인 상세 | `GET /api/v1/elderly/{id}` |
| 노인 수정 | `PATCH /api/v1/elderly/{id}` |
| 노인 삭제 | `DELETE /api/v1/elderly/{id}` (409면 "동의 철회로 관리" 안내) |
| ML 위험도 | `POST /internal/v1/risk/forecast` (서버 간 호출 전용, 브라우저에서 호출 불가 — API 키 필요) |
| 안심 돌봄 실행 | `POST /api/v1/guidance/care-runs/{elderlyId}` |
| 통화결과 교정 | `PATCH /api/v1/contact/observations/{id}` |
| 통화결과 삭제 | `DELETE /api/v1/contact/observations/{id}` |

### 안심 돌봄 실행 (care-run)

대응계획 생성 → 예방 전화 → 요약 저장이 **한 요청 안에서 동기로** 일어납니다. 실제 전화가
끝날 때까지 기다리므로 한 건에 수십 초, 최대 2분이 걸립니다 (백엔드 커넥션 타임아웃 120초,
프론트는 130초에서 중단).

- 실행 중에는 해당 어르신 행에 경과 시간이 흐르고 버튼이 잠깁니다.
- "전체 자동 통화"는 **순차로** 돕니다. 실제 전화라 동시에 걸지 않습니다. 실행 중 버튼을 다시
  누르면 남은 건을 중지합니다.
- 자동전화에 동의하지 않은 어르신은 요청을 보내기 전에 버튼이 막힙니다.
- 오류는 코드별로 안내합니다 — `CONSENT_REQUIRED`(403), `GUIDANCE_GENERATION_BLOCKED`(422, RAG
  근거 검증 실패), `RESOURCE_NOT_FOUND`(404, 위험도 예측 먼저 필요), 502/504.

## 아직 목업인 영역

백엔드에 해당 API가 없어 목업으로 표시하며, 대시보드 상단 배너가 무엇이 실 API이고 무엇이 목업인지 항상 보여줍니다.

- 오늘 집계 / 체감온도 곡선 / 통화 기록 / 발신 진행 / 무더위쉼터 — `dashboard`·`weather`·`shelter` 컨트롤러 없음
- **노인별 통화기록 목록** — 조회 API 없음. care-run이 저장한 요약도 아직 화면에 나타나지 않습니다.
  프론트는 이미 `GET /api/v1/contact/observations?elderlyId={id}`를 호출하도록 맞춰 두었고,
  API가 뜨면 자동으로 실 데이터가 뜹니다.
  설계·구현 계획: [`ansimon-backend/docs/superpowers/plans/2026-08-19-call-observation-list-api.md`](../ansimon-backend/docs/superpowers/plans/2026-08-19-call-observation-list-api.md)
- 조치 방안 수정·삭제 — 백엔드 API 없음. 담당자가 직접 쓴 내용은 브라우저 `localStorage`에만
  저장되며, 백엔드가 저장한 조치 방안이 있으면 그쪽을 우선 표시합니다.

백엔드에 API가 생기면 각 파일 상단의 `ENDPOINTS` 상수와 `MOCK_ONLY` 목록에서 해당 키를 옮기면 됩니다.
