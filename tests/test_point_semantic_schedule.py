"""Semantic batch scheduler v1: 보호된 endpoint + GitHub workflow 정적 검증.

실제 GitHub Actions / Render / OpenAI 호출 없음.
"""
from __future__ import annotations

import json
import os
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from features.points.mapping.current import classify_manual as current_classify
from features.points.project import project_point_events
from features.points.routes import BATCH_TOKEN_ENV
from features.points.semantic import get_semantic_mapping
from features.points.semantic_classifier import (
    MAX_LABELS_PER_RUN,
    classify_and_store_unmapped_labels,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = PROJECT_ROOT / '.github' / 'workflows' / 'point-semantic-daily.yml'
ENDPOINT = '/internal/point-semantic-classify'
TEST_TOKEN = 'schedule-test-token-value'
TEST_MODEL = 'point-semantic-test'
AS_OF = date(2026, 8, 22)


def _record(manual_items):
    items = list(manual_items or [])
    manual_sum = sum(int(item.get('points') or 0) for item in items)
    return {
        'date': AS_OF,
        'subjects': {},
        'manual_items': items,
        'manual_points': manual_sum,
        'total_points': manual_sum,
    }


class _FakeResponse:
    def __init__(self, payload):
        self.status = 'completed'
        self.output_text = json.dumps(payload, ensure_ascii=False)


class _FakeClient:
    def __init__(self, payload=None):
        self.calls = []
        self._payload = payload if payload is not None else {'mappings': []}
        self.responses = SimpleNamespace(create=self.create)

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeResponse(self._payload)


class MaxLabelsPerRunTests(unittest.TestCase):
    def setUp(self):
        from tests.helpers import bootstrap_test_app
        self.app, self.db = bootstrap_test_app()
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.db.session.remove()
        self.db.drop_all()
        self.db.create_all()

    def tearDown(self):
        self.db.session.remove()
        self.ctx.pop()

    def test_more_than_max_candidates_only_first_100_in_one_llm_call(self):
        items = [
            {'subject': f'수수께끼표현{index:03d}', 'points': 10}
            for index in range(140)
        ]
        client = _FakeClient()
        summary = classify_and_store_unmapped_labels(
            [_record(items)], client=client, model=TEST_MODEL,
        )
        self.assertEqual(MAX_LABELS_PER_RUN, 100)
        self.assertEqual(len(client.calls), 1)
        payload = json.loads(client.calls[0]['input'])
        self.assertEqual(len(payload['labels']), 100)
        self.assertEqual(summary['candidate_count'], 140)
        self.assertEqual(summary['remaining_count'], 40)
        self.assertEqual(summary['llm_calls'], 1)

    def test_under_limit_sends_all_candidates(self):
        items = [
            {'subject': f'수수께끼표현{index:03d}', 'points': 10}
            for index in range(23)
        ]
        client = _FakeClient()
        summary = classify_and_store_unmapped_labels(
            [_record(items)], client=client, model=TEST_MODEL,
        )
        payload = json.loads(client.calls[0]['input'])
        self.assertEqual(len(payload['labels']), 23)
        self.assertEqual(summary['candidate_count'], 23)
        self.assertEqual(summary['remaining_count'], 0)

    def test_debug_script_still_uses_service(self):
        source = PROJECT_ROOT.joinpath(
            'scripts', 'debug', 'point_semantic_classify.py'
        ).read_text(encoding='utf-8')
        self.assertIn('classify_and_store_unmapped_labels', source)


class SemanticBatchEndpointTests(unittest.TestCase):
    def setUp(self):
        from tests.helpers import bootstrap_test_app
        self.app, self.db = bootstrap_test_app()
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.db.session.remove()
        self.db.drop_all()
        self.db.create_all()
        self.client = self.app.test_client()
        self._env = patch.dict(os.environ, {BATCH_TOKEN_ENV: TEST_TOKEN})
        self._env.start()

    def tearDown(self):
        self._env.stop()
        self.db.session.remove()
        self.ctx.pop()

    def _post(self, token=TEST_TOKEN, headers=None):
        merged = dict(headers or {})
        if token is not None and 'Authorization' not in merged:
            merged['Authorization'] = f'Bearer {token}'
        return self.client.post(ENDPOINT, headers=merged)

    def _fake_summary(self, **overrides):
        summary = {
            'candidate_count': 0,
            'remaining_count': 0,
            'classified_count': 0,
            'stored_count': 0,
            'failed_count': 0,
            'llm_calls': 0,
            'error': None,
        }
        summary.update(overrides)
        return summary

    def test_post_with_valid_token_runs_service_once(self):
        with patch(
            'features.points.routes.classify_and_store_unmapped_labels',
            return_value=self._fake_summary(
                candidate_count=3, classified_count=3, stored_count=3, llm_calls=1,
            ),
        ) as service:
            response = self._post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(service.call_count, 1)
        body = response.get_json()
        self.assertEqual(body['status'], 'ok')
        self.assertEqual(body['stored_count'], 3)

    def test_get_is_rejected(self):
        with patch(
            'features.points.routes.classify_and_store_unmapped_labels'
        ) as service:
            response = self.client.get(
                ENDPOINT, headers={'Authorization': f'Bearer {TEST_TOKEN}'},
            )
        self.assertEqual(response.status_code, 405)
        self.assertEqual(service.call_count, 0)

    def test_missing_authorization_rejected(self):
        with patch(
            'features.points.routes.classify_and_store_unmapped_labels'
        ) as service:
            response = self.client.post(ENDPOINT)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(service.call_count, 0)

    def test_non_bearer_scheme_rejected(self):
        with patch(
            'features.points.routes.classify_and_store_unmapped_labels'
        ) as service:
            response = self.client.post(
                ENDPOINT, headers={'Authorization': f'Basic {TEST_TOKEN}'},
            )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(service.call_count, 0)

    def test_wrong_token_rejected(self):
        with patch(
            'features.points.routes.classify_and_store_unmapped_labels'
        ) as service:
            response = self._post(token='wrong-token')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(service.call_count, 0)

    def test_missing_server_token_env_rejected(self):
        env = {
            key: value for key, value in os.environ.items()
            if key != BATCH_TOKEN_ENV
        }
        with patch.dict(os.environ, env, clear=True):
            with patch(
                'features.points.routes.classify_and_store_unmapped_labels'
            ) as service:
                response = self._post()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(service.call_count, 0)

    def test_query_string_token_is_not_accepted(self):
        with patch(
            'features.points.routes.classify_and_store_unmapped_labels'
        ) as service:
            response = self.client.post(f'{ENDPOINT}?token={TEST_TOKEN}')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(service.call_count, 0)

    def test_zero_candidates_returns_ok_without_llm(self):
        # 빈 DB → candidate 0 → 실제 service가 그대로 200/0을 반환.
        # OPENAI_API_KEY 없이도 성공한다 = 외부 호출 0회.
        response = self._post()
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body['status'], 'ok')
        self.assertEqual(body['candidate_count'], 0)
        self.assertEqual(body['classified_count'], 0)
        self.assertEqual(body['stored_count'], 0)
        self.assertEqual(body['failed_count'], 0)

    def test_service_failure_returns_non_2xx(self):
        with patch(
            'features.points.routes.classify_and_store_unmapped_labels',
            return_value=self._fake_summary(
                candidate_count=5, failed_count=5, llm_calls=1,
                error='openai api timeout',
            ),
        ):
            response = self._post()
        self.assertEqual(response.status_code, 502)
        body = response.get_json()
        self.assertEqual(body['status'], 'failed')
        self.assertEqual(body['failed_count'], 5)

    def test_response_contains_only_aggregates(self):
        with patch(
            'features.points.routes.classify_and_store_unmapped_labels',
            return_value=self._fake_summary(
                candidate_count=2, classified_count=2, stored_count=2, llm_calls=1,
            ),
        ):
            response = self._post()
        body = response.get_json()
        self.assertEqual(
            set(body.keys()),
            {
                'status', 'candidate_count', 'classified_count',
                'stored_count', 'failed_count', 'remaining_count',
            },
        )
        blob = response.get_data(as_text=True)
        self.assertNotIn(TEST_TOKEN, blob)
        for forbidden in ('label', 'child', 'created_by', 'reason', 'api_key', 'model'):
            self.assertNotIn(forbidden, blob)

    def test_endpoint_run_does_not_change_accounting(self):
        import json as json_module
        from app import Child, DailyPoints, User, fetch_child_daily_point_records

        teacher = User(
            username='semantic_schedule_teacher',
            name='배치교사',
            role='돌봄선생님',
            email='semantic-schedule@example.test',
            password_hash='',
        )
        child = Child(name='배치아동', grade=3, viewer_slug='ssssssssssssssssssssssss')
        self.db.session.add_all([teacher, child])
        self.db.session.commit()
        history = json_module.dumps(
            [{'subject': '수수께끼표현', 'points': 300}], ensure_ascii=False,
        )
        self.db.session.add(DailyPoints(
            child_id=child.id,
            date=AS_OF,
            korean_points=200,
            math_points=0,
            ssen_points=0,
            reading_points=0,
            piano_points=0,
            english_points=0,
            advanced_math_points=0,
            writing_points=0,
            manual_points=300,
            manual_history=history,
            total_points=500,
            created_by=teacher.id,
        ))
        self.db.session.commit()

        records_before = fetch_child_daily_point_records(child.id)
        events_before = project_point_events(
            records_before, classify_manual=current_classify,
        )
        amounts_before = sorted(event.amount for event in events_before)

        fake_client = _FakeClient({'mappings': [{
            'label': '수수께끼표현',
            'category': 'EXTRA_LEARNING',
            'subject_key': None,
            'item_key': None,
        }]})

        def run_with_fake_client(records, **kwargs):
            return classify_and_store_unmapped_labels(
                records, client=fake_client, model=TEST_MODEL,
            )

        with patch(
            'features.points.routes.classify_and_store_unmapped_labels',
            side_effect=run_with_fake_client,
        ):
            response = self._post()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['stored_count'], 1)
        self.assertEqual(len(fake_client.calls), 1)
        self.assertEqual(
            get_semantic_mapping('수수께끼표현').category, 'EXTRA_LEARNING',
        )

        records_after = fetch_child_daily_point_records(child.id)
        events_after = project_point_events(
            records_after, classify_manual=current_classify,
        )
        amounts_after = sorted(event.amount for event in events_after)
        self.assertEqual(amounts_after, amounts_before)
        self.assertEqual(
            [row['total_points'] for row in records_after],
            [row['total_points'] for row in records_before],
        )

    def test_routes_module_has_no_session_auth_or_retry(self):
        import inspect
        import features.points.routes as module
        source = inspect.getsource(module)
        self.assertNotIn('login_required', source)
        self.assertNotIn('current_user', source)
        self.assertNotIn('retry', source.lower())
        self.assertIn('compare_digest', source)


class WorkflowStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW_PATH.read_text(encoding='utf-8')

    def test_schedule_and_manual_dispatch(self):
        self.assertIn("cron: '22 3 * * *'", self.text)
        self.assertIn("timezone: 'Asia/Seoul'", self.text)
        self.assertIn('workflow_dispatch', self.text)

    def test_minimal_permissions_and_concurrency(self):
        self.assertIn('permissions: {}', self.text)
        self.assertIn('group: point-semantic-daily', self.text)
        self.assertIn('cancel-in-progress: false', self.text)
        self.assertNotIn('write-all', self.text)

    def test_no_third_party_actions_or_checkout(self):
        self.assertNotIn('uses:', self.text)
        self.assertNotIn('actions/checkout', self.text)
        self.assertNotIn('setup-python', self.text)

    def test_secret_and_variable_references(self):
        self.assertIn('${{ secrets.POINT_SEMANTIC_BATCH_TOKEN }}', self.text)
        self.assertIn('${{ vars.POINT_SEMANTIC_BATCH_URL }}', self.text)
        # GitHub에 DB/OpenAI secret을 넣지 않는다.
        for forbidden in ('OPENAI_API_KEY', 'DATABASE_URL', 'SUPABASE', 'FIREBASE'):
            self.assertNotIn(forbidden, self.text)

    def test_retry_three_attempts_with_backoff(self):
        self.assertEqual(self.text.count('if call_endpoint; then'), 3)
        self.assertIn('sleep 300', self.text)
        self.assertIn('sleep 900', self.text)
        self.assertIn('exit 1', self.text)
        self.assertNotIn('while', self.text)

    def test_curl_flags(self):
        self.assertIn('--fail-with-body', self.text)
        self.assertIn('--max-time 120', self.text)
        self.assertIn('--request POST', self.text)
        self.assertIn('Authorization: Bearer ${BATCH_TOKEN}', self.text)

    def test_token_never_echoed(self):
        self.assertNotIn('echo "${BATCH_TOKEN}', self.text)
        self.assertNotIn('echo ${BATCH_TOKEN}', self.text)
        self.assertNotIn('set -x', self.text)
        # token은 env 주입과 Authorization header에만 등장한다.
        for line in self.text.splitlines():
            stripped = line.strip()
            if 'BATCH_TOKEN' not in line or 'secrets.' in line:
                continue
            if stripped.startswith('#'):
                continue
            self.assertTrue(
                'Authorization' in line
                or ('-z' in line and 'BATCH_TOKEN}' in line),
                msg=f'unexpected token usage: {stripped}',
            )


if __name__ == '__main__':
    unittest.main()
