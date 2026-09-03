"""Semantic batch classifier. 실제 OpenAI 호출 없음."""
from __future__ import annotations

import inspect
import json
import os
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from features.points.events import (
    CATEGORY_EXTRA_LEARNING,
    CATEGORY_HELP_CONTRIBUTION,
    CATEGORY_PRAISE,
    CATEGORY_STATIONERY,
    CATEGORY_UNCLASSIFIED,
)
from features.points.mapping.current import classify_manual as current_classify
from features.points.project import accounting_parts, project_point_events
from features.points.semantic import get_semantic_mapping, upsert_semantic_mapping
from features.points.semantic_classifier import (
    MODEL_ENV,
    SYSTEM_PROMPT,
    SemanticClassifierAPIError,
    build_classifier_payload,
    classify_and_store_unmapped_labels,
    classify_unmapped_labels,
    resolve_semantic_model,
    validate_classifier_mappings,
)
from feature_models import PointSemanticMapping


AS_OF = date(2026, 8, 22)
TEST_MODEL = 'point-semantic-test'


def _record(manual_items, *, subjects=None):
    items = list(manual_items or [])
    subjects = dict(subjects or {})
    subject_sum = sum(int(value or 0) for value in subjects.values())
    manual_sum = sum(int(item.get('points') or 0) for item in items)
    return {
        'date': AS_OF,
        'subjects': subjects,
        'manual_items': items,
        'manual_points': manual_sum,
        'total_points': subject_sum + manual_sum,
    }


def _runtime(record):
    from features.points import project_current_center_events
    return project_current_center_events((record,))


class _FakeResponse:
    def __init__(self, payload):
        self.id = 'resp_semantic_test'
        self.status = 'completed'
        self.model = TEST_MODEL
        self.output_text = json.dumps(payload, ensure_ascii=False)
        self.usage = SimpleNamespace(input_tokens=1, output_tokens=1, total_tokens=2)


class _FakeClient:
    def __init__(self, payload=None, error=None):
        self.calls = []
        self._payload = payload if payload is not None else {'mappings': []}
        self._error = error
        self.responses = SimpleNamespace(create=self.create)

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return _FakeResponse(self._payload)


