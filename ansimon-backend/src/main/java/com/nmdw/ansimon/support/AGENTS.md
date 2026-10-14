# support

## Responsibility
통화 결과를 바탕으로 이동 지원, 안부 확인, 수동 확인 등 사회복지사 지원 업무를 생성하고 처리 상태를 관리합니다.

## Structure
```bash
support/
├── api/          # 지원 업무 큐 조회, 배정, 완료 API
├── application/  # 업무 생성 규칙, 우선순위 산정, 처리
├── domain/       # SupportTask, SupportPriority, SupportTaskType 등
├── infra/        # JPA Repository
└── dto/          # 업무 큐/완료 요청 응답 DTO
```

## Rules
- 증상 언급은 `CRITICAL`, 이동 불가/도움 필요는 `HIGH`를 기본 우선순위로 둡니다.
- 응답 불명확과 2회 미응답은 수동 확인 업무를 생성합니다.
- 동일 원인으로 같은 대상자에게 중복 업무가 생성되지 않도록 참조 ID를 관리합니다.
