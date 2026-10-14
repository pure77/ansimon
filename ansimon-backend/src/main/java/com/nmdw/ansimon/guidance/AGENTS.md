# guidance

## Responsibility
노인 정보와 최신 ML 위험도를 외부 안심온 커넥션에 전달해 대응계획 생성, 전화, 통화 요약을 실행합니다.

## Structure
```bash
guidance/
├── api/           # 안내 계획 생성/조회 API
├── application/   # 컨텍스트 조립, guidance 서버 호출, 결과 검증/저장
├── domain/        # InterventionPlan, GuidanceStatus, EvidenceChunkRef 등
├── infra/
│   └── client/    # 안심온 커넥션의 care-run API를 호출하는 WebClient 어댑터
└── dto/           # 안내 계획 요청/응답 DTO
```

## Rules
- 정부/공공기관 공식 문서만 운영 지침의 RAG 근거로 사용합니다.
- LLM 응답은 JSON/DTO로 구조화하고 enum, 필수 필드, 근거 ID를 검증합니다.
- 숫자, 주소, 운영시간, 전화번호는 LLM 결과를 신뢰하지 말고 원천 데이터와 대조합니다.
- 응급 증상 관련 문구는 자유 생성보다 승인된 고정 템플릿을 우선 사용합니다.
- 쉼터 후보 검색(TMAP 포함)은 외부 안심온 커넥션의 LLM/RAG 서버가 처리합니다. 이 패키지는 노인·위치·최신 위험도 스냅샷을 조립해 전달합니다.
- 자동전화 동의 상태를 요청에 포함하며, 커넥션은 동의가 없거나 철회된 대상자의 실행을 403으로 차단합니다.
- 통화 내용·조치 내용 요약은 이 패키지가 만들지 않습니다. 외부 서버가 전화를 마친 뒤 `contact` 패키지의 `POST /internal/v1/contact/results`로 대응계획과 함께 보내옵니다.
- `POST /internal/v1/guidance/care-runs/{elderlyId}`가 대응계획 생성부터 전화·요약까지 동기로 트리거합니다.