class SemanticClassifierPureTests(unittest.TestCase):
    def test_empty_labels_do_not_call_llm(self):
        client = _FakeClient()
        result = classify_unmapped_labels([], client=client, model=TEST_MODEL)
        self.assertEqual(result, [])
        self.assertEqual(client.calls, [])

    def test_payload_contains_only_labels(self):
        payload = build_classifier_payload(['공부 더 함', '공부더함', '센터정리함'])
        self.assertEqual(payload, {'labels': ['공부더함', '센터정리함']})
        blob = json.dumps(payload, ensure_ascii=False)
        for forbidden in ('child_id', 'created_by', 'amount', 'points', 'reason', 'count', '2026-'):
            self.assertNotIn(forbidden, blob)

    def test_invalid_category_is_dropped(self):
        mappings = validate_classifier_mappings(
            ['공부더함'],
            {'mappings': [{
                'label': '공부더함',
                'category': 'NOT_REAL',
                'subject_key': None,
                'item_key': None,
            }]},
        )
        self.assertEqual(mappings, ())

    def test_unknown_label_is_dropped(self):
        mappings = validate_classifier_mappings(
            ['공부더함'],
            {'mappings': [{
                'label': '만들어낸라벨',
                'category': CATEGORY_EXTRA_LEARNING,
                'subject_key': None,
                'item_key': None,
            }]},
        )
        self.assertEqual(mappings, ())

    def test_duplicate_identical_output_keeps_one(self):
        row = {
            'label': '공부더함',
            'category': CATEGORY_EXTRA_LEARNING,
            'subject_key': None,
            'item_key': None,
        }
        mappings = validate_classifier_mappings(['공부더함'], {'mappings': [row, dict(row)]})
        self.assertEqual(len(mappings), 1)
        self.assertEqual(mappings[0]['category'], CATEGORY_EXTRA_LEARNING)

    def test_duplicate_conflicting_output_is_dropped(self):
        mappings = validate_classifier_mappings(
            ['공부더함'],
            {'mappings': [
                {
                    'label': '공부더함',
                    'category': CATEGORY_EXTRA_LEARNING,
                    'subject_key': None,
                    'item_key': None,
                },
                {
                    'label': '공부더함',
                    'category': CATEGORY_PRAISE,
                    'subject_key': None,
                    'item_key': None,
                },
            ]},
        )
        self.assertEqual(mappings, ())

    def test_subject_key_validation(self):
        mappings = validate_classifier_mappings(
            ['수학문제더품', '문제더품'],
            {'mappings': [
                {
                    'label': '수학문제더품',
                    'category': CATEGORY_EXTRA_LEARNING,
                    'subject_key': 'math',
                    'item_key': None,
                },
                {
                    'label': '문제더품',
                    'category': CATEGORY_EXTRA_LEARNING,
                    'subject_key': 'made_up_subject',
                    'item_key': None,
                },
            ]},
        )
        by_label = {item['label']: item for item in mappings}
        self.assertEqual(by_label['수학문제더품']['subject_key'], 'math')
        self.assertIsNone(by_label['문제더품']['subject_key'])

    def test_item_key_validation(self):
        mappings = validate_classifier_mappings(
            ['연필샀음', '필기구'],
            {'mappings': [
                {
                    'label': '연필샀음',
                    'category': CATEGORY_STATIONERY,
                    'subject_key': None,
                    'item_key': 'pencil',
                },
                {
                    'label': '필기구',
                    'category': CATEGORY_STATIONERY,
                    'subject_key': None,
                    'item_key': 'notebook',
                },
            ]},
        )
        by_label = {item['label']: item for item in mappings}
        self.assertEqual(by_label['연필샀음']['item_key'], 'pencil')
        self.assertIsNone(by_label['필기구']['item_key'])

    def test_malformed_output_raises(self):
        from features.points.semantic_classifier import SemanticClassifierParseError
        with self.assertRaises(SemanticClassifierParseError):
            validate_classifier_mappings(['공부더함'], {'oops': []})
        with self.assertRaises(SemanticClassifierParseError):
            validate_classifier_mappings(['공부더함'], {'mappings': 'not-a-list'})

    def test_model_comes_from_env_not_hardcoded_gpt(self):
        import features.points.semantic_classifier as module
        self.assertNotIn('gpt-5.6', inspect.getsource(module))
        with patch.dict(os.environ, {
            MODEL_ENV: 'env-semantic-model',
            'GROWTH_AI_MODEL': 'growth-model',
        }):
            self.assertEqual(resolve_semantic_model(), 'env-semantic-model')
        env = {
            key: value for key, value in os.environ.items()
            if key != MODEL_ENV
        }
        env['GROWTH_AI_MODEL'] = 'growth-model'
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(resolve_semantic_model(), 'growth-model')

    def test_module_does_not_import_luna(self):
        import features.points.semantic_classifier as module
        source = inspect.getsource(module)
        self.assertNotIn('features.growth.ai.prompt', source)
        self.assertNotIn('features.growth.ai.runtime', source)
        self.assertNotIn('GROWTH_TEACHER_SYSTEM_PROMPT', source)
        self.assertNotIn('evidence packet', SYSTEM_PROMPT.lower())

    def test_manual_script_is_separate_from_luna(self):
        from pathlib import Path
        source = Path(__file__).resolve().parents[1].joinpath(
            'scripts', 'debug', 'point_semantic_classify.py'
        ).read_text(encoding='utf-8')
        self.assertIn('classify_and_store_unmapped_labels', source)
        self.assertNotIn('features.growth', source)
        self.assertNotIn('apscheduler', source.lower())
        self.assertNotIn('crontab', source.lower())


