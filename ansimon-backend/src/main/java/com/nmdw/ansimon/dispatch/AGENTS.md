# dispatch

## Responsibility
지원 업무량, 예상 처리 시간, 가용 인력, 추가 필요 인원을 계산합니다.

## Structure
```bash
dispatch/
├── api/          # 업무량/인력 요약 API
├── application/  # 업무량 계산, 추가 인력 필요 여부 산정
├── domain/       # WorkloadSummary, StaffCapacity 등
├── infra/        # staff/support 조회 어댑터
└── dto/          # 대시보드용 응답 DTO
```

## Rules
- 계산 로직은 `support` 업무 상태와 우선순위를 기준으로 합니다.
- 추정 시간은 정책 값으로 분리해 나중에 기관별 조정이 가능해야 합니다.
- 대시보드 표시에 필요한 요약값만 제공하고 업무 처리 자체는 `support`가 담당합니다.
