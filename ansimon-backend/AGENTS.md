# Project: ansimon-backend

## Overview
NMDW(너무더워) 팀의 안심온(ansimon) Spring Boot API 서버입니다.

안심온은 폭염 취약 노인을 관리하는 사회복지사와 관리자를 위해 위험 예측, 행동지침 생성, 무더위쉼터 추천, 예방 전화, 통화 결과 구조화, 지원 업무 생성을 연결합니다.

## Tech Stack
- Runtime: Java 21
- Framework: Spring Boot 4.1.0
- Build: Gradle
- Main Database: MySQL
- RAG Vector Database: PostgreSQL + pgvector
- ORM: Spring Data JPA
- DB Migration: Flyway
- External API Client: Spring WebClient
- AI: Spring AI 2.0.0
- LLM Provider: OpenAI-compatible Spring AI model starter
- Auth: MVP에서는 로그인/인증 기능 제외

## Project Structure
```bash
src/main/java/com/nmdw/ansimon/
├── global/      # 공통 설정, 에러, 응답, WebClient, 스케줄러
├── elderly/     # 노인 프로필, 주소, 동의, 담당자 관리
├── weather/     # 기상청 예보/특보 수집, 정규화, 최신성 판정
├── risk/        # ML 위험도 API 연동, 위험 스냅샷, 정책 보정
├── shelter/     # 무더위쉼터 동기화, 후보 검색, TMAP 경로 캐시
├── guidance/    # Spring AI 기반 LLM/RAG 안내 계획 생성/검증
├── contact/     # 외부 LLM/RAG 전화 결과 수신, 계획·전화작업·통화결과 저장
├── support/     # 지원 업무 생성, 우선순위, 배정/완료
├── dispatch/    # 업무량, 가용 인력, 추가 필요 인원 계산
└── dashboard/   # 대시보드 요약 지표와 하이라이트 조회
```

## Structure Reference Rule
파일 구조를 참고하거나 새 파일을 추가할 때는 먼저 이 루트 `AGENTS.md`를 확인하고, 작업 대상 패키지의 하위 `AGENTS.md`도 반드시 확인하세요.

예시:
- `weather` 기능을 수정할 때는 `src/main/java/com/nmdw/ansimon/weather/AGENTS.md`를 확인합니다.
- `guidance` 또는 RAG 기능을 수정할 때는 `src/main/java/com/nmdw/ansimon/guidance/AGENTS.md`를 확인합니다.
- 공통 응답, 예외, WebClient 설정을 수정할 때는 `src/main/java/com/nmdw/ansimon/global/AGENTS.md`를 확인합니다.

## API Conventions
- RESTful 설계 원칙을 따릅니다.
- 외부 공개 API 경로는 `/api/v1/**`를 사용합니다.
- 내부 배치/콜백 API 경로는 `/internal/v1/**`를 사용합니다.
- 기본 응답 형식은 아래 형태를 권장합니다.

```json
{
  "success": true,
  "data": {},
  "error": null
}
```

## Code Style Rules
- [ ] 컨트롤러는 요청/응답 변환만 담당합니다.
- [ ] 비즈니스 로직은 `application` 서비스에 둡니다.
- [ ] 핵심 상태와 정책은 `domain`에 둡니다.
- [ ] 외부 API 호출은 인터페이스와 어댑터를 분리합니다.
- [ ] 외부 API 호출에는 WebClient를 사용합니다.
- [ ] DB 변경은 Flyway 마이그레이션으로 관리합니다.
- [ ] 민감정보는 로그에 남기지 않습니다.
- [ ] 전화번호 검색은 원문이 아닌 해시 기반으로 처리합니다.
- [ ] LLM 응답은 자유 문장으로 저장하지 않고 DTO/record로 구조화해 검증합니다.
- [ ] 대응계획 생성과 전화는 외부 LLM/RAG 서버가 수행합니다. 이 서버는 발신 어댑터·재시도 스케줄러를 두지 않습니다.
- [ ] 동의가 없거나 철회된 대상자는 연락 대상 목록에서 제외합니다.

## Commands
- `./gradlew bootRun` - 개발 서버 실행
- `./gradlew test` - 테스트 실행
- `./gradlew build` - 빌드
- `./gradlew flywayMigrate` - DB 마이그레이션 실행(플러그인 추가 시)

Windows에서 Gradle Wrapper가 없으면 로컬 Gradle 설치 후 `gradle bootRun`, `gradle test`, `gradle build`를 사용합니다.

## Important Notes
- `.env`와 실제 API 키는 절대 커밋하지 않습니다.
- OpenAI, 기상청, TMAP, 전화 어댑터 키는 환경변수 또는 배포 환경 secret으로 관리합니다.
- MySQL은 서비스 데이터 저장소입니다.
- PostgreSQL + pgvector는 RAG 임베딩 검색 저장소입니다.
- 대응계획 생성부터 전화까지는 외부 LLM/RAG 서버가 수행하고, 이 서버는 결과를 받아 저장·조회·후속 업무로 연결합니다.
- 외부 서버는 완료 후 `POST /internal/v1/contact/results`로 대응계획과 통화 결과를 한 번에 전송합니다.
