# elderly

## Responsibility
노인 프로필, 주소, 좌표, 행정동 코드, 담당 기관/담당자, 전화 수신 가능 시간, 자동전화 동의 상태를 관리합니다.

## Structure
```bash
elderly/
├── api/          # 노인 등록/조회/수정/삭제 REST API
├── application/  # 프로필 등록, 동의 변경, 주소 정규화 흐름
├── domain/       # ElderlyProfile, ConsentStatus 등 핵심 모델
├── infra/        # JPA Repository, 지오코딩 어댑터
└── dto/          # 요청/응답 DTO
```

## Rules
- 전화번호 원문 검색을 금지하고 `phone_hash`를 사용합니다.
- 자동전화 동의가 없거나 철회된 대상자는 `contact`로 넘기지 않습니다.
- 주소 변경 시 좌표와 행정구역 코드도 함께 갱신해야 합니다.
- 삭제는 잘못 등록한 대상자 정정용입니다. 안내계획·전화 작업·지원 업무 이력이 있으면 외래키 제약이 막고 409로 응답하며, 이 경우 삭제 대신 동의 철회(`WITHDRAWN`)로 관리합니다.
