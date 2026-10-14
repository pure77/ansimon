# 안심온 (Ansimon)

폭염 취약 어르신 안부 확인 서비스 통합 저장소입니다.

| 폴더 | 설명 |
|---|---|
| `ansimon-backend/` | Spring Boot 백엔드 |
| `ansimon-connection/` | RAG·전화 연결 서비스 (Python) |
| `ansimon_front_end/` | 프론트엔드 |
| `heatwave_ml_model-main/` | 폭염 위험도 예측 ML 모델 |
| `docs/` | 설계 문서 |

각 서비스 실행에 필요한 키는 `.env.example`을 복사해 `.env`로 만든 뒤 채워 넣으세요. `.env`는 저장소에 올라가지 않습니다.
