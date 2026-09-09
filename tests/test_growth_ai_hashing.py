"""Canonical packet hash / runtime signature. DB/AWS 없음."""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from features.growth.ai.hashing import packet_hash, runtime_signature
from features.growth.ai.prompt import GROWTH_TEACHER_PROMPT_VERSION
from features.growth.ai.runtime import current_runtime_parts, current_runtime_signature
from features.growth.evidence_packet import build_teacher_evidence_packet


class PacketHashTests(unittest.TestCase):
    def test_same_packet_same_hash(self):
        packet = {'b': 1, 'a': {'z': 2, 'y': [3, 1]}}
        self.assertEqual(packet_hash(packet), packet_hash(packet))

    def test_key_order_does_not_change_hash(self):
        left = {'b': 1, 'a': 2}
        right = {'a': 2, 'b': 1}
        self.assertEqual(packet_hash(left), packet_hash(right))

    def test_value_change_changes_hash(self):
        left = {'reading': {'activity_days': 8}}
        right = {'reading': {'activity_days': 9}}
        self.assertNotEqual(packet_hash(left), packet_hash(right))

    def test_builder_is_deterministic(self):
        bundle = {
            'reading': {
                'as_of': '2026-12-15',
                'window_days': 30,
                'current_window': {'start': '2026-11-16', 'end': '2026-12-15'},
                'previous_window': {'start': '2026-10-17', 'end': '2026-11-15'},
                'comparable': {'reading_days': True, 'completed': True},
                'current': {'reading_days': 8, 'completed_count': 1},
                'previous': {'reading_days': 3, 'completed_count': 0},
            },
            'points': {},
            'progress': {},
            'learning': {},
            'recent_window_bests': {},
        }
        first = build_teacher_evidence_packet(bundle, grade=3)
        second = build_teacher_evidence_packet(bundle, grade=3)
        self.assertEqual(packet_hash(first), packet_hash(second))
        self.assertEqual(first['selected_insights'], second['selected_insights'])

    def test_runtime_signature_changes_with_prompt(self):
        base = {
            'generator_provider': 'openai',
            'model': 'gpt-5.6-luna',
            'prompt_version': 'growth_teacher_prompt_v2',
            'output_schema_version': 'growth_teacher_interpretation_v1',
            'factual_validator_version': 'growth_teacher_factual_validator_v1',
            'safety_provider': 'aws_bedrock_guardrail',
            'safety_guardrail_id': 'gr-alpha',
            'safety_guardrail_version': '1',
        }
        other = dict(base)
        other['prompt_version'] = 'growth_teacher_prompt_v9'
        self.assertNotEqual(runtime_signature(base), runtime_signature(other))
        self.assertEqual(GROWTH_TEACHER_PROMPT_VERSION, 'growth_teacher_prompt_v9')
        self.assertEqual(current_runtime_parts()['prompt_version'], GROWTH_TEACHER_PROMPT_VERSION)
        self.assertEqual(
            current_runtime_parts()['factual_validator_version'],
            'growth_teacher_factual_validator_v3',
        )

    def test_v2_prompt_and_schema_change_current_signature(self):
        v1 = {
            'generator_provider': 'openai',
            'model': 'gpt-5.6-luna',
            'prompt_version': 'growth_teacher_prompt_v2',
            'output_schema_version': 'growth_teacher_interpretation_v1',
            'factual_validator_version': 'growth_teacher_factual_validator_v1',
            'safety_provider': 'aws_bedrock_guardrail',
            'safety_guardrail_id': 'gr-alpha',
            'safety_guardrail_version': '1',
        }
        with patch.dict(os.environ, {
            'GROWTH_SAFETY_GUARDRAIL_ID': 'gr-alpha',
            'GROWTH_SAFETY_GUARDRAIL_VERSION': '1',
            'GROWTH_AI_MODEL': 'gpt-5.6-luna',
        }, clear=False):
            self.assertNotEqual(runtime_signature(v1), current_runtime_signature())

    def test_same_guardrail_id_and_version_same_signature(self):
        env = {
            'GROWTH_SAFETY_GUARDRAIL_ID': 'gr-alpha',
            'GROWTH_SAFETY_GUARDRAIL_VERSION': '1',
            'GROWTH_AI_MODEL': 'gpt-5.6-luna',
        }
        with patch.dict(os.environ, env, clear=False):
            first = current_runtime_signature()
            second = current_runtime_signature()
        self.assertEqual(first, second)

    def test_different_guardrail_id_same_version_different_signature(self):
        env = {
            'GROWTH_SAFETY_GUARDRAIL_VERSION': '1',
            'GROWTH_AI_MODEL': 'gpt-5.6-luna',
        }
        with patch.dict(os.environ, {**env, 'GROWTH_SAFETY_GUARDRAIL_ID': 'gr-alpha'}, clear=False):
            left = current_runtime_signature()
        with patch.dict(os.environ, {**env, 'GROWTH_SAFETY_GUARDRAIL_ID': 'gr-beta'}, clear=False):
            right = current_runtime_signature()
        self.assertNotEqual(left, right)
