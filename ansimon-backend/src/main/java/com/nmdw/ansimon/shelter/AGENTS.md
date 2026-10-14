# shelter

## Responsibility
무더위쉼터 공공데이터를 동기화하고 위치 기반 후보 검색과 TMAP 이동시간/거리 검증을 담당합니다.

## Structure
```bash
shelter/
├── api/          # 쉼터 조회, 내부 동기화 API
├── application/  # 쉼터 동기화, 후보 선정, 경로 캐싱
├── domain/       # Shelter, ShelterRoute, OpenStatus 등
├── infra/        # 공공데이터/TMAP WebClient 어댑터, Repository
└── dto/          # 외부 API 응답 DTO, 내부 응답 DTO
```

## Rules
- 쉼터 주소, 운영상태, 좌표, 이용대상은 원천 데이터 버전과 함께 관리합니다.
- TMAP 호출 결과는 `shelter_route_cache`에 저장해 중복 호출을 줄입니다.
- 안내 계획에 들어가는 쉼터 정보는 원천 데이터와 대조 가능한 ID를 포함해야 합니다.
