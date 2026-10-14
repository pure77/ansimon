# ansimon-backend

NMDW(너무더워) 팀의 **안심온(ansimon)** Spring Boot API 서버입니다. 폭염 취약 노인의 위험 예측부터 안내 계획, 예방 전화, 지원 업무까지 사회복지사의 대응 흐름을 지원합니다.

## 기술 구성

- Java 21, Spring Boot 4.1.0, Gradle
- Spring MVC + WebClient
- MySQL: 서비스 도메인 데이터 및 Flyway 마이그레이션 저장소
- PostgreSQL + pgvector: Spring AI RAG 벡터 저장소(연결 시)
- OpenAI 호환 Spring AI 모델, Actuator

## 프로젝트 구조

```text
src/main/java/com/nmdw/ansimon/
├── global/      # 공통 응답, 설정, WebClient 등
├── elderly/     # 노인 프로필, 주소, 동의, 담당자
├── weather/     # 기상청 예보·특보 수집 및 최신성 판정
├── risk/        # ML 위험도 연동, 위험 스냅샷·정책 보정
├── shelter/     # 무더위쉼터 동기화·검색, TMAP 경로 캐시
├── guidance/    # Spring AI/RAG 안내 계획 생성·검증
├── contact/     # 예방 전화 작업, 재시도, 결과 콜백
├── support/     # 지원 업무 생성, 우선순위, 배정·완료
├── dispatch/    # 업무량·가용 인력·추가 인원 계산
└── dashboard/   # 대시보드 요약 및 하이라이트

src/main/resources/
├── application.yml        # 공통 설정
├── application-local.yml  # 로컬 프로필
├── application-prod.yml   # 운영 프로필
└── db/migration/mysql/    # MySQL Flyway 마이그레이션
```

세부 작업 규칙은 [AGENTS.md](AGENTS.md), 도메인별 규칙은 각 패키지의 `AGENTS.md`를 확인합니다.

## 배포 방식

배포 대상은 **Railway**이며, GitHub Actions 워크플로우([`.github/workflows/ci-cd.yml`](.github/workflows/ci-cd.yml))가 담당합니다.

1. `main` 브랜치 Pull Request 또는 `main` 푸시 시 검증 작업이 실행됩니다.
2. 검증 작업은 JDK 21에서 테스트를 수행하고 `Dockerfile`로 Docker 이미지를 빌드합니다.
3. `main` 푸시에서 검증이 성공하면 Railway CLI가 배포를 실행합니다.
4. 컨테이너는 멀티 스테이지 Docker 빌드로 JAR를 만들고 비root `spring` 사용자로 실행합니다.

배포가 실행되려면 GitHub 저장소에 아래 값이 모두 등록돼 있어야 합니다. 하나라도 없으면 워크플로우는 성공 처리되지만 `deployment skipped` 로그를 남기고 배포를 건너뜁니다.

| GitHub Actions 설정 | 용도 |
| --- | --- |
| `RAILWAY_TOKEN` (Secret) | Railway CLI 인증 |
| `RAILWAY_PROJECT_ID` (Variable) | Railway 프로젝트 식별자 |
| `RAILWAY_SERVICE_NAME` (Variable) | 배포할 Railway 서비스 이름 |
| `RAILWAY_ENVIRONMENT` (Variable) | Railway 환경 이름 |

Railway 서비스 환경변수에는 최소한 `SPRING_PROFILES_ACTIVE=prod`, `MYSQL_URL`, `MYSQL_USERNAME`, `MYSQL_PASSWORD`를 설정해야 합니다. Railway가 제공하는 `PORT`는 애플리케이션이 자동으로 우선 사용합니다. 운영 환경에서는 외부 API와 AI 기능에 필요한 키 및 URL도 함께 설정해야 합니다.

## 현재 배포 상태 (저장소 기준, 2026-08-15)

