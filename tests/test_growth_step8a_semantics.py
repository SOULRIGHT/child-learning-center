"""Growth vNext Step 8A: canonical vs legacy UI semantics. 계산 공식은 바꾸지 않는다."""
from __future__ import annotations

import json
import os
import unittest
from datetime import date, timedelta
from unittest import mock

from tests.helpers import bootstrap_test_app, local_development_sqlite_path, resolved_engine_sqlite_path

app, db = bootstrap_test_app()

from app import Child, DailyPoints, User  # noqa: E402
from feature_models import (  # noqa: E402
    ACTOR_TEACHER,
    LearningProgressEntry,
    LearningSubject,
    STUDY_STATUS_STUDIED,
)
from features.dates import DEV_DATE_CONTROL_ENV  # noqa: E402
from features.growth.ai.presenter import present_cited_evidence_bundle  # noqa: E402
from features.growth.copy import (  # noqa: E402
    LEARNING_PAGE_ADVANCE_RECENT_WINDOW_BEST,
    PROGRESS_ENTRIES_DECREASE,
    PROGRESS_ENTRIES_INCREASE,
)
from features.growth.learning_view import (  # noqa: E402
    NO_SNAPSHOT_LABEL,
    PEER_NONE_LABEL,
    PERIOD_COMPARISON_UNAVAILABLE_LABEL,
    PERIOD_POINTS_CHART_TITLE,
    PERIOD_POINTS_RECORDS_INSUFFICIENT_LABEL,
    PERIOD_RECORDS_INSUFFICIENT_LABEL,
    reading_record_status_label,
)
from features.growth.service import _localize_reading_analysis, build_growth_view_model  # noqa: E402
from features.planning.service import create_workbook_plan  # noqa: E402
from features.progress.service import ensure_default_subjects  # noqa: E402
from features.study.constants import INPUT_CHANNEL_TEACHER, RECORD_VERIFICATION_OBSERVED  # noqa: E402
from features.study.records import create_study_session  # noqa: E402


AS_OF = date(2026, 12, 15)
PREV_START = date(2026, 10, 17)
CURRENT_START = date(2026, 11, 16)
BOOK = '우등생 수학 3-2'


