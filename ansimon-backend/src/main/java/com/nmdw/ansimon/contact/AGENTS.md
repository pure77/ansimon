# contact

## Responsibility
외부 LLM/RAG 서버가 대응계획 생성과 전화를 마친 뒤 보내는 최종 결과를 받아, 안내계획·전화 작업·통화 결과를 저장합니다.

## Structure
```bash
contact/
├── api/          # 대응계획 + 통화 결과 수신 콜백 API, 통화 결과 교정/삭제 API
├── application/  # 결과 검증, 세 엔티티 동시 생성, 중복 전송 방지, 통화 결과 교정
├── domain/       # ContactJob, ContactStatus, CallObservation 등
├── infra/        # Repository
└── dto/          # 통화 결과 수신/응답 DTO
```

## Rules
- 전화 발신과 재시도는 외부 LLM/RAG 서버가 수행합니다. 이 패키지에 발신 어댑터, 발신 스케줄러, 재시도 예약, 워커 잠금을 두지 않습니다.
- 결과는 `POST /internal/v1/contact/results` 하나로 통째로 받습니다. 중간 진행 상태 갱신 API는 두지 않습니다.
- `InterventionPlan`, `ContactJob`, `CallObservation`을 한 트랜잭션으로 함께 생성합니다. 외부 서버는 내부 식별자를 몰라도 됩니다.
- 외부 서버가 부여한 `externalCallId`를 `ContactJob.idempotencyKey`로 저장해 중복 전송을 막습니다(중복은 409).
- 미응답 결과는 요약 없이 3상태 항목을 모두 `UNKNOWN`, 신뢰도를 0으로 기록합니다.
- 응답한 통화는 요약, 3상태 항목 네 개, 0~1 범위 신뢰도를 모두 갖춰야 저장합니다. LLM 결과를 그대로 믿지 않고 저장 전에 검증합니다.
- `transcriptRef`에는 녹취·전사 원문이 아니라 접근이 통제된 참조값만 저장합니다.
- 후속 지원 업무는 통화 결과의 판정값으로 결정되므로, LLM이 잘못 판단한 항목은 `PATCH /api/v1/contact/observations/{id}`로 담당자가 교정할 수 있어야 합니다.
- 통화 결과 삭제는 전화 작업을 남기므로, 같은 통화에 대한 결과를 다시 저장할 수 있습니다.
