# Growth AI Harness

durable technical facts. Notion은 이 문서의 대상이 아니다.

- generator v1 model: `gpt-5.6-luna` (OpenAI Responses API)
- production winner: 미확정
- input: `growth_teacher_evidence_v1` only
- prompt: `growth_teacher_prompt_v5`
  - v1 → v2: live probe에서 관측된 unknown citation(`plan.status`, `effective_weekdays`)과
    metric label confusion(`reading.activity_days`를 "학습 활동일"로 혼용)을 prompt에서만 보강.
    runtime semantic classifier는 두지 않는다.
  - v2 → v3: metric 낭독 금지. 반드시 핵심 변화 / 의미 / 지금 할 일 / 다음 확인.
    원인·심리·능력 추측 금지. 보상 인과 단정 금지.
  - v3 → v4: 길이 상한(insight 2문장 / interpretation 3문장). 다른 단위 숫자 한 문장 나열 금지.
  - v4 → v5: evidence_id는 packet exact copy만. `*.plan.status` 등 field name 금지.
    next_actions citation은 제안을 만든 기존 관찰 사실만.
- output: `growth_teacher_interpretation_v2`
  - required: `priority_insight`, `interpretation`, `observations`(max 3),
    `next_actions`(max 2, `conditional=true`), `next_check`
  - 각 항목 `evidence_ids.minItems=1`. v1 `summary`/`suggestions` cache는
    prompt+schema version이 `runtime_signature`에 들어가므로 재사용되지 않음
- `store=false`, single-turn, `reasoning.effort=low`
- no tools / search / conversation / previous_response_id
- provider boundary: `GrowthInterpretationProvider.generate(packet)`
- v1 implementation: `OpenAIGrowthInterpretationProvider`
- B3A deterministic factual validator: `validate_teacher_interpretation(packet, parsed_output)`
  - version: `growth_teacher_factual_validator_v2`
  - citation은 모델이 제출한 reference이며 internal reasoning provenance가 아니다
  - schema `evidence_ids.minItems=1`
  - unknown citation reject (`learning.math.plan.status` 등 field name은 id가 아님)
  - numeric/unit factual validation (cited evidence 기준. packet 어딘가의 숫자로는 정당화하지 않음)
  - unavailable != zero
  - estimated != exact (item 단위)
  - next_actions/suggestions `conditional` must be true
  - citation semantic relevance는 runtime에서 완전 검증하지 않음
  - metric semantic ambiguity는 prompt + later B5 eval
  - Dynamic evidence enum은 쓰지 않는다. runtime membership이 final-output guarantee다
- B3B safety provider: `SafetyProvider.check_response(text) -> SafetyDecision`
  - v1 implementation: `AwsBedrockGuardrailSafetyProvider` (`bedrock-runtime` `ApplyGuardrail`, `source=OUTPUT`)
  - 검사 대상은 모델이 생성한 사용자 노출 자연어만
    (`priority_insight`/`interpretation`/`next_check`/`observations`/`next_actions` text.
    v1 `summary`/`suggestions`도 호환)
  - Evidence Packet / evidence_ids / system prompt / child·center identifiers / DB data는 AWS에 보내지 않는다
  - AWS Guardrail console이 Content Filters / Denied Topics / Sensitive Information 정책을 담당한다. Python에서 욕설 목록이나 topic classifier를 복제하지 않는다
  - `action=NONE` → safe, `GUARDRAIL_INTERVENED` → reject, API/timeout/auth error → fail closed
