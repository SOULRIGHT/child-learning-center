"""Step 8C1: Growth 공식 진입점과 센터 운영 설정 hub."""
from __future__ import annotations

import unittest
from datetime import date

from tests.helpers import bootstrap_test_app

app, db = bootstrap_test_app()

from app import VIEWER_ROLE_NAME, Child, User  # noqa: E402
from feature_models import (  # noqa: E402
    Book,
    CenterNonStudyDay,
    CenterStudyCalendar,
    LearningSubject,
    LearningWorkbookPlan,
    ManualPointPreset,
)
from features.planning.service import update_center_weekdays  # noqa: E402
from features.planning.weekdays import DEFAULT_STUDY_WEEKDAYS  # noqa: E402
from features.progress.service import ensure_default_subjects  # noqa: E402
from features.setup.status import (  # noqa: E402
    DEST_BOOKS,
    DEST_CENTER_WEEKDAYS,
    DEST_LEARNING_SUBJECTS,
    DEST_NON_STUDY_DAYS,
    DEST_POINTS,
    DEST_PRESETS,
    DEST_SUBJECT_WEEKDAYS,
    DEST_WORKBOOK_PLANS,
    STATUS_AVAILABLE,
    STATUS_MISSING,
    STATUS_OPTIONAL,
    STATUS_PARTIAL,
    STATUS_SAVED,
    STATUS_USING_DEFAULT,
    build_center_setup_status,
)
from features.study.calendar import save_center_non_study_day, save_subject_study_weekdays  # noqa: E402

AS_OF = date(2026, 9, 10)


class SetupStatusTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def _item(self, key, status=None):
        payload = status or build_center_setup_status(today=AS_OF)
        for item in payload['sections']:
            if item['key'] == key:
                return item
        self.fail(f'missing setup item {key}')

    def test_center_weekdays_missing_row_is_using_default_not_missing(self):
        item = self._item('center_study_weekdays')
        self.assertEqual(item['status'], STATUS_USING_DEFAULT)
        self.assertNotEqual(item['status'], STATUS_MISSING)
        self.assertNotEqual(item['status'], STATUS_SAVED)
        self.assertIn('기본값(월~금) 사용 중', item['summary'])
        self.assertIn('확인 권장', item['detail'])
        self.assertEqual(item['destination'], DEST_CENTER_WEEKDAYS)

    def test_center_weekdays_saved_row(self):
        update_center_weekdays([0, 2, 4])
        item = self._item('center_study_weekdays')
        self.assertEqual(item['status'], STATUS_SAVED)
        self.assertIn('월', item['summary'])

    def test_subject_weekdays_missing_partial_saved(self):
        ensure_default_subjects()
        subjects = list(LearningSubject.query.filter_by(is_active=True).order_by(LearningSubject.id))
        missing = self._item('subject_weekdays')
        self.assertEqual(missing['status'], STATUS_MISSING)
        self.assertEqual(missing['counts']['configured'], 0)
        self.assertEqual(missing['counts']['total'], 3)
        self.assertEqual(missing['destination'], DEST_SUBJECT_WEEKDAYS)

        save_subject_study_weekdays(subjects[0].id, [0, 1])
        partial = self._item('subject_weekdays')
        self.assertEqual(partial['status'], STATUS_PARTIAL)
        self.assertEqual(partial['counts']['configured'], 1)

        for subject in subjects[1:]:
            save_subject_study_weekdays(subject.id, [0, 1, 2])
        saved = self._item('subject_weekdays')
        self.assertEqual(saved['status'], STATUS_SAVED)
        self.assertEqual(saved['counts']['configured'], 3)

    def test_non_study_days_zero_is_optional_not_error(self):
        item = self._item('non_study_days')
        self.assertEqual(item['status'], STATUS_OPTIONAL)
        self.assertEqual(item['counts']['count'], 0)
        self.assertEqual(item['counts']['year'], 2026)
        self.assertNotIn('미설정', item['summary'])
        self.assertNotIn('실패', item['detail'])
        self.assertEqual(item['destination'], DEST_NON_STUDY_DAYS)

        save_center_non_study_day(date(2026, 5, 5), label='어린이날')
        counted = self._item('non_study_days')
        self.assertEqual(counted['status'], STATUS_OPTIONAL)
        self.assertEqual(counted['counts']['count'], 1)

    def test_workbook_plan_zero_explains_capability_not_growth_block(self):
        item = self._item('workbook_plans')
        self.assertEqual(item['status'], STATUS_MISSING)
        self.assertEqual(item['counts']['count'], 0)
        self.assertEqual(item['summary'], '교재 계획 없음')
        self.assertIn('관측 기반 진도', item['detail'])
        self.assertIn('완료예상', item['detail'])
        self.assertNotIn('사용 못', item['detail'])
        self.assertNotIn('불가', item['detail'])
        self.assertEqual(item['destination'], DEST_WORKBOOK_PLANS)

        ensure_default_subjects()
        math = LearningSubject.query.filter_by(key='math').one()
        db.session.add(LearningWorkbookPlan(
            grade=3,
            learning_subject_id=math.id,
            textbook_title='수학 3-1',
            start_page=1,
            end_page=100,
            start_date=date(2026, 3, 1),
            target_completion_date=date(2026, 12, 20),
        ))
        db.session.commit()
        ready = self._item('workbook_plans')
        self.assertEqual(ready['status'], STATUS_AVAILABLE)
        self.assertEqual(ready['counts']['count'], 1)

    def test_points_without_preset_is_not_overall_failure(self):
        payload = build_center_setup_status(today=AS_OF)
        item = self._item('points', payload)
        self.assertEqual(item['status'], STATUS_OPTIONAL)
        self.assertEqual(item['counts']['preset_count'], 0)
        self.assertEqual(item['destination'], DEST_POINTS)
        self.assertEqual(item['extra_actions'][0]['destination'], DEST_PRESETS)
        self.assertEqual(payload['next']['key'], 'learning_subjects')

        db.session.add(ManualPointPreset(
            key='pencil',
            label='연필',
            default_points=-300,
            is_active=True,
            sort_order=1,
        ))
        db.session.commit()
        ready = self._item('points')
        self.assertEqual(ready['status'], STATUS_AVAILABLE)

    def test_books_none_is_optional_not_blocker(self):
        item = self._item('reading')
        self.assertEqual(item['status'], STATUS_OPTIONAL)
        self.assertEqual(item['counts']['active'], 0)
        self.assertEqual(item['destination'], DEST_BOOKS)
        self.assertIn('필수는 아닙니다', item['detail'])

        db.session.add(Book(title='책', normalized_key='책', is_active=True))
        db.session.commit()
        ready = self._item('reading')
        self.assertEqual(ready['status'], STATUS_AVAILABLE)

    def test_next_recommended_is_deterministic(self):
        empty = build_center_setup_status(today=AS_OF)
        self.assertEqual(empty['next']['key'], 'learning_subjects')
        self.assertEqual(empty['next']['destination'], DEST_LEARNING_SUBJECTS)

        ensure_default_subjects()
        after_subjects = build_center_setup_status(today=AS_OF)
        self.assertEqual(after_subjects['next']['key'], 'center_study_weekdays')
        self.assertEqual(after_subjects['next']['status'], STATUS_USING_DEFAULT)

        update_center_weekdays(list(DEFAULT_STUDY_WEEKDAYS))
        after_center = build_center_setup_status(today=AS_OF)
        self.assertEqual(after_center['next']['key'], 'subject_weekdays')

        for subject in LearningSubject.query.filter_by(is_active=True):
            save_subject_study_weekdays(subject.id, [0, 1, 2, 3, 4])
        after_subject_days = build_center_setup_status(today=AS_OF)
        self.assertEqual(after_subject_days['next']['key'], 'workbook_plans')
        self.assertNotEqual(after_subject_days['next']['key'], 'non_study_days')

        math = LearningSubject.query.filter_by(key='math').one()
        db.session.add(LearningWorkbookPlan(
            grade=2,
            learning_subject_id=math.id,
            textbook_title='수학',
            start_page=1,
            end_page=50,
            start_date=date(2026, 3, 1),
            target_completion_date=date(2026, 7, 1),
        ))
        db.session.commit()
        after_plan = build_center_setup_status(today=AS_OF)
        self.assertEqual(after_plan['next']['key'], 'points')

        db.session.add(ManualPointPreset(
            key='print',
            label='프린트',
            default_points=-100,
            is_active=True,
            sort_order=1,
        ))
        db.session.commit()
        after_points = build_center_setup_status(today=AS_OF)
        self.assertEqual(after_points['next']['key'], 'reading')

        db.session.add(Book(title='도서', normalized_key='도서', is_active=True))
        db.session.commit()
        done = build_center_setup_status(today=AS_OF)
        self.assertIsNone(done['next'])

    def test_status_read_does_not_write_completion_rows(self):
        before_calendar = CenterStudyCalendar.query.count()
        before_days = CenterNonStudyDay.query.count()
        build_center_setup_status(today=AS_OF)
        self.assertEqual(CenterStudyCalendar.query.count(), before_calendar)
        self.assertEqual(CenterNonStudyDay.query.count(), before_days)
        self.assertIsNone(CenterStudyCalendar.query.first())


class SetupHubRouteTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        ensure_default_subjects()
        self.teacher = User(
            username='setup_teacher',
            name='설정교사',
            role='돌봄선생님',
            email='setup-teacher@example.test',
            password_hash='',
        )
        self.director = User(
            username='setup_director',
            name='설정센터장',
            role='센터장',
            email='setup-director@example.test',
            password_hash='',
        )
        self.general = User(
            username='setup_general',
            name='설정일반',
            role='일반사용자',
            email='setup-general@example.test',
            password_hash='',
        )
        self.viewer = User(
            username='setup_viewer',
            name='설정열람',
            role=VIEWER_ROLE_NAME,
            email='setup-viewer@example.test',
            password_hash='',
        )
        self.child = Child(name='설정아동', grade=2, viewer_slug='setupchildslugsetupchild')
        db.session.add_all([self.teacher, self.director, self.general, self.viewer, self.child])
        db.session.commit()
        self.client = app.test_client()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def _login(self, user):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True

    def test_teacher_growth_and_setup_journeys(self):
        self._login(self.teacher)
        listing = self.client.get('/children')
        self.assertEqual(listing.status_code, 200)
        self.assertIn(f'/children/{self.child.id}/growth', listing.get_data(as_text=True))

        detail = self.client.get(f'/children/{self.child.id}')
        self.assertEqual(detail.status_code, 200)
        self.assertIn('성장 리포트', detail.get_data(as_text=True))

        growth = self.client.get(f'/children/{self.child.id}/growth')
        self.assertEqual(growth.status_code, 200)
        self.assertIn('성장 리포트', growth.get_data(as_text=True))

        settings = self.client.get('/settings')
        self.assertEqual(settings.status_code, 200)
        self.assertIn('/settings/setup', settings.get_data(as_text=True))

        hub = self.client.get('/settings/setup')
        self.assertEqual(hub.status_code, 200)
        hub_html = hub.get_data(as_text=True)
        self.assertIn('/settings/study-calendar', hub_html)

        calendar = self.client.get('/settings/study-calendar')
        self.assertEqual(calendar.status_code, 200)
        subjects = self.client.get('/settings/learning-subjects')
        self.assertEqual(subjects.status_code, 200)

    def test_teacher_child_detail_has_growth_link(self):
        self._login(self.teacher)
        html = self.client.get(f'/children/{self.child.id}').get_data(as_text=True)
        self.assertIn(f'/children/{self.child.id}/growth', html)
        self.assertIn('성장 리포트', html)
        self.assertIn('data-testid="growth-report-entry"', html)
        self.assertIn('포인트 입력', html)
        self.assertIn('btn btn-outline-primary" data-testid="growth-report-entry"', html)

    def test_children_list_has_growth_link(self):
        self._login(self.teacher)
        html = self.client.get('/children').get_data(as_text=True)
        self.assertIn(f'/children/{self.child.id}/growth', html)
        self.assertIn('title="성장 리포트"', html)
        self.assertIn('data-testid="growth-report-entry"', html)

    def test_viewer_does_not_see_teacher_growth_cta(self):
        self._login(self.viewer)
        home = self.client.get('/viewer').get_data(as_text=True)
        self.assertNotIn(f'/children/{self.child.id}/growth', home)
        self.assertNotIn('성장 리포트', home)
        detail = self.client.get(f'/children/{self.child.id}', follow_redirects=False)
        self.assertEqual(detail.status_code, 302)
        self.assertIn('/viewer', detail.headers.get('Location', ''))
        listing = self.client.get('/children', follow_redirects=False)
        self.assertEqual(listing.status_code, 302)
        report = self.client.get(f'/viewer/report/{self.child.viewer_slug}').get_data(as_text=True)
        self.assertNotIn(f'/children/{self.child.id}/growth', report)
        self.assertNotIn('성장 리포트', report)

    def test_sidebar_print_label_keeps_endpoint(self):
        self._login(self.teacher)
        html = self.client.get('/dashboard').get_data(as_text=True)
        self.assertIn('출력용 리포트', html)
        self.assertIn('/settings/print/children', html)
        self.assertNotIn('개인 리포트', html)
        print_page = self.client.get('/settings/print/children')
        self.assertEqual(print_page.status_code, 200)

    def test_settings_roles_and_existing_form_hrefs(self):
        self._login(self.teacher)
        index = self.client.get('/settings').get_data(as_text=True)
        self.assertIn('/settings/setup', index)
        self.assertIn('센터 운영 설정', index)
        self.assertIn('/settings/learning-subjects', index)

        hub = self.client.get('/settings/setup')
        self.assertEqual(hub.status_code, 200)
        html = hub.get_data(as_text=True)
        self.assertIn('/settings/learning-subjects', html)
        self.assertIn('/settings/study-calendar', html)
        self.assertIn('/settings/subject-weekdays', html)
        self.assertIn('/settings/non-study-days', html)
        self.assertIn('/settings/workbook-plans', html)
        self.assertIn('/settings/points', html)
        self.assertIn('/settings/manual-presets', html)
        self.assertIn('/books', html)
        self.assertIn('기본값(월~금) 사용 중', html)
        self.assertIn('data-next-key="center_study_weekdays"', html)
        self.assertNotIn('setup 75', html)
        self.assertNotIn('75%', html)
        self.assertIn('data-status="optional"', html)
        calendar_before = CenterStudyCalendar.query.count()
        self.client.get('/settings/setup')
        self.assertEqual(CenterStudyCalendar.query.count(), calendar_before)

        self._login(self.director)
        self.assertEqual(self.client.get('/settings/setup').status_code, 200)

    def test_general_user_blocked_from_setup_hub(self):
        self._login(self.general)
        blocked = self.client.get('/settings/setup', follow_redirects=False)
        self.assertEqual(blocked.status_code, 302)
        self.assertIn('/dashboard', blocked.headers.get('Location', ''))

    def test_viewer_blocked_from_setup_hub(self):
        self._login(self.viewer)
        viewer_blocked = self.client.get('/settings/setup', follow_redirects=False)
        self.assertEqual(viewer_blocked.status_code, 302)
        self.assertIn('/viewer', viewer_blocked.headers.get('Location', ''))
