"""Growth AI attempt 집계 helper. 네트워크/canonical DB 미사용."""
from __future__ import annotations

import unittest

from features.growth.ai.diagnostics import aggregate_growth_ai_logs


class GrowthAiDiagnosticsTests(unittest.TestCase):
    def test_retry_recovery_and_validator_codes(self):
        generations = [
            {'id': 1, 'status': 'SUCCESS', 'failure_code': None, 'attempt_count': 1},
            {'id': 2, 'status': 'FAILED', 'failure_code': 'VALIDATOR_REJECT', 'attempt_count': 2},
            {'id': 3, 'status': 'SUCCESS', 'failure_code': None, 'attempt_count': 2},
            {'id': 4, 'status': 'PENDING', 'failure_code': None, 'attempt_count': 1, 'created_at': '2026-09-01'},
        ]
        attempts = [
            {'id': 1, 'generation_id': 1, 'attempt_number': 1, 'status': 'SUCCESS', 'stage': 'safety'},
            {
                'id': 2, 'generation_id': 2, 'attempt_number': 1, 'status': 'VALIDATOR_REJECT',
                'stage': 'validator', 'failure_code': 'VALIDATOR_REJECT',
                'validator_codes': '["UNKNOWN_EVIDENCE_ID"]',
                'validator_issues': '[{"code":"UNKNOWN_EVIDENCE_ID","evidence_id":"learning.math.plan.status"}]',
                'generated_output': '{"next_actions":[{"text":"plan status를 확인하세요."}]}',
            },
            {
                'id': 3, 'generation_id': 2, 'attempt_number': 2, 'status': 'TIMEOUT',
                'stage': 'generator', 'failure_code': 'TIMEOUT',
            },
            {
                'id': 4, 'generation_id': 3, 'attempt_number': 1, 'status': 'VALIDATOR_REJECT',
                'stage': 'validator', 'failure_code': 'VALIDATOR_REJECT',
                'validator_codes': '["UNIT_MISMATCH"]',
            },
            {'id': 5, 'generation_id': 3, 'attempt_number': 2, 'status': 'SUCCESS', 'stage': 'safety'},
        ]
        stats = aggregate_growth_ai_logs(generations, attempts)
        self.assertEqual(stats['generation_count'], 4)
        self.assertEqual(stats['final_success_count'], 2)
        self.assertEqual(stats['first_attempt_success_count'], 1)
        self.assertEqual(stats['first_attempt_fail_count'], 2)
        self.assertEqual(stats['retry_count'], 2)
        self.assertEqual(stats['retry_recovery_count'], 1)
        self.assertEqual(stats['retry_also_fail_count'], 1)
        self.assertEqual(stats['attempt_failure_buckets']['TIMEOUT'], 1)
        self.assertEqual(stats['attempt_failure_buckets']['VALIDATOR_REJECT'], 2)
        self.assertEqual(stats['unknown_evidence_id_counts']['learning.math.plan.status'], 1)
        self.assertEqual(stats['generation_proxy']['retry_recovery_count'], 1)
        self.assertEqual(stats['pending_without_attempts'][0]['generation_id'], 4)
        self.assertNotIn('child', str(stats).lower())
        self.assertNotIn('name', stats['validator_reject_samples'][0])