- 배포 자동화 파일과 Dockerfile은 저장소에 포함되어 있습니다.
- 현재 로컬 체크아웃 브랜치는 `develop`이며 최신 커밋은 `b794895` (`chore: verify Railway auto deployment`)입니다.
- 워크플로우는 **`main` 푸시만 Railway 배포 대상으로 삼습니다.** 따라서 현재 `develop`의 최신 커밋은 이 워크플로우만으로는 배포되지 않습니다.
- 저장소만으로는 Railway 서비스의 실제 실행 상태, 공개 URL, 또는 GitHub Actions 비밀값 등록 여부를 확인할 수 없습니다. 최종 배포 성공 여부는 GitHub Actions 실행 로그와 Railway Deployments 화면에서 확인해야 합니다.

## 로컬 실행

### 1. 준비물

- JDK 21
- Docker Desktop 등의 MySQL 실행 환경, 또는 접근 가능한 MySQL 8+ 인스턴스
- Gradle Wrapper가 저장소에 포함되어 있으므로 별도 Gradle 설치는 필요하지 않습니다. Windows에서는 `gradlew.bat`을 사용합니다.

### 2. 환경변수 설정

Run Configuration 를 통해 환경변수를 등록합니다. `.env`는 Git에서 제외되지만 Spring Boot가 자동으로 읽는 파일은 아니므로, IntelliJ의 **Run/Debug Configurations → Environment variables** 또는 OS 환경변수에 설정하세요.

```powershell
$env:SPRING_PROFILES_ACTIVE = 'local'
$env:MYSQL_URL = 'jdbc:mysql://altaria.proxy.rlwy.net:30765/ansimonTest'
$env:MYSQL_USERNAME = 'root'
$env:MYSQL_PASSWORD = '실제_비밀번호'
```

`MYSQL_URL`, `MYSQL_USERNAME`, `MYSQL_PASSWORD`를 모두 같은 실행 환경에 설정해야 합니다. Railway 운영 배포도 계속 Railway 환경변수를 사용합니다.

### 3. MySQL 준비

`ansimon` 데이터베이스와 접속 계정을 만들고, 위의 `MYSQL_*` 값과 일치시킵니다. 애플리케이션 시작 시 Flyway가 `src/main/resources/db/migration/mysql`의 스키마를 적용합니다. JPA는 `ddl-auto=validate`이므로 테이블을 직접 생성하지 않습니다.

```sql
CREATE DATABASE ansimon CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'ansimon'@'localhost' IDENTIFIED BY 'ansimon';
GRANT ALL PRIVILEGES ON ansimon.* TO 'ansimon'@'localhost';
FLUSH PRIVILEGES;
```

### 4. 실행 및 확인

```powershell
.\gradlew.bat bootRun
.\gradlew.bat test
.\gradlew.bat build
```

서버는 기본적으로 `http://localhost:8080`에서 실행됩니다. 상태 확인 주소는 `http://localhost:8080/actuator/health`입니다.

## 로컬에서 선택적으로 연결할 서비스

| 서비스 | 로컬에서 필요한 설정 | 사용하지 않을 때 |
| --- | --- | --- |
| OpenAI | `OPENAI_API_KEY` | AI 기능 호출 전까지 비워둘 수 있음 |
| pgvector | PostgreSQL/pgvector 연결 정보와 `SPRING_AI_VECTORSTORE_TYPE=pgvector` | 기본값 `none` 유지 |
| 기상청 | `KMA_API_KEY` | 기상청 실연동 기능을 호출하지 않음 |
| 무더위쉼터 | `SHELTER_API_KEY` | 쉼터 동기화 기능을 호출하지 않음 |
| TMAP | `TMAP_API_KEY` | 경로 계산 기능을 호출하지 않음 |
| ML 서버 | `ML_API_BASE_URL` | 위험도 연동 호출을 피하거나 로컬 서버 실행 |
| 안심온 커넥션 서버 | `CONNECTION_BASE_URL`, `CONNECTION_API_KEY` | care-run 호출을 피하거나 로컬 서버 실행 |

운영 키, 실제 전화번호 등 민감정보는 코드·README·Git에 저장하지 않습니다.
