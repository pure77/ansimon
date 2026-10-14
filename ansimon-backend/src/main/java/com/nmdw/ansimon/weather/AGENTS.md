# weather

## Responsibility
기상청 단기예보, 초단기예보, 특보 데이터를 수집하고 정규화하며 데이터 최신성을 판정합니다.

## Structure
```bash
weather/
├── api/          # 내부 수동 동기화 API
├── application/  # 수집, 정규화, 최신성 판정
├── domain/       # WeatherForecast, WeatherSyncStatus 등
├── infra/        # KMA WebClient 어댑터, JPA Repository
└── dto/          # 기상청 응답 DTO, 내부 응답 DTO
```

## Rules
- 발표시각과 예보대상시각을 분리해서 저장합니다.
- 모든 시각은 `Asia/Seoul` 기준으로 다룹니다.
- 최신 데이터가 만료되면 자동전화 승인 제한에 필요한 상태를 제공해야 합니다.
