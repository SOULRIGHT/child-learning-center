# Growth AI Harness

durable technical facts. Notion은 이 문서의 대상이 아니다.

- generator v1 model: `gpt-5.6-luna` (OpenAI Responses API)
- production winner: 미확정
- input: `growth_teacher_evidence_v1` only
- prompt: `growth_teacher_prompt_v2`
  - v1 → v2: live probe에서 관측된 unknown citation(`plan.status`, `effective_weekdays`)과
    metric label confusion(`reading.activity_days`를 "학습 활동일"로 혼용)을 prompt에서만 보강.
    runtime semantic classifier는 두지 않는다.
- output: `growth_teacher_interpretation_v1`
- `store=false`, single-turn, `reasoning.effort=low`
- no tools / search / conversation / previous_response_id
- provider boundary: `GrowthInterpretationProvider.generate(packet)`
- v1 implementation: `OpenAIGrowthInterpretationProvider`
- B3A deterministic factual validator: `validate_teacher_interpretation(packet, parsed_output)`
  - citation은 모델이 제출한 reference이며 internal reasoning provenance가 아니다
  - schema `evidence_ids.minItems=1`
  - unknown citation reject (`learning.math.plan.status` 등 field name은 id가 아님)
  - numeric/unit factual validation (cited evidence 기준. packet 어딘가의 숫자로는 정당화하지 않음)
  - unavailable != zero
  - estimated != exact (item 단위)
  - suggestion `conditional` must be true
  - citation semantic relevance는 runtime에서 완전 검증하지 않음
  - metric semantic ambiguity는 prompt + later B5 eval
  - Dynamic evidence enum은 쓰지 않는다. runtime membership이 final-output guarantee다
- B3B safety provider: `SafetyProvider.check_response(text) -> SafetyDecision`
  - v1 implementation: `AwsBedrockGuardrailSafetyProvider` (`bedrock-runtime` `ApplyGuardrail`, `source=OUTPUT`)
  - 검사 대상은 모델이 생성한 사용자 노출 자연어만 (`summary.text` + `observations[].text` + `suggestions[].text`)
  - Evidence Packet / evidence_ids / system prompt / child·center identifiers / DB data는 AWS에 보내지 않는다
  - AWS Guardrail console이 Content Filters / Denied Topics / Sensitive Information 정책을 담당한다. Python에서 욕설 목록이나 topic classifier를 복제하지 않는다
  - `action=NONE` → safe, `GUARDRAIL_INTERVENED` → reject, API/timeout/auth error → fail closed
  - retry / rate limit / production route 연결 없음
- Google Model Armor / secondary safety provider / teacher AI UI: 미구현
- B6 challenger: Gemini 2.5 Flash-Lite
- final model selection: domain eval 기반
- production Growth HTML/route는 아직 LLM / B3A validator / AWS Guardrails를 호출하지 않는다

future extension (미구현): Reading Qualitative는 별도 input privacy guardrail을 두고
`ApplyGuardrail(source="INPUT")`로 raw `review_text`의 PII를 ANONYMIZE한 뒤에만 LLM으로 전달하는 구조를 검토한다.
NAME detection은 책 등장인물명도 마스킹할 수 있으므로 synthetic reading-journal eval 후 정책을 확정한다.

numeric validation이 지원하는 claim: 숫자+단위 `일/권/점|포인트/쪽|페이지/건/명`.
cited evidence value(또는 같은 item에서 같은 단위 current/previous 차이)와 단위가 맞아야 한다.

의도적으로 지원하지 않음: 문장 속 모든 숫자, window/날짜/학년/교재명 숫자, 비율·평균 등 미식별 표현, citation 적합성 전체.

env:

- `OPENAI_API_KEY` (required at generate time)
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
