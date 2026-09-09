"""QA-only fake Growth AI provider. 실서비스 경로에서 기본 사용하지 않는다."""
from __future__ import annotations

from features.growth.ai.bedrock_safety import ACTION_NONE
from features.growth.ai.prompt import GROWTH_TEACHER_PROMPT_VERSION
from features.growth.ai.provider import GenerationResult
from features.growth.ai.safety import SafetyDecision
from features.growth.ai.schema import OUTPUT_SCHEMA_VERSION
from features.growth.evidence_packet import collect_evidence_ids


class FakeGrowthInterpretationProvider:
    """live AI 호출 없이 schema-valid 해석을 반환한다."""

    def generate(self, packet, timeout_s=None) -> GenerationResult:
        evidence_id = _first_available_id(packet)
        parsed = {
            'schema_version': OUTPUT_SCHEMA_VERSION,
            'priority_insight': {
                'text': '뚜렷한 주요 변화 없음. 확인된 기록을 기준으로 현재 상태를 살펴보면 됩니다.',
                'evidence_ids': [evidence_id],
            },
            'interpretation': {
                'text': '제공된 사실만 보면 과장된 성장이나 문제를 새로 만들 필요는 없습니다.',
                'evidence_ids': [evidence_id],
            },
            'observations': [
                {
                    'text': '현재 packet에 있는 확인된 사실을 중심으로 보면 됩니다.',
                    'evidence_ids': [evidence_id],
                }
            ],
            'next_actions': [
                {
                    'text': '같은 기록을 다음 비교 시점에도 이어서 보면 좋겠습니다.',
                    'evidence_ids': [evidence_id],
                    'conditional': True,
                }
            ],
            'next_check': {
                'text': '다음 기간에도 같은 지표를 확인하면 변화가 있는지 판단하기 쉽습니다.',
                'evidence_ids': [evidence_id],
            },
        }
        return GenerationResult(
            provider='qa_fake',
            model='qa-fake-growth',
            prompt_version=GROWTH_TEACHER_PROMPT_VERSION,
            output_schema_version=OUTPUT_SCHEMA_VERSION,
            parsed_output=parsed,
            response_id='qa_fake',
            usage={'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0},
            latency_ms=1,
        )


class FakePassSafetyProvider:
    def check_response(self, text, timeout_s=None) -> SafetyDecision:
        return SafetyDecision(
            safe=True,
            provider='qa_fake_safety',
            action=ACTION_NONE,
        )


def _first_available_id(packet):
    packet = packet or {}
    supporting = packet.get('supporting_facts') or packet
    for evidence_id, node in _walk_evidence(supporting):
        if node.get('available') is not True:
            continue
        if 'peer' in evidence_id:
            continue
        if evidence_id.startswith('reading.analysis.observation'):
            continue
        return evidence_id
    for evidence_id in collect_evidence_ids(packet):
        if evidence_id:
            return evidence_id
    return 'reading.activity_days.current'


def _walk_evidence(node):
    if isinstance(node, dict):
        evidence_id = node.get('evidence_id')
        if isinstance(evidence_id, str):
            yield evidence_id, node
        for item in node.values():
            yield from _walk_evidence(item)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_evidence(item)
