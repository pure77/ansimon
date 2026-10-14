# dashboard

## Responsibility
사회복지사/관리자 화면에 필요한 위험, 통화, 지원 업무, 인력 요약 지표와 하이라이트를 제공합니다.

## Structure
```bash
dashboard/
├── api/          # 대시보드 요약 조회 API
├── application/  # 읽기 모델 조합, 하이라이트 생성
├── domain/       # DashboardSummary 등 조회 모델
├── infra/        # 도메인별 조회 Repository/Query
└── dto/          # 대시보드 응답 DTO
```

## Rules
- 상태 변경 로직을 넣지 않습니다. 대시보드는 조회와 요약만 담당합니다.
- 2회 미응답자, CRITICAL 업무, 데이터 최신성 오류를 하이라이트합니다.
- 여러 도메인의 데이터를 조합하되, 원천 상태 변경은 각 도메인 서비스에 위임합니다.