class SemanticClassifierStoreTests(unittest.TestCase):
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

    def test_no_candidates_skips_llm(self):
        client = _FakeClient()
        summary = classify_and_store_unmapped_labels(
            [_record([{'subject': '칭찬', 'points': 100}])],
            client=client,
            model=TEST_MODEL,
        )
        self.assertEqual(summary['candidate_count'], 0)
        self.assertEqual(summary['llm_calls'], 0)
        self.assertEqual(client.calls, [])
        self.assertEqual(PointSemanticMapping.query.count(), 0)

    def test_multiple_labels_one_batch(self):
        client = _FakeClient({'mappings': [
            {'label': '공부더함', 'category': CATEGORY_EXTRA_LEARNING, 'subject_key': None, 'item_key': None},
            {'label': '센터정리함', 'category': CATEGORY_HELP_CONTRIBUTION, 'subject_key': None, 'item_key': None},
        ]})
        summary = classify_and_store_unmapped_labels(
            [_record([
                {'subject': '공부 더 함', 'points': 300},
                {'subject': '센터정리함', 'points': 100},
            ])],
            client=client,
            model=TEST_MODEL,
        )
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(summary['llm_calls'], 1)
        payload = json.loads(client.calls[0]['input'])
        self.assertEqual(sorted(payload['labels']), ['공부더함', '센터정리함'])
        self.assertEqual(summary['stored_count'], 2)
        self.assertEqual(PointSemanticMapping.query.count(), 2)

    def test_unclassified_is_stored_and_excluded_next_time(self):
        client = _FakeClient({'mappings': [{
            'label': '추가점수',
            'category': CATEGORY_UNCLASSIFIED,
            'subject_key': None,
            'item_key': None,
        }]})
        records = [_record([{'subject': '추가점수', 'points': 500}])]
        first = classify_and_store_unmapped_labels(records, client=client, model=TEST_MODEL)
        self.assertEqual(first['stored_count'], 1)
        self.assertEqual(get_semantic_mapping('추가점수').category, CATEGORY_UNCLASSIFIED)
        client.calls.clear()
        second = classify_and_store_unmapped_labels(records, client=client, model=TEST_MODEL)
        self.assertEqual(second['candidate_count'], 0)
        self.assertEqual(second['llm_calls'], 0)
        self.assertEqual(client.calls, [])

    def test_invalid_category_not_stored(self):
        client = _FakeClient({'mappings': [{
            'label': '공부더함',
            'category': 'MAGIC',
            'subject_key': None,
            'item_key': None,
        }]})
        summary = classify_and_store_unmapped_labels(
            [_record([{'subject': '공부더함', 'points': 200}])],
            client=client,
            model=TEST_MODEL,
        )
        self.assertEqual(summary['stored_count'], 0)
        self.assertEqual(PointSemanticMapping.query.count(), 0)

    def test_unknown_label_in_response_not_stored(self):
        client = _FakeClient({'mappings': [
            {
                'label': '공부더함',
                'category': CATEGORY_EXTRA_LEARNING,
                'subject_key': None,
                'item_key': None,
            },
            {
                'label': '만들어낸라벨',
                'category': CATEGORY_EXTRA_LEARNING,
                'subject_key': None,
                'item_key': None,
            },
        ]})
        summary = classify_and_store_unmapped_labels(
            [_record([{'subject': '공부더함', 'points': 200}])],
            client=client,
            model=TEST_MODEL,
        )
        self.assertEqual(summary['stored_count'], 1)
        self.assertIsNotNone(get_semantic_mapping('공부더함'))
        self.assertIsNone(get_semantic_mapping('만들어낸라벨'))

    def test_duplicate_model_output_stores_once(self):
        row = {
            'label': '공부더함',
            'category': CATEGORY_EXTRA_LEARNING,
            'subject_key': None,
            'item_key': None,
        }
        client = _FakeClient({'mappings': [row, dict(row)]})
        summary = classify_and_store_unmapped_labels(
            [_record([{'subject': '공부더함', 'points': 200}])],
            client=client,
            model=TEST_MODEL,
        )
        self.assertEqual(summary['stored_count'], 1)
        self.assertEqual(PointSemanticMapping.query.count(), 1)

    def test_malformed_response_stores_nothing(self):
        client = _FakeClient({'not_mappings': []})
        summary = classify_and_store_unmapped_labels(
            [_record([{'subject': '공부더함', 'points': 200}])],
            client=client,
            model=TEST_MODEL,
        )
        self.assertEqual(summary['stored_count'], 0)
        self.assertEqual(summary['failed_count'], 1)
        self.assertIsNotNone(summary['error'])
        self.assertEqual(PointSemanticMapping.query.count(), 0)

    def test_api_exception_does_not_change_existing(self):
        upsert_semantic_mapping('이미있음', CATEGORY_HELP_CONTRIBUTION)
        self.db.session.commit()
        before = PointSemanticMapping.query.count()
        record = _record(
            [{'subject': '공부더함', 'points': 300}],
            subjects={'korean': 200},
        )
        before_events = project_point_events((record,), classify_manual=current_classify)
        client = _FakeClient(error=RuntimeError('network down'))
        summary = classify_and_store_unmapped_labels([record], client=client, model=TEST_MODEL)
        self.assertEqual(summary['stored_count'], 0)
        self.assertEqual(summary['failed_count'], 1)
        self.assertEqual(summary['llm_calls'], 1)
        self.assertIsNotNone(summary['error'])
        self.assertEqual(PointSemanticMapping.query.count(), before)
        self.assertEqual(get_semantic_mapping('이미있음').category, CATEGORY_HELP_CONTRIBUTION)
        after_events = project_point_events((record,), classify_manual=current_classify)
        self.assertEqual(
            [event.amount for event in after_events],
            [event.amount for event in before_events],
        )

    def test_existing_semantic_and_deterministic_excluded_from_payload(self):
        upsert_semantic_mapping('이미매핑', CATEGORY_HELP_CONTRIBUTION)
        self.db.session.commit()
        client = _FakeClient({'mappings': [{
            'label': '공부더함',
            'category': CATEGORY_EXTRA_LEARNING,
            'subject_key': None,
            'item_key': None,
        }]})
        classify_and_store_unmapped_labels(
            [_record([
                {'subject': '칭찬', 'points': 100},
                {'subject': '이미매핑', 'points': 50},
                {'subject': '공부더함', 'points': 300},
            ])],
            client=client,
            model=TEST_MODEL,
        )
        payload = json.loads(client.calls[0]['input'])
        self.assertEqual(payload['labels'], ['공부더함'])
        blob = json.dumps(client.calls[0], ensure_ascii=False)
        self.assertNotIn('child_id', blob)
        self.assertNotIn('created_by', blob)
        self.assertNotIn('300', blob)

    def test_accounting_unchanged_after_semantic_store(self):
        record = _record(
            [{'subject': '공부 더 함', 'points': 300}],
            subjects={'korean': 200},
        )
        before = project_point_events((record,), classify_manual=current_classify)
        self.assertEqual(before[1].category, CATEGORY_UNCLASSIFIED)
        client = _FakeClient({'mappings': [{
            'label': '공부더함',
            'category': CATEGORY_EXTRA_LEARNING,
            'subject_key': None,
            'item_key': None,
        }]})
        classify_and_store_unmapped_labels([record], client=client, model=TEST_MODEL)
        after = _runtime(record)
        self.assertEqual(after[1].category, CATEGORY_EXTRA_LEARNING)
        self.assertEqual(after[1].amount, before[1].amount)
        self.assertEqual(sum(event.amount for event in after), sum(event.amount for event in before))
        self.assertTrue(accounting_parts(record, after)['balanced'])

    def test_one_batch_kwargs_use_semantic_prompt_not_luna(self):
        client = _FakeClient({'mappings': [{
            'label': '공부더함',
            'category': CATEGORY_EXTRA_LEARNING,
            'subject_key': None,
            'item_key': None,
        }]})
        classify_unmapped_labels(['공부더함'], client=client, model=TEST_MODEL)
        kwargs = client.calls[0]
        self.assertEqual(kwargs['model'], TEST_MODEL)
        self.assertIs(kwargs['store'], False)
        self.assertEqual(kwargs['instructions'], SYSTEM_PROMPT)
        self.assertNotIn('tools', kwargs)
        fmt = kwargs['text']['format']
        self.assertEqual(fmt['type'], 'json_schema')
        self.assertTrue(fmt['strict'])


if __name__ == '__main__':
    unittest.main()
