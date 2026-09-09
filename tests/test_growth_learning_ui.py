"""Teacher Growth learning UI. 계산/insight 없이 Step D 표시만 검증한다."""
from __future__ import annotations

import os
import unittest
from datetime import date, timedelta

from tests.helpers import bootstrap_test_app, local_development_sqlite_path, resolved_engine_sqlite_path

app, db = bootstrap_test_app()

from app import Child, DailyPoints, User  # noqa: E402
from feature_models import LearningProgressEntry, LearningSubject, LearningWorkbookPlan  # noqa: E402
from features.dates import DEV_DATE_CONTROL_ENV  # noqa: E402
from features.growth.copy import READING_ACTIVITY_INCREASE  # noqa: E402
from features.growth.insights import generate_insight_candidates, top_candidates  # noqa: E402
from features.growth.learning_view import (  # noqa: E402
    INSUFFICIENT_LABEL,
    NO_SNAPSHOT_LABEL,
    OBSERVED_STUDY_DAYS_HINT,
    OBSERVED_STUDY_DAYS_LABEL,
    PEER_NONE_LABEL,
    PEER_STALE_LABEL,
    PERIOD_INSUFFICIENT_LABEL,
    _rate_text,
)
from features.growth.service import build_growth_view_model  # noqa: E402
from features.planning.service import create_workbook_plan  # noqa: E402
from features.planning.workload import WORKLOAD_KIND_ESTIMATED, WORKLOAD_KIND_EXACT  # noqa: E402
from features.progress.service import ensure_default_subjects  # noqa: E402
from feature_models import (  # noqa: E402
    ACTOR_TEACHER,
    POLICY_VERSION_GENERAL_V2,
    Book,
    ChildReading,
    ReadingDay,
)


AS_OF = date(2026, 12, 15)
BOOK = '우등생 수학 3-2'
BOOK_OLD = '우등생 수학 3-1'
PREV_START = date(2026, 10, 17)
CURRENT_START = date(2026, 11, 16)


class GrowthLearningUiTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.assertNotEqual(resolved_engine_sqlite_path(db), local_development_sqlite_path())
        ensure_default_subjects()
        self.teacher = User(
            username='learn_ui_teacher',
            name='학습화면교사',
            role='돌봄선생님',
            email='learn-ui@example.test',
            password_hash='',
        )
        self.child = Child(name='학습화면아동', grade=3, viewer_slug='uuuuuuuuuuuuuuuuuuuuuuuu')
        db.session.add_all([self.teacher, self.child])
        db.session.commit()
        self.math = LearningSubject.query.filter_by(key='math').one()
        self.korean = LearningSubject.query.filter_by(key='korean').one()
        self.ssen = LearningSubject.query.filter_by(key='ssen').one()
        self.client = app.test_client()
        os.environ[DEV_DATE_CONTROL_ENV] = '1'

    def tearDown(self):
        os.environ.pop(DEV_DATE_CONTROL_ENV, None)
        db.session.remove()
        self.ctx.pop()

    def _child(self, name, *, grade=3, include_in_stats=True, slug):
        row = Child(name=name, grade=grade, viewer_slug=slug, include_in_stats=include_in_stats)
        db.session.add(row)
        db.session.commit()
        return row

    def _progress(self, on, *, page, title=BOOK, subject=None, child=None):
        db.session.add(LearningProgressEntry(
            child_id=(child or self.child).id,
            learning_subject_id=(subject or self.math).id,
            recorded_on=on,
            textbook_title=title,
            page=page,
            created_by_user_id=self.teacher.id,
        ))
        db.session.commit()

    def _daily(self, on, *, korean=100, child=None):
        db.session.add(DailyPoints(
            child_id=(child or self.child).id,
            date=on,
            korean_points=korean,
            math_points=0,
            ssen_points=0,
            reading_points=0,
            piano_points=0,
            english_points=0,
            advanced_math_points=0,
            writing_points=0,
            manual_points=0,
            manual_history='[]',
            total_points=korean,
            created_by=self.teacher.id,
        ))
        db.session.commit()

    def _plan(self, *, title=BOOK, subject=None, start_page=1, end_page=184,
              start_date=date(2026, 9, 1), target=date(2026, 12, 20),
              exclusions=None, grade=3):
        return create_workbook_plan(
            grade=grade,
            learning_subject_id=(subject or self.math).id,
            textbook_title=title,
            start_page=start_page,
            end_page=end_page,
            start_date=start_date,
            target_completion_date=target,
            exclusion_ranges_text=exclusions,
        )

    def _view(self, as_of=AS_OF, child=None):
        return build_growth_view_model(child or self.child, as_of=as_of)

    def _math_card(self, as_of=AS_OF, child=None):
        view = self._view(as_of=as_of, child=child)
        return next(item for item in view['learning']['subjects'] if item['key'] == 'math')

    def _login(self):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(self.teacher.id)
            sess['_fresh'] = True

    def _html(self, as_of=AS_OF, child=None):
        self._login()
        target = child or self.child
        response = self.client.get(
            f'/children/{target.id}/growth',
            query_string={'as_of': as_of.isoformat()},
        )
        self.assertEqual(response.status_code, 200)
        return response.get_data(as_text=True)

    def _learning_html(self, as_of=AS_OF, child=None):
        html = self._html(as_of=as_of, child=child)
        start = html.find('data-growth-learning')
        self.assertGreater(start, 0)
        end = html.find('</section>', start)
        return html[start:end]

    def test_empty_subject_cards_and_observed_days(self):
        view = self._view()
        subjects = view['learning']['subjects']
        self.assertEqual([item['key'] for item in subjects], ['korean', 'math', 'ssen'])
        self.assertFalse(subjects[0]['has_snapshot'])
        self.assertEqual(subjects[0]['empty_label'], NO_SNAPSHOT_LABEL)
        observed = view['learning']['observed_study_days']
        self.assertEqual(observed['label'], OBSERVED_STUDY_DAYS_LABEL)
        self.assertEqual(observed['summary'], '최근 0일 · 이전 0일')
        self.assertFalse(observed['attendance'])
        html = self._html()
        self.assertEqual(html.count('관측 학습일'), 1)
        self.assertEqual(html.count(NO_SNAPSHOT_LABEL), 3)
        self.assertIn(OBSERVED_STUDY_DAYS_HINT, html)
        self.assertNotIn('출석일', html)
        self.assertNotIn('출석률', html)

    def test_current_snapshot_replaces_old_snapshot_cards(self):
        self._progress(date(2026, 12, 10), page=112)
        card = self._math_card()
        self.assertTrue(card['has_snapshot'])
        self.assertEqual(card['textbook_title'], BOOK)
        self.assertEqual(card['page'], 112)
        self.assertEqual(card['page_display'], '현재 112p')
        self.assertEqual(card['recorded_on_label'], '최근 기록 12/10')
        html = self._learning_html()
        self.assertIn(BOOK, html)
        self.assertIn('현재 112p', html)
        self.assertIn('최근 기록 12/10', html)
        self.assertIn('2026-12-10', html)
        self.assertNotIn('progress.latest_snapshots', html)
        self.assertEqual(html.count('data-learning-subject="math"'), 1)

    def test_positive_zero_negative_and_unavailable_page_advance(self):
        self._progress(date(2026, 11, 10), page=80)
        self._progress(date(2026, 11, 20), page=90)
        self._progress(date(2026, 12, 10), page=120)
        card = self._math_card()
        self.assertTrue(card['page_advance']['current_available'])
        self.assertEqual(card['page_advance']['current_display'], '+40p')
        html = self._learning_html()
        self.assertIn('+40p', html)
        self.assertNotIn('후퇴', html)
        self.assertNotIn('부진', html)

        db.session.query(LearningProgressEntry).delete()
        db.session.commit()
        self._progress(date(2026, 11, 10), page=80)
        self._progress(date(2026, 12, 10), page=80)
        zero = self._math_card()
        self.assertEqual(zero['page_advance']['current_value'], 0)
        self.assertEqual(zero['page_advance']['current_display'], '0p · 변화 없음')
        self.assertIn('0p · 변화 없음', self._learning_html())

        db.session.query(LearningProgressEntry).delete()
        db.session.commit()
        self._progress(date(2026, 11, 10), page=100)
        self._progress(date(2026, 12, 10), page=95)
        negative = self._math_card()
        self.assertEqual(negative['page_advance']['current_value'], -5)
        self.assertEqual(negative['page_advance']['current_display'], '기록상 -5p')
        body = self._learning_html()
        self.assertIn('기록상 -5p', body)
        self.assertNotIn('감소했다', body)
        self.assertNotIn('후퇴', body)

        db.session.query(LearningProgressEntry).delete()
        db.session.commit()
        self._progress(date(2026, 11, 20), page=90)
        unavailable = self._math_card()
        self.assertFalse(unavailable['page_advance']['current_available'])
        self.assertEqual(unavailable['page_advance']['unavailable_label'], INSUFFICIENT_LABEL)
        html = self._learning_html()
        self.assertIn(INSUFFICIENT_LABEL, html)
        self.assertNotIn('최근 30일</div>\n                        <div class="growth-learn-value">0p', html)

    def test_trend_comparable_and_book_change(self):
        self._progress(date(2026, 10, 10), page=50)
        self._progress(date(2026, 11, 10), page=80)
        self._progress(date(2026, 12, 10), page=120)
        comparable = self._math_card()
        self.assertTrue(comparable['page_advance']['trend_comparable'])
        self.assertEqual(comparable['page_advance']['previous_display'], '이전 +30p')
        self.assertEqual(comparable['page_advance']['delta_display'], '+10p')
        html = self._learning_html()
        self.assertIn('이전 +30p', html)
        self.assertIn('기간 대비 +10p', html)
        self.assertNotIn('growth-delta-up', html.split('data-growth-learning', 1)[1])

        db.session.query(LearningProgressEntry).delete()
        db.session.commit()
        self._progress(date(2026, 10, 10), page=50, title=BOOK_OLD)
        self._progress(date(2026, 11, 10), page=150, title=BOOK_OLD)
        self._progress(date(2026, 11, 12), page=10)
        self._progress(date(2026, 12, 10), page=40)
        changed = self._math_card()
        self.assertTrue(changed['page_advance']['current_available'])
        self.assertFalse(changed['page_advance']['trend_comparable'])
        self.assertEqual(changed['page_advance']['trend_unavailable_label'], PERIOD_INSUFFICIENT_LABEL)
        self.assertIsNone(changed['page_advance']['delta_display'])
        body = self._learning_html()
        self.assertIn(PERIOD_INSUFFICIENT_LABEL, body)
        self.assertNotIn('기간 대비', body)

    def test_peer_median_n_and_unavailable(self):
        self._progress(date(2026, 12, 10), page=112)
        one = self._child('동료1', slug='peerui111111111111111111')
        self._progress(date(2026, 12, 12), page=124, child=one)
        card = self._math_card()
        self.assertTrue(card['peer']['available'])
        self.assertEqual(card['peer']['n'], 1)
        self.assertEqual(card['peer']['n_display'], '비교 1명')
        self.assertEqual(card['peer']['median_display'], '124p')
        self.assertEqual(card['peer']['gap_display'], '중앙값 대비 -12p')
        html = self._learning_html()
        self.assertNotIn('동학년 동일 교재', html)
        self.assertNotIn('중앙값 124p', html)
        self.assertNotIn('중앙값 대비 -12p', html)
        self.assertNotIn('뒤처짐', html)
        self.assertNotIn('우수', html)
        self.assertNotIn('부진', html)
        self.assertNotIn('상위', html)

        two = self._child('동료2', slug='peerui222222222222222222')
        self._progress(date(2026, 12, 12), page=100, child=two)
        pair = self._math_card()
        self.assertEqual(pair['peer']['n'], 2)
        self.assertEqual(pair['peer']['median_display'], '112p')
        self.assertEqual(pair['peer']['n_display'], '비교 2명')

        three = self._child('동료3', slug='peerui333333333333333333')
        self._progress(date(2026, 12, 12), page=101, child=three)
        half = self._math_card()
        self.assertEqual(half['peer']['n'], 3)
        # 100, 101, 124 → median 101
        self.assertEqual(half['peer']['median_display'], '101p')

        four = self._child('동료4', slug='peerui444444444444444444')
        self._progress(date(2026, 12, 12), page=130, child=four)
        even = self._math_card()
        self.assertEqual(even['peer']['n'], 4)
        self.assertEqual(even['peer']['median_display'], '112.5p')
        self.assertNotIn('112.5p', self._learning_html())

        db.session.query(LearningProgressEntry).filter(
            LearningProgressEntry.child_id != self.child.id
        ).delete()
        db.session.commit()
        none = self._math_card()
        self.assertFalse(none['peer']['available'])
        self.assertEqual(none['peer']['unavailable_label'], PEER_NONE_LABEL)
        self.assertIsNone(none['peer']['median_display'])
        self.assertIn(PEER_NONE_LABEL, self._learning_html())

        db.session.query(LearningProgressEntry).delete()
        db.session.commit()
        self._progress(date(2026, 10, 1), page=51)
        stale = self._math_card()
        self.assertEqual(stale['peer']['unavailable_label'], PEER_STALE_LABEL)
        self.assertNotIn('중앙값 0p', self._learning_html())

    def test_plan_statuses_and_exact_estimated(self):
        self._plan(exclusions='10-12')
        self._progress(date(2026, 12, 10), page=112)
        exact = self._math_card()
        self.assertEqual(exact['plan']['status'], 'active')
        self.assertEqual(exact['plan']['workload_kind'], WORKLOAD_KIND_EXACT)
        self.assertTrue(exact['plan']['exact'])
        self.assertFalse(exact['plan']['estimated'])
        self.assertTrue(exact['plan']['show_required'])
        self.assertFalse(exact['plan']['remaining_display'].startswith('약 '))
        self.assertIsNone(exact['plan']['remaining_note'])
        html = self._learning_html()
        self.assertIn('목표 12월 20일', html)
        self.assertNotIn('제외 페이지 20% 추정', html)
        self.assertNotIn('(추정)', html.split('data-learning-subject="math"', 1)[1][:1200])

        db.session.query(LearningProgressEntry).delete()
        db.session.commit()
        db.session.query(LearningWorkbookPlan).delete()
        db.session.commit()
        self._plan(exclusions=None)
        self._progress(date(2026, 12, 10), page=112)
        estimated = self._math_card()
        self.assertEqual(estimated['plan']['workload_kind'], WORKLOAD_KIND_ESTIMATED)
        self.assertTrue(estimated['plan']['remaining_display'].startswith('약 '))
        self.assertEqual(estimated['plan']['remaining_note'], '(제외 페이지 20% 추정)')
        self.assertEqual(estimated['plan']['required_note'], '(추정)')
        body = self._learning_html()
        self.assertIn('제외 페이지 20% 추정', body)
        self.assertIn('(추정)', body)

        db.session.query(LearningProgressEntry).delete()
        db.session.commit()
        db.session.query(LearningWorkbookPlan).delete()
        db.session.commit()
        self._plan(end_page=120, exclusions='10-12')
        self._progress(date(2026, 12, 10), page=120)
        complete = self._math_card()
        self.assertEqual(complete['plan']['status'], 'complete')
        self.assertEqual(complete['plan']['headline'], '목표 분량 완료')
        self.assertFalse(complete['plan']['show_required'])
        complete_html = self._learning_html()
        self.assertIn('목표 분량 완료', complete_html)
        self.assertNotIn('0p / 학습일', complete_html)
        self.assertNotIn('0.0p / 학습일', complete_html)

        db.session.query(LearningProgressEntry).delete()
        db.session.commit()
        db.session.query(LearningWorkbookPlan).delete()
        db.session.commit()
        self._plan(start_date=date(2027, 1, 5), target=date(2027, 3, 1), exclusions='10-12')
        self._progress(date(2026, 12, 10), page=40)
        upcoming = self._math_card()
        self.assertEqual(upcoming['plan']['status'], 'before_plan_start')
        self.assertIn('1월 5일 시작 예정', upcoming['plan']['headline'])
        self.assertTrue(upcoming['plan']['show_target'])
        self.assertFalse(upcoming['plan']['show_required'])
        self.assertIn('1월 5일 시작 예정', self._learning_html())
        self.assertIn('목표 3월 1일', self._learning_html())

        db.session.query(LearningProgressEntry).delete()
        db.session.commit()
        db.session.query(LearningWorkbookPlan).delete()
        db.session.commit()
        self._progress(date(2026, 12, 10), page=40)
        no_plan = self._math_card()
        self.assertEqual(no_plan['plan']['status'], 'no_plan')
        self.assertEqual(no_plan['plan']['headline'], '등록된 교재 계획 없음')
        self.assertTrue(no_plan['plan']['show_admin_link'])
        no_plan_html = self._learning_html()
        self.assertIn('등록된 교재 계획 없음', no_plan_html)
        self.assertIn('/settings/workbook-plans', no_plan_html)

        db.session.query(LearningProgressEntry).delete()
        db.session.commit()
        self._plan(start_date=date(2026, 9, 1), target=date(2026, 12, 1), exclusions='10-12')
        self._progress(date(2026, 12, 10), page=40)
        elapsed = self._math_card()
        self.assertEqual(elapsed['plan']['status'], 'target_elapsed')
        self.assertEqual(elapsed['plan']['headline'], '목표 완료일 경과')
        self.assertTrue(elapsed['plan']['show_remaining'])
        self.assertFalse(elapsed['plan']['show_required'])
        elapsed_html = self._learning_html()
        self.assertIn('목표 완료일 경과', elapsed_html)
        self.assertNotIn('계획 실패', elapsed_html)
        self.assertNotIn('p / 학습일', elapsed_html)

        db.session.query(LearningProgressEntry).delete()
        db.session.commit()
        db.session.query(LearningWorkbookPlan).delete()
        db.session.commit()
        self._plan(start_date=date(2026, 9, 1), target=date(2026, 12, 20), exclusions='10-12')
        self._progress(date(2026, 12, 18), page=40)
        no_days = self._math_card(as_of=date(2026, 12, 18))
        self.assertEqual(no_days['plan']['status'], 'no_remaining_planned_days')
        self.assertEqual(no_days['plan']['headline'], '남은 예정 학습일 없음')
        self.assertTrue(no_days['plan']['show_remaining'])
        self.assertFalse(no_days['plan']['show_required'])
        no_days_html = self._html(as_of=date(2026, 12, 18))
        self.assertIn('남은 예정 학습일 없음', no_days_html)
        self.assertNotIn('0p / 학습일', no_days_html)
        self.assertNotIn('0.0p / 학습일', no_days_html)

    def test_required_per_day_presentation_rounding(self):
        self.assertEqual(_rate_text(4.076923), '4.1p / 학습일')
        self.assertEqual(_rate_text(4.0), '4.0p / 학습일')
        self.assertEqual(_rate_text(4.076923, approx=True), '약 4.1p / 학습일')
        self.assertNotEqual(_rate_text(4.076923), '5p / 학습일')
        self.assertIsNone(_rate_text(None))

    def test_observed_study_days_not_repeated_on_subject_cards(self):
        self._daily(date(2026, 12, 10))
        self._daily(date(2026, 12, 11))
        self._daily(date(2026, 11, 1))
        self._progress(date(2026, 12, 10), page=40)
        view = self._view()
        self.assertEqual(view['learning']['observed_study_days']['current'], 2)
        self.assertEqual(view['learning']['observed_study_days']['previous'], 1)
        html = self._html()
        self.assertEqual(html.count('관측 학습일'), 1)
        self.assertIn('최근 2일 · 이전 1일', html)
        math_html = html.split('data-learning-subject="math"', 1)[1]
        self.assertNotIn('관측 학습일', math_html)
        self.assertNotIn('출석', self._learning_html())

    def test_existing_cards_charts_and_insight_output_unchanged(self):
        book = Book(title='증가책', normalized_key='증가책', is_active=True, grade_band='2-3')
        db.session.add(book)
        db.session.flush()
        reading = ChildReading(
            child_id=self.child.id,
            book_id=book.id,
            started_on=PREV_START,
            status='in_progress',
            policy_version=POLICY_VERSION_GENERAL_V2,
            created_by_user_id=self.teacher.id,
            actor_type=ACTOR_TEACHER,
        )
        db.session.add(reading)
        db.session.flush()
        dates = [PREV_START + timedelta(days=offset) for offset in range(6)]
        dates += [CURRENT_START + timedelta(days=offset) for offset in range(11)]
        for on in dates:
            db.session.add(ReadingDay(
                child_reading_id=reading.id,
                date=on,
                created_by_user_id=self.teacher.id,
                actor_type=ACTOR_TEACHER,
                policy_version=POLICY_VERSION_GENERAL_V2,
            ))
        db.session.commit()
        self._progress(date(2026, 11, 10), page=80)
        self._progress(date(2026, 12, 10), page=120)
        view = self._view()
        self.assertEqual(view['insights'][0]['id'], READING_ACTIVITY_INCREASE)
        self.assertEqual(len(view['insights']), 1)
        self.assertEqual(
            [item['id'] for item in view['insights']],
            [item.id for item in top_candidates(generate_insight_candidates(view['bundle']))],
        )
        html = self._html()
        self.assertIn('최근 독서 기록일', html)
        self.assertIn('최근 vs 이전 기간', html)
        self.assertIn('포인트 비교', html)
        self.assertIn('id="growth-chart-data"', html)
        self.assertIn('분석 근거 보기', html)
        self.assertIn('시작 기록', html)
        self.assertNotIn('stale_baseline', html)
        self.assertNotIn('center_default', html)
        self.assertNotIn('InsightCandidate', html)

    def test_build_learning_section_does_not_keep_orm_or_child_name(self):
        self._progress(date(2026, 12, 10), page=40)
        view = self._view()
        payload = str(view['learning'])
        self.assertNotIn('LearningProgressEntry', payload)
        self.assertNotIn(self.child.name, payload)
        self.assertNotIn('학습화면아동', self._learning_html())

    def test_observed_progress_labeled_and_na_without_sessions(self):
        html = self._learning_html()
        self.assertIn('관측 기반 진도', html)
        self.assertIn('학습 기록 기준', html)
        self.assertNotIn('전체 진도', html)
        math_html = html.split('data-learning-subject="math"', 1)[1]
        self.assertIn('data-testid="observed-progress-math"', math_html)
        self.assertIn('observed-forecast-unavailable', math_html)
        self.assertNotIn('observed-forecast-range', math_html)
        card = self._math_card()
        self.assertEqual(card['observed_progress']['pages_display'], 'N/A')
        self.assertEqual(card['observed_progress']['forecast_display'], 'N/A')
        self.assertFalse(card['observed_progress']['forecast_available'])
        self.assertNotEqual(card['observed_progress']['ratio_display'], '0%')

    def test_responsive_subject_grid_classes(self):
        html = self._html()
        self.assertIn('col-12 col-md-6 col-xl-4', html)
        self.assertNotIn('col-md-4', html.split('data-growth-learning', 1)[1][:400])
