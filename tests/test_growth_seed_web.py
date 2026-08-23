"""Growth seed 개발 UI: production/postgres 거부, temp SQLite에서만 실행."""
from __future__ import annotations

import os
import unittest
from unittest import mock

from tests.helpers import (
    assert_test_engine_isolated,
    bootstrap_test_app,
    local_development_sqlite_path,
)

app, db = bootstrap_test_app()

from app import Child, User  # noqa: E402
from scripts.seed.seed_growth_scenarios import (  # noqa: E402
    ALLOW_ENV,
    CANONICAL_ANCHOR,
    NAME_PREFIX,
    SCENARIO_CATALOG,
    growth_seed_web_denial_reason,
)


AS_OF = CANONICAL_ANCHOR


class GrowthSeedWebTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        assert_test_engine_isolated(db)
        self.assertNotEqual(
            assert_test_engine_isolated(db),
            local_development_sqlite_path(),
        )
        self.teacher = User(
            username='growth_web_teacher',
            name='시드교사',
            role='돌봄선생님',
            email='growth-web-teacher@example.test',
            password_hash='',
        )
        db.session.add(self.teacher)
        self.child_a = Child(name='아동A', grade=5, viewer_slug='aaaaaaaaaaaaaaaaaaaaaaaa')
        self.child_b = Child(name='아동B', grade=3, viewer_slug='bbbbbbbbbbbbbbbbbbbbbbbb')
        db.session.add_all([self.child_a, self.child_b])
        db.session.commit()
        self.client = app.test_client()
        os.environ.pop(ALLOW_ENV, None)

    def tearDown(self):
        os.environ.pop(ALLOW_ENV, None)
        os.environ.pop('FLASK_ENV', None)
        db.session.remove()
        self.ctx.pop()

    def _login(self):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(self.teacher.id)
            sess['_fresh'] = True

    def _post_growth(self, **extra):
        data = {
            'action': 'growth_seed',
            'growth_seed_anchor': AS_OF.isoformat(),
        }
        data.update(extra)
        return self.client.post('/settings/data', data=data, follow_redirects=False)

    def test_production_runtime_rejects_post_and_hides_button(self):
        self._login()
        with mock.patch.dict(os.environ, {'FLASK_ENV': 'production'}, clear=False):
            get_resp = self.client.get('/settings/data')
            self.assertEqual(get_resp.status_code, 200)
            body = get_resp.get_data(as_text=True)
            self.assertIn('시드 데이터 실행', body)
            self.assertNotIn('Growth 테스트 데이터 생성', body)
            post_resp = self._post_growth()
            self.assertEqual(post_resp.status_code, 403)
            self.assertIn('운영 환경', post_resp.get_data(as_text=True))
        self.assertEqual(Child.query.filter(Child.name.startswith(NAME_PREFIX)).count(), 0)
        self.assertEqual(Child.query.count(), 2)

    def test_postgres_uri_is_rejected(self):
        self._login()
        previous_uri = app.config.get('SQLALCHEMY_DATABASE_URI')
        previous_env = os.environ.get('DATABASE_URL')
        try:
            app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://example.invalid/db'
            os.environ['DATABASE_URL'] = 'postgresql://example.invalid/db'
            get_resp = self.client.get('/settings/data')
            self.assertEqual(get_resp.status_code, 200)
            self.assertNotIn('Growth 테스트 데이터 생성', get_resp.get_data(as_text=True))
            post_resp = self._post_growth()
            self.assertEqual(post_resp.status_code, 403)
            self.assertIn('PostgreSQL', post_resp.get_data(as_text=True))
            self.assertNotIn('postgresql://', post_resp.get_data(as_text=True))
        finally:
            app.config['SQLALCHEMY_DATABASE_URI'] = previous_uri
            if previous_env is None:
                os.environ.pop('DATABASE_URL', None)
            else:
                os.environ['DATABASE_URL'] = previous_env
        self.assertEqual(Child.query.count(), 2)

    def test_non_local_sqlite_without_testing_flag_is_rejected(self):
        self._login()
        with mock.patch.dict(os.environ, {'CLC_TESTING': ''}, clear=False):
            os.environ.pop('CLC_TESTING', None)
            self.assertEqual(growth_seed_web_denial_reason(), 'not_local')
            post_resp = self._post_growth()
            self.assertEqual(post_resp.status_code, 403)
        self.assertEqual(Child.query.filter(Child.name.startswith(NAME_PREFIX)).count(), 0)

    def test_temp_sqlite_can_create_seed_children_and_preserve_existing(self):
        self._login()
        get_resp = self.client.get('/settings/data')
        body = get_resp.get_data(as_text=True)
        self.assertIn('시드 데이터 실행', body)
        self.assertIn('Growth 테스트 데이터 생성', body)
        self.assertIn('name="growth_seed_anchor"', body)
        self.assertIn('value="2026-12-15"', body)

        resp = self._post_growth()
        self.assertIn(resp.status_code, (302, 200))
        self.assertEqual(os.environ.get(ALLOW_ENV), None)
        names = {child.name for child in Child.query.all()}
        self.assertIn('아동A', names)
        self.assertIn('아동B', names)
        seed_names = {item['name'] for item in SCENARIO_CATALOG.values()}
        self.assertTrue(seed_names <= names)
        self.assertEqual(Child.query.filter(Child.name.startswith(NAME_PREFIX)).count(), 22)
        self.assertEqual(Child.query.count(), 24)

    def test_rerun_does_not_duplicate_seed_children(self):
        self._login()
        first = self._post_growth()
        self.assertIn(first.status_code, (302, 200))
        second = self._post_growth()
        self.assertIn(second.status_code, (302, 200))
        self.assertEqual(Child.query.filter(Child.name.startswith(NAME_PREFIX)).count(), 22)
        self.assertEqual(Child.query.filter_by(name='아동A').count(), 1)
        self.assertEqual(Child.query.filter_by(name='아동B').count(), 1)
        self.assertEqual(Child.query.count(), 24)

    def test_seed_basic_button_and_route_remain(self):
        self._login()
        get_resp = self.client.get('/settings/data')
        self.assertIn('시드 데이터 실행', get_resp.get_data(as_text=True))
        self.assertIn('name="action" value="seed_data"', get_resp.get_data(as_text=True))
        with mock.patch('scripts.seed.seed_basic.main') as seed_main:
            resp = self.client.post(
                '/settings/data',
                data={'action': 'seed_data'},
                follow_redirects=False,
            )
            self.assertIn(resp.status_code, (302, 200))
            seed_main.assert_called_once()
        self.assertEqual(Child.query.count(), 2)
        self.assertEqual(Child.query.filter(Child.name.startswith(NAME_PREFIX)).count(), 0)


if __name__ == '__main__':
    unittest.main()
