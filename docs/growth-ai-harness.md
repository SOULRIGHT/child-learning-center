# Growth AI Harness

durable technical facts. Notion은 이 문서의 대상이 아니다.

- generator v1 model: `gpt-5.6-luna` (OpenAI Responses API)
- production winner: 미확정
- input: `growth_teacher_evidence_v1` only
- prompt: `growth_teacher_prompt_v1`
- output: `growth_teacher_interpretation_v1`
- `store=false`, single-turn, `reasoning.effort=low`
- no tools / search / conversation / previous_response_id
- provider boundary: `GrowthInterpretationProvider.generate(packet)`
- v1 implementation: `OpenAIGrowthInterpretationProvider`
- validator / Google Model Armor / teacher AI UI: 미구현
- B6 challenger: Gemini 2.5 Flash-Lite
- final model selection: domain eval 기반
- production Growth HTML/route는 아직 LLM을 호출하지 않는다

env:

- `OPENAI_API_KEY` (required at generate time)
- `GROWTH_AI_MODEL` (optional override)

manual smoke (synthetic packet only, instance DB 미사용):

`venv\Scripts\python.exe scripts\debug\growth_ai_smoke.py`

local smoke는 project root `.env`를 `load_dotenv(..., override=False)`로 읽는다. 이미 있는 OS/Render env가 우선이다. provider 자체는 dotenv를 읽지 않는다.