- B4 Teacher AI Runtime / UX: `generate_teacher_growth_interpretation(...)`
  - user-triggered generation only (`[ AI 성장 해석 만들기 ]`). Growth GET은 API를 호출하지 않음
  - account/day 30 user-initiated requests (KST, 실패도 1회, cache/조회는 추가 차감 없음. 내부 regeneration 없음)
  - cache: same child + packet_hash + runtime_signature + SUCCESS
  - stale: packet hash mismatch. 과거 해석을 최신처럼 표시하지 않음
  - total deadline 20s (backend authoritative). frontend abort 21s
  - max 1 Luna generation per user request. validator/parse/provider/safety 실패 시 내부 재생성 없음.
    AWS safety API도 요청당 1회. 사용자 [다시 시도]만 새 generation + 새 20초 deadline.
  - kill switch: `GROWTH_AI_ENABLED` (default off). OFF여도 deterministic Growth는 유지
  - factual validator + AWS safety required before render
  - friendly evidence UI (raw evidence_id 비노출)
  - feedback은 DB만 저장. OpenAI/AWS로 전달하지 않음
  - AI failure never breaks deterministic Growth
  - loading presentation: 2.0s × 4 unidirectional stages, min 8s hold when generation started.
    preflight(disabled/quota/in_progress/cache)는 8s를 강제하지 않음.
    4단계 이후 1단계로 돌아가지 않음. fake % / fake completion 없음. timeout 20s 유지.
    mascot slot `data-stage=organize|interpret|verify|safety|waiting`
  - attempt diagnostics: `growth_ai_attempt` (Alembic `c3a8f17b2d01`, additive `d9e1b24c7a03` for existing tables missing `safety_categories`). generation당 최대 1 row (user request당 Luna 1회).
    validator/safety reject 출력 저장. timeout은 generated_output null 허용.
    일반 UI/API 비노출. packet/prompt/credentials/review_text 저장 금지.
    B5가 읽을 필드: status/stage/failure_code/validator_codes/safety_action/safety_categories/
    tokens/latencies
- deterministic rewards evidence (packet whitelist only):
  - exemption usage current/previous/delta + same-grade peer median/n
  - additional/manual points + event counts (reading-reward source_type 제외)
  - reading reward event points
  - recommended reading activity/completions via `ChildReading.program_type`
  - reward↔recommended 14-day before/after observational feature: 미구현
    (이벤트 시각 SOT가 start/complete/daily_points 이중 기록으로 불안정)
- Google Model Armor / secondary safety provider: 미구현
- B6 challenger: Gemini 2.5 Flash-Lite
- final model selection: domain eval 기반

future extension (미구현): Reading Qualitative는 별도 input privacy guardrail을 두고
`ApplyGuardrail(source="INPUT")`로 raw `review_text`의 PII를 ANONYMIZE한 뒤에만 LLM으로 전달하는 구조를 검토한다.
NAME detection은 책 등장인물명도 마스킹할 수 있으므로 synthetic reading-journal eval 후 정책을 확정한다.

numeric validation이 지원하는 claim: 숫자+단위 `일/권/점|포인트/쪽|페이지/건/회/명`.
cited evidence value(또는 같은 item에서 같은 단위 current/previous 차이)와 단위가 맞아야 한다.

의도적으로 지원하지 않음: 문장 속 모든 숫자, window/날짜/학년/교재명 숫자, 비율·평균 등 미식별 표현, citation 적합성 전체.

env:

- `GROWTH_AI_ENABLED` (default off. `1`/`true`/`yes`/`on`일 때만 신규 generation)
- `GROWTH_AI_MODEL` (optional override)
- `GROWTH_SAFETY_GUARDRAIL_ID` (required at safety check time)
- `GROWTH_SAFETY_GUARDRAIL_VERSION` (required at safety check time)
- `AWS_REGION` or `AWS_DEFAULT_REGION` (required when building the Bedrock client; no hardcoded default)
- AWS credentials: standard chain only (`AWS_PROFILE` local, `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` on Render). 코드가 credential을 파싱·저장하지 않는다

manual smoke (synthetic packet only, instance DB 미사용):

`venv\Scripts\python.exe scripts\debug\growth_ai_smoke.py`

5-case probe:

`venv\Scripts\python.exe scripts\debug\growth_ai_luna_probe.py`

optional Bedrock Guardrail live smoke (synthetic text 3문장, instance DB 미사용):

`venv\Scripts\python.exe scripts\debug\growth_ai_safety_smoke.py`

local smoke는 project root `.env`를 `load_dotenv(..., override=False)`로 읽는다. 이미 있는 OS/Render env가 우선이다. provider 자체는 dotenv를 읽지 않는다.
