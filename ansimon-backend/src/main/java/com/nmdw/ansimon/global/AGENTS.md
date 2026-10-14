# global

## Responsibility
공통 설정, 예외 처리, 공통 응답, WebClient, 스케줄러, 시간/보안 유틸리티를 관리합니다.

## Structure
```bash
global/
├── config/      # Spring 설정, WebClient, Jackson, CORS 등
├── error/       # 공통 예외, 에러 코드, 예외 핸들러
├── response/    # 공통 API 응답 포맷
├── scheduler/   # 공통 스케줄링 설정
└── util/        # 도메인에 속하지 않는 순수 유틸리티
```

## Rules
- 특정 도메인의 정책을 `global`에 넣지 않습니다.
- 외부 API용 WebClient Bean은 이곳에서 만들고, 도메인별 base URL/API key는 설정 값으로 주입합니다.
- 민감정보 마스킹, 시간대(`Asia/Seoul`) 처리, 공통 에러 응답은 여기에서 일관되게 관리합니다.
