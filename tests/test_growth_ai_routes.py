"""Teacher Growth AI routes/UI. 실제 OpenAI/AWS 호출 없음."""
from __future__ import annotations

import json
import os
import unittest
from datetime import date
from unittest.mock import patch

from tests.helpers import PROJECT_ROOT, bootstrap_test_app

app, db = bootstrap_test_app()

from app import VIEWER_ALLOWED_ENDPOINTS, VIEWER_ROLE_NAME, Child, User  # noqa: E402
from feature_models import GROWTH_AI_STATUS_SUCCESS, GrowthAIFeedback, GrowthAIGeneration  # noqa: E402
from features.growth.ai.hashing import packet_hash, runtime_signature
from features.growth.ai.runtime import TeacherAIResult, current_runtime_parts
from features.growth.ai.schema import OUTPUT_SCHEMA_VERSION
from tests.test_growth_ai_validator import _packet  # noqa: E402


AS_OF = date(2026, 12, 15)


def _pass_output():
    return {
        'schema_version': OUTPUT_SCHEMA_VERSION,
        'priority_insight': {
            'text': '최근 독서 활동일은 5일입니다.',
            'evidence_ids': ['reading.activity_days.current'],
        },
        'interpretation': {
            'text': '최근 독서 활동일을 다른 기록과 함께 보면 우선 확인할 변화가 분명합니다.',
            'evidence_ids': ['reading.activity_days.current'],
        },
        'observations': [
            {
                'text': '최근 독서 활동일은 5일입니다.',
                'evidence_ids': ['reading.activity_days.current'],
            }
        ],
        'next_actions': [
            {
                'text': '학습 계획이 있으면 남은 학습량도 함께 보면 좋겠습니다.',
                'evidence_ids': ['learning.math.plan.remaining_workload'],
                'conditional': True,
            }
        ],
        'next_check': {
            'text': '다음 비교 시점에 같은 기록을 다시 보면 판단이 더 분명해집니다.',
            'evidence_ids': ['reading.activity_days.current'],
        },
    }


class GrowthAIRouteTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.teacher = User(
            username='ai_route_teacher',
            name='AI라우트교사',
            role='돌봄선생님',
            email='ai-route@example.test',
            password_hash='',
        )
        self.viewer = User(
            username='ai_route_viewer',
            name='AI열람',
            role=VIEWER_ROLE_NAME,
            email='ai-viewer@example.test',
            password_hash='',
        )
        self.general = User(
            username='ai_route_general',
            name='AI일반',
            role='일반사용자',
            email='ai-general@example.test',
            password_hash='',
        )
        self.child = Child(name='라우트아동', grade=2, viewer_slug='airoutetchildslugxxx')
        db.session.add_all([self.teacher, self.viewer, self.general, self.child])
        db.session.commit()
        self.client = app.test_client()
        self.env = patch.dict(os.environ, {
            'GROWTH_AI_ENABLED': 'true',
            'GROWTH_SAFETY_GUARDRAIL_VERSION': '1',
        }, clear=False)
        self.env.start()
        self.packet_patch = patch(
            'features.growth.ai.runtime.build_current_packet',
            return_value=_packet(),
        )
        self.packet_patch.start()

    def tearDown(self):
        self.packet_patch.stop()
        self.env.stop()
        db.session.remove()
        self.ctx.pop()

    def _login(self, user):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True

    def _url(self, suffix=''):
        return f'/children/{self.child.id}/growth{suffix}'

    def test_unauthenticated_generate_rejected(self):
        response = self.client.post(self._url('/ai/generate'))
        self.assertIn(response.status_code, (302, 401))

    def test_viewer_generate_rejected(self):
        self._login(self.viewer)
        response = self.client.post(self._url('/ai/generate'))
        self.assertEqual(response.status_code, 302)

    def test_non_teacher_generate_rejected(self):
        self._login(self.general)
        response = self.client.post(self._url('/ai/generate'))
        self.assertEqual(response.status_code, 403)

    def test_missing_child_rejected(self):
        self._login(self.teacher)
        response = self.client.post('/children/999999/growth/ai/generate')
        self.assertEqual(response.status_code, 404)

    def test_get_does_not_auto_generate(self):
        self._login(self.teacher)
        with patch(
            'features.growth.routes.generate_teacher_growth_interpretation'
        ) as generate:
            response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        generate.assert_not_called()
        body = response.get_data(as_text=True)
        self.assertIn('발견된 변화', body)
        self.assertIn('AI 성장 해석 만들기', body)
        self.assertIn('data-ai-action="generate"', body)
        self.assertIn('growth-ai-mascot-slot', body)
        self.assertIn('성장 데이터 정리', body)
        self.assertIn('AI가 기록의 흐름 해석', body)
        self.assertIn('사실이 맞는지 확인', body)
        self.assertIn('안전하게 보여드릴 수 있는지 확인', body)
        self.assertIn('보통 5~10초 정도 걸려요', body)
        self.assertIn('성장 해석을 꼼꼼하게 마무리하고 있어요', body)
        self.assertIn('거의 다 준비됐어요. 잠시만 기다려주세요.', body)
        self.assertIn('data-stage="organize"', body)
        self.assertIn('prefers-reduced-motion', body)
        self.assertNotIn('현재 AWS', body)
        self.assertNotIn('fake percentage', body)
        loading = body.split('data-ai-panel="loading"', 1)[1].split('data-ai-panel="success"', 1)[0]
        self.assertNotIn('%', loading)
        self.assertNotIn('✓', loading)
        self.assertNotIn('완료', loading)
        waiting = loading.split('data-ai-role="waiting"', 1)[1]
        self.assertIn('growth-ai-hidden', loading.split('data-ai-role="waiting"', 1)[0][-80:] + waiting[:80])
        self.assertNotIn('AI 성장 해석이 준비됐어요!', loading)
        self.assertIn('growth-ai-hidden', body.split('data-ai-role="ready"', 1)[0][-80:] + body.split('data-ai-role="ready"', 1)[1][:80])
        js = (PROJECT_ROOT / 'static' / 'js' / 'growth-ai.js').read_text(encoding='utf-8')
        self.assertIn('const STAGE_MS = 2000', js)
        self.assertIn('const MIN_HOLD_MS = 8000', js)
        self.assertNotIn('const STAGE_MS = 1500', js)
        self.assertNotIn('const MIN_HOLD_MS = 6000', js)
        self.assertNotIn('const CYCLE_MS = 3500', js)
        self.assertNotIn('% CYCLE.length', js)
        self.assertIn("data-stage", js)
        self.assertIn("'organize'", js)
        self.assertIn("'waiting'", js)
        self.assertIn('prefers-reduced-motion', js)
        self.assertNotIn('percent', js.lower())
        self.assertNotIn('AWS', js)
        self.assertNotIn('reading.activity_days.current', body)
        self.assertNotIn('learning.math.peer.median', body)

    def test_disabled_flag_keeps_growth_page(self):
        self._login(self.teacher)
        with patch.dict(os.environ, {'GROWTH_AI_ENABLED': ''}, clear=False):
            response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn('발견된 변화', body)
        self.assertIn('AI 성장 해석 기능을 현재 사용할 수 없습니다', body)

    def test_cached_result_renders_without_ids(self):
        packet = _packet()
        db.session.add(GrowthAIGeneration(
            child_id=self.child.id,
            requested_by_user_id=self.teacher.id,
            packet_hash=packet_hash(packet),
            runtime_signature=runtime_signature(current_runtime_parts()),
            as_of=AS_OF,
            status=GROWTH_AI_STATUS_SUCCESS,
            parsed_output=_pass_output(),
        ))
        db.session.commit()
        self._login(self.teacher)
        body = self.client.get(self._url()).get_data(as_text=True)
        self.assertIn('최근 독서 활동일은 5일입니다.', body)
        self.assertIn('관찰한 점', body)
        self.assertIn('지금 해볼 일', body)
        self.assertIn('다음에 확인할 점', body)
        self.assertIn('가장 먼저 볼 변화', body)
        self.assertIn('분석 근거', body)
        self.assertIn('분석 근거 보기', body)
        self.assertIn('개별 근거 모두 보기', body)
        self.assertNotIn('reading.activity_days.current', body)
        self.assertNotIn('learning.math.plan.remaining_workload', body)
        self.assertNotIn('AI가 실제로 참조한', body)
        self.assertNotIn('AI 사고에 사용된', body)
        self.assertIn('data-ai-state="success"', body)
        self.assertIn('growth-ai-hidden', body.split('data-ai-role="ready"', 1)[0][-120:])

    def test_stale_state_renders(self):
        db.session.add(GrowthAIGeneration(
            child_id=self.child.id,
            requested_by_user_id=self.teacher.id,
            packet_hash='0' * 64,
            runtime_signature=runtime_signature(current_runtime_parts()),
            as_of=AS_OF,
            status=GROWTH_AI_STATUS_SUCCESS,
            parsed_output=_pass_output(),
        ))
        db.session.commit()
        self._login(self.teacher)
        body = self.client.get(self._url()).get_data(as_text=True)
        self.assertIn('성장 데이터가 업데이트됐어요', body)
        self.assertIn('새로 분석하기', body)
        self.assertNotIn('data-ai-state="success"', body)

    def test_generate_json_success_and_feedback(self):
        self._login(self.teacher)
        with patch('features.growth.routes.generate_teacher_growth_interpretation') as generate:
            generate.return_value = TeacherAIResult(
                ok=True,
                state='success',
                generation_id=99,
                interpretation={'summary': '요약', 'observations': ['관찰'], 'suggestions': ['제안']},
                evidence=[{'label': '최근 독서 활동일', 'value': '5일', 'note': None}],
                started=True,
            )
            response = self.client.post(self._url('/ai/generate'))
        payload = response.get_json()
        self.assertTrue(payload['ok'])
        self.assertTrue(payload['started'])
        self.assertNotIn('generated_output', json.dumps(payload))
        self.assertNotIn('reading.activity_days', json.dumps(payload))
        row = GrowthAIGeneration(
            child_id=self.child.id,
            requested_by_user_id=self.teacher.id,
            packet_hash='1' * 64,
            runtime_signature='2' * 64,
            as_of=AS_OF,
            status=GROWTH_AI_STATUS_SUCCESS,
            parsed_output=_pass_output(),
        )
        db.session.add(row)
        db.session.commit()
        feedback = self.client.post(
            self._url('/ai/feedback'),
            json={'generation_id': row.id, 'helpful': False, 'comment': '이해하기 어려워요'},
        )
        self.assertEqual(feedback.status_code, 200)
        row = GrowthAIFeedback.query.one()
        self.assertEqual(row.comment, '이해하기 어려워요')
        self.assertFalse(row.helpful)

    def test_ai_failure_does_not_break_growth_page(self):
        self._login(self.teacher)
        with patch('features.growth.routes.load_teacher_ai_view', side_effect=RuntimeError('boom')):
            response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn('발견된 변화', body)
        self.assertIn('AI 성장 해석', body)

    def test_viewer_allowlist_excludes_ai_endpoints(self):
        self.assertNotIn('growth.generate_ai', VIEWER_ALLOWED_ENDPOINTS)
        self.assertNotIn('growth.feedback_ai', VIEWER_ALLOWED_ENDPOINTS)
        endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
        self.assertIn('growth.generate_ai', endpoints)
        self.assertIn('growth.feedback_ai', endpoints)