class GrowthStep8ASemanticsTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.assertNotEqual(resolved_engine_sqlite_path(db), local_development_sqlite_path())
        ensure_default_subjects()
        self.teacher = User(
            username='step8a_teacher',
            name='의미교사',
            role='돌봄선생님',
            email='step8a@example.test',
            password_hash='',
        )
        self.child = Child(name='의미아동', grade=3, viewer_slug='step8achildstep8achildaa')
        db.session.add_all([self.teacher, self.child])
        db.session.commit()
        self.math = LearningSubject.query.filter_by(key='math').one()
        self.korean = LearningSubject.query.filter_by(key='korean').one()
        self.client = app.test_client()
        os.environ[DEV_DATE_CONTROL_ENV] = '1'
        self.patchers = [
            mock.patch('features.study.records.kst_today', return_value=AS_OF),
            mock.patch('features.study.coverage.kst_today', return_value=AS_OF),
            mock.patch('features.study.schedule.kst_today', return_value=AS_OF),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        os.environ.pop(DEV_DATE_CONTROL_ENV, None)
        db.session.remove()
        self.ctx.pop()

    def _login(self):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(self.teacher.id)
            sess['_fresh'] = True

    def _html(self, child=None, as_of=AS_OF):
        self._login()
        target = child or self.child
        response = self.client.get(
            f'/children/{target.id}/growth',
            query_string={'as_of': as_of.isoformat()},
        )
        self.assertEqual(response.status_code, 200)
        return response.get_data(as_text=True)

    def _view(self, child=None, as_of=AS_OF):
        return build_growth_view_model(child or self.child, as_of=as_of)

    def _plan(self, *, title=BOOK, subject=None, start_page=1, end_page=200,
              start_date=date(2026, 1, 1), target=date(2026, 12, 31)):
        plan = create_workbook_plan(
            grade=3,
            learning_subject_id=(subject or self.math).id,
            textbook_title=title,
            start_page=start_page,
            end_page=end_page,
            start_date=start_date,
            target_completion_date=target,
            exclusion_ranges_text=None,
        )
        plan.exclusion_ranges_json = []
        db.session.commit()
        return plan

    def _session(self, plan, day, start, end, *, child=None, subject=None):
        return create_study_session(
            child_id=(child or self.child).id,
            learning_subject_id=(subject or self.math).id,
            study_date=day,
            study_status=STUDY_STATUS_STUDIED,
            start_page=start,
            end_page=end,
            recorded_by_user_id=self.teacher.id,
            record_verification=RECORD_VERIFICATION_OBSERVED,
            learning_workbook_plan_id=plan.id,
            actor_type=ACTOR_TEACHER,
            input_channel=INPUT_CHANNEL_TEACHER,
        )

    def _progress_entry(self, on, page, *, child=None, subject=None, title=BOOK):
        db.session.add(LearningProgressEntry(
            child_id=(child or self.child).id,
            learning_subject_id=(subject or self.math).id,
            recorded_on=on,
            textbook_title=title,
            page=page,
            created_by_user_id=self.teacher.id,
        ))
        db.session.commit()

    def _points(self, on, total, *, child=None):
        db.session.add(DailyPoints(
            child_id=(child or self.child).id,
            date=on,
            korean_points=total,
            math_points=0,
            ssen_points=0,
            reading_points=0,
            piano_points=0,
            english_points=0,
            advanced_math_points=0,
            writing_points=0,
            manual_points=0,
            manual_history='[]',
            total_points=total,
            created_by=self.teacher.id,
        ))
        db.session.commit()

    def _peer(self, name, slug):
        row = Child(name=name, grade=3, viewer_slug=slug, include_in_stats=True)
        db.session.add(row)
        db.session.commit()
        return row

    def test_canonical_progress_does_not_say_no_progress_record(self):
        plan = self._plan()
        self._session(plan, date(2026, 12, 1), 1, 145)
        html = self._html()
        math_html = html.split('data-learning-subject="math"', 1)[1]
        self.assertIn('관측 기반 진도', math_html)
        self.assertIn('145 / 200페이지', math_html)
        self.assertNotIn(NO_SNAPSHOT_LABEL, html)
        self.assertNotIn('진도 기록 없음', math_html)

    def test_study_session_without_progress_entry_is_not_zero_count_status(self):
        plan = self._plan()
        self._session(plan, date(2026, 12, 1), 1, 20)
        view = self._view()
        self.assertEqual(view['progress']['entry_count_current'] or 0, 0)
        kpi_keys = [item['key'] for item in view['kpis']]
        self.assertNotIn('progress_entries', kpi_keys)
        html = self._html()
        self.assertNotIn('최근 학습 진도 기록', html)
        self.assertNotIn('학습 진도 기록 최근 0건', html)
        self.assertNotIn('학습 진도 기록 0건', html)

    def test_previous_period_and_peer_labels_are_distinct(self):
        self._points(CURRENT_START, 270)
        for index in range(4):
            peer = self._peer(f'비교{index}', f'step8apeer{index:018d}')
            self._points(CURRENT_START, 280 + index * 10, child=peer)
        html = self._html()
        self.assertIn(PERIOD_COMPARISON_UNAVAILABLE_LABEL, html)
        self.assertIn(PERIOD_POINTS_CHART_TITLE, html)
        self.assertIn(PERIOD_POINTS_RECORDS_INSUFFICIENT_LABEL, html)
        self.assertNotIn('비교할 수 있는 포인트 기록이 아직 충분하지 않습니다.', html)
        self.assertIn('내 기록 270점', html)
        self.assertNotIn('비교 자료 부족', html.split('핵심 지표', 1)[1].split('학습 진도', 1)[0])
        self.assertNotEqual(PERIOD_COMPARISON_UNAVAILABLE_LABEL, PEER_NONE_LABEL)
        self.assertNotEqual(PERIOD_POINTS_RECORDS_INSUFFICIENT_LABEL, PEER_NONE_LABEL)
        self.assertNotEqual(PERIOD_RECORDS_INSUFFICIENT_LABEL, PEER_NONE_LABEL)
        points_peer = html.split('data-testid="canonical-peer-points"', 1)[1][:800]
        self.assertNotIn(PERIOD_COMPARISON_UNAVAILABLE_LABEL, points_peer)
        self.assertNotIn(PERIOD_POINTS_RECORDS_INSUFFICIENT_LABEL, points_peer)
        self.assertNotIn(PERIOD_RECORDS_INSUFFICIENT_LABEL, points_peer)

    def test_learning_progress_entry_sentinel_does_not_change_canonical_progress(self):
        plan = self._plan()
        self._session(plan, date(2026, 12, 1), 1, 10)
        self._progress_entry(date(2026, 12, 10), 999)
        card = next(item for item in self._view()['learning']['subjects'] if item['key'] == 'math')
        self.assertEqual(card['page'], 999)
        self.assertEqual(card['observed_progress']['pages_display'], '10 / 200페이지')
        html = self._html()
        math_html = html.split('data-learning-subject="math"', 1)[1]
        self.assertIn('10 / 200페이지', math_html)
        self.assertNotIn('현재 999p', math_html)
        self.assertNotIn('999 / 200페이지', math_html)

    def test_forecast_same_date_and_range_formatting(self):
        same = {'earliest_date': date(2026, 9, 29), 'latest_date': date(2026, 9, 29), 'available': True}
        from features.growth.learning_view import _observed_progress_view
        same_view = _observed_progress_view({'forecast': same, 'progress': {}, 'status': 'exact'})
        self.assertEqual(same_view['forecast_display'], '2026-09-29 예상')
        ranged = _observed_progress_view({
            'forecast': {
                'earliest_date': date(2026, 9, 29),
                'latest_date': date(2026, 10, 6),
                'available': True,
            },
            'progress': {},
            'status': 'exact',
        })
        self.assertEqual(ranged['forecast_display'], '2026-09-29 ~ 2026-10-06 예상')

    def test_reading_status_enum_is_localized(self):
        self.assertEqual(reading_record_status_label('in_progress'), '읽는 중')
        self.assertEqual(reading_record_status_label('completed'), '완독')
        self.assertEqual(reading_record_status_label('abandoned'), '중단')
        self.assertEqual(reading_record_status_label('mystery_status'), '상태 미상')
        localized = _localize_reading_analysis({
            'recent_records': [
                {'date': '2026-12-01', 'book_title': '상태책', 'status': 'in_progress'},
            ],
        })
        self.assertEqual(localized['recent_records'][0]['status_label'], '읽는 중')
        html = self._html()
        reading_block = html.split('data-testid="growth-reading-recent"', 1)[-1][:800]
        self.assertNotIn('in_progress', reading_block)
        self.assertNotIn('completed', reading_block)
        self.assertNotIn('abandoned', reading_block)

    def test_unavailable_is_not_rendered_as_zero(self):
        html = self._html()
        math_html = html.split('data-learning-subject="math"', 1)[1]
        self.assertIn('관측 기반 진도', math_html)
        self.assertIn('N/A', math_html)
        self.assertIn('교재 계획 없음', math_html)
        self.assertNotIn('0 / 0페이지', math_html)
        self.assertNotIn('학습 기록 기준 0%', math_html)
        self.assertIn(PEER_NONE_LABEL, math_html)
        self.assertNotIn('같은 학년 또래 중앙값 0%', math_html)
        self.assertNotIn('같은 학년·같은 과목 또래 중앙값 0%', math_html)
        self.assertIn(PERIOD_RECORDS_INSUFFICIENT_LABEL, html)
        self.assertIn(PERIOD_POINTS_CHART_TITLE, html)
        self.assertIn(PERIOD_POINTS_RECORDS_INSUFFICIENT_LABEL, html)
        self.assertNotIn('아직 비교할 수 있는 기록이 충분하지 않습니다.', html)
        self.assertNotIn('비교할 수 있는 기록이 아직 충분하지 않습니다.', html)
        self.assertNotIn('비교할 수 있는 포인트 기록이 아직 충분하지 않습니다.', html)
        self.assertNotIn(PERIOD_RECORDS_INSUFFICIENT_LABEL, math_html)

    def test_rank_percentile_copy_absent(self):
        plan = self._plan()
        self._session(plan, date(2026, 12, 1), 1, 20)
        html = self._html()
        for banned in ('순위', '백분위', '상위권', '하위권', '퍼센타일', 'percentile'):
            self.assertNotIn(banned, html)

    def test_legacy_progress_insights_are_not_shown(self):
        self._progress_entry(PREV_START, 10)
        self._progress_entry(PREV_START + timedelta(days=1), 12)
        self._progress_entry(CURRENT_START, 40)
        self._progress_entry(CURRENT_START + timedelta(days=1), 50)
        self._progress_entry(CURRENT_START + timedelta(days=2), 60)
        view = self._view()
        ids = {item['id'] for item in view['insights']}
        self.assertNotIn(PROGRESS_ENTRIES_INCREASE, ids)
        self.assertNotIn(PROGRESS_ENTRIES_DECREASE, ids)
        self.assertNotIn(LEARNING_PAGE_ADVANCE_RECENT_WINDOW_BEST, ids)
        html = self._html()
        self.assertNotIn('최근 학습 진도 기록이 이전 기간보다 늘었어요.', html)

    def test_compact_presenter_v3_metric_set(self):
        packet = {
            'supporting_facts': {
                'reading': {
                    'activity_days': {
                        'current': {
                            'evidence_id': 'reading.activity_days.current',
                            'available': True,
                            'value': 8,
                        },
                    },
                    'analysis': {
                        'observation': {
                            '1': {
                                'evidence_id': 'reading.analysis.observation.1',
                                'available': True,
                                'value': '문장 길이가 줄었습니다',
                            },
                        },
                    },
                },
                'points': {
                    'period': {
                        'current': {
                            'evidence_id': 'points.period.current',
                            'available': True,
                            'value': 270,
                        },
                    },
                    'peer': {
                        'peer_median': {
                            'evidence_id': 'points.peer.peer_median',
                            'available': True,
                            'value': 292.5,
                        },
                    },
                },
                'learning': {
                    'subjects': {
                        'math': {
                            'subject_key': 'math',
                            'subject_label': '수학',
                            'performance': {
                                'current': {
                                    'rate': {
                                        'evidence_id': 'learning.math.performance.rate.current',
                                        'available': True,
                                        'value': 0.8,
                                    },
                                },
                            },
                            'progress': {
                                'coverage_ratio': {
                                    'evidence_id': 'learning.math.progress.coverage_ratio',
                                    'available': True,
                                    'value': 0.72,
                                },
                            },
                            'performance_peer': {
                                'peer_median': {
                                    'evidence_id': 'learning.math.performance_peer.peer_median',
                                    'available': True,
                                    'value': 0.7,
                                },
                            },
                            'coverage_peer': {
                                'peer_median': {
                                    'evidence_id': 'learning.math.coverage_peer.peer_median',
                                    'available': True,
                                    'value': 0.65,
                                },
                            },
                            'forecast': {
                                'earliest_date': {
                                    'evidence_id': 'learning.math.forecast.earliest_date',
                                    'available': True,
                                    'value': '2026-09-29',
                                },
                                'latest_date': {
                                    'evidence_id': 'learning.math.forecast.latest_date',
                                    'available': True,
                                    'value': '2026-09-29',
                                },
                            },
                        },
                    },
                },
            },
        }
        parsed = {
            'summary': {
                'text': '종합',
                'evidence_ids': [
                    'learning.math.performance.rate.current',
                    'learning.math.progress.coverage_ratio',
                    'learning.math.performance_peer.peer_median',
                    'learning.math.coverage_peer.peer_median',
                    'learning.math.forecast.earliest_date',
                    'learning.math.forecast.latest_date',
                    'points.period.current',
                    'points.peer.peer_median',
                    'reading.activity_days.current',
                    'reading.analysis.observation.1',
                ],
            },
        }
        bundle = present_cited_evidence_bundle(packet, parsed)
        blob = json.dumps(bundle, ensure_ascii=False)
        self.assertNotIn('learning.math.performance.rate.current', blob)
        by_key = {group['key']: group for group in bundle['groups']}
        math_compact = {row['label']: row['value'] for row in by_key['math']['compact']}
        self.assertEqual(math_compact['학습 수행률'], '80%')
        self.assertEqual(math_compact['관측 기반 진도율'], '72%')
        self.assertEqual(math_compact['같은 학년·같은 과목 수행률 중앙값'], '70%')
        self.assertEqual(math_compact['같은 교재 진도율 중앙값'], '65%')
        self.assertEqual(math_compact['완료예상'], '2026-09-29 예상')
        other = {row['label']: row['value'] for row in by_key['other']['compact']}
        self.assertEqual(other['최근'], '270점')
        self.assertEqual(other['같은 학년 포인트 중앙값'], '292.5점')
        reading = {row['label']: row['value'] for row in by_key['reading']['compact']}
        self.assertEqual(reading['최근 30일'], '활동 8일')
        self.assertEqual(reading['독서 관찰'], '문장 길이가 줄었습니다')
