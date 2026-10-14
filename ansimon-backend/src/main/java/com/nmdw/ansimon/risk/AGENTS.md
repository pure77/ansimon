# risk

## Responsibility
Python ML 추론 API를 호출하고 지역/시간대별 온열질환 발생 위험도 스냅샷을 저장합니다.

## Structure
```bash
risk/
├── api/          # 내부 위험도 예측 요청 API
├── application/  # ML 호출, 위험도 저장, 정책 보정
├── domain/       # RiskSnapshot, RiskLevel, RiskFactor 등
├── infra/        # ML WebClient 어댑터, JPA Repository
└── dto/          # ML 요청/응답 DTO
```

## Rules
- `riskScore`는 의료 진단이 아니라 예방 연락 우선순위 지표입니다.
- 모델 버전, 생성 시각, 예측 대상 구간을 항상 저장합니다.
- Spring은 ML 점수에 데이터 최신성, 개인 프로필, 기관 정책을 결합해 최종 우선순위를 계산합니다.
