"""Teacher evidence packet: whitelist projection. LLM/provider 없음."""
from __future__ import annotations

import inspect
import json
import unittest
from datetime import date
from unittest.mock import patch

from tests.helpers import bootstrap_test_app, local_development_sqlite_path, resolved_engine_sqlite_path

app, db = bootstrap_test_app()

from app import Child, DailyPoints, User  # noqa: E402
from feature_models import (  # noqa: E402
    ACTOR_TEACHER,
    POLICY_VERSION_GENERAL_V2,
    Book,
    ChildReading,
    LearningProgressEntry,
    LearningSubject,
    ReadingDay,
)
from features.growth.copy import (
    LEARNING_PAGE_ADVANCE_RECENT_WINDOW_BEST,
    READING_DAYS_RECENT_WINDOW_BEST,
)
from features.growth.evidence_packet import (  # noqa: E402
    AUDIENCE_TEACHER,
    SCHEMA_VERSION,
    SELECTED_INSIGHT_LIMIT,
    build_teacher_evidence_packet,
    collect_evidence_ids,
)
from features.growth.metrics import metrics_bundle  # noqa: E402
from features.growth.service import INSIGHT_LIMIT, build_growth_view_model  # noqa: E402
from features.growth.windows import current_window, previous_window  # noqa: E402
from features.planning.service import create_workbook_plan, set_child_weekdays_override  # noqa: E402
from features.planning.workload import WORKLOAD_KIND_ESTIMATED, WORKLOAD_KIND_EXACT  # noqa: E402
from features.progress.service import ensure_default_subjects  # noqa: E402


AS_OF = date(2026, 12, 15)
CURRENT = current_window(AS_OF, 30)
PREV = previous_window(AS_OF, 30)
PREV1 = {'start': date(2026, 10, 17), 'end': date(2026, 11, 15)}
PREV2 = {'start': date(2026, 9, 17), 'end': date(2026, 10, 16)}

SENTINEL_NAME = 'SENTINEL_CHILD_NAME_ZX9'
SENTINEL_SLUG = 'sentinel-viewer-slug-zx9xxxxxxxx'
SENTINEL_REVIEW = 'SENTINEL_REVIEW_TEXT_ZX9'
SENTINEL_URL = 'https://internal.example.test/nfc/999'

FORBIDDEN_KEYS = {
    'child_id',
    'plan_id',
    'snapshot_id',
    'book_id',
    'user_id',
    'child_reading_id',
    'reading_id',
    'viewer_slug',
    'firebase_uid',
    'review_text',
    'manual_history',
    'change_reason',
    'created_at',
    'created_by',
    'created_by_user_id',
    'password_hash',
    'email',
    'child_cumulative_points',
    'importance',
    'headline',
    'detail',
}


def _windows():
    return CURRENT, PREV


def _reading(*, days=(4, 2), completed=(1, 0), comparable=True, pair=None):
    current, previous = _windows()
    empty_pair = {'sample_count': 0, 'difficulty_average': None, 'fun_average': None}
    return {
        'as_of': AS_OF,
        'window_days': 30,
        'current_window': current,
        'previous_window': previous,
        'available_from': {
            'reading_days': PREV['start'] if comparable else CURRENT['start'],
            'completed': PREV['start'] if comparable else CURRENT['start'],
            'experience_rating_pair': PREV['start'] if pair else None,
        },
        'comparable': {
            'reading_days': comparable,
            'completed': comparable,
            'experience_rating_pair': bool(pair),
        },
        'current': {
            'reading_days': days[0],
            'completed_count': completed[0],
            'paired_experience_rating': pair[0] if pair else empty_pair,
        },
        'previous': {
            'reading_days': days[1],
            'completed_count': completed[1],
            'paired_experience_rating': pair[1] if pair else empty_pair,
        },
    }


def _progress(*, counts=(3, 1), comparable=True):
    current, previous = _windows()
    return {
        'as_of': AS_OF,
        'window_days': 30,
        'current_window': current,
        'previous_window': previous,
        'available_from': {'progress': PREV['start'] if comparable else None},
        'comparable': {'progress': comparable},
        'current': {'progress_entry_count': counts[0], 'progress_entry_count_by_subject': {}},
        'previous': {'progress_entry_count': counts[1], 'progress_entry_count_by_subject': {}},
        'latest_snapshot_by_subject': {},
    }


def _points(*, values=(400, 100), comparable=True, cumulative=1200, live_cache=99999):
    current, previous = _windows()
    return {
        'as_of': AS_OF,
        'window_days': 30,
        'current_window': current,
        'previous_window': previous,
        'available_from': {'points': PREV['start'] if comparable else None},
        'comparable': {'points': comparable},
        'current': {'period_points': values[0], 'point_activity_days': 4, 'manual_points_sum': 0},
        'previous': {'period_points': values[1], 'point_activity_days': 2, 'manual_points_sum': 0},
        'cumulative_as_of': cumulative,
        'current_cumulative': cumulative,
        'child_cumulative_points': live_cache,
    }


def _advance(value, *, status='ok', available=True, title='수학 3-2', window=None):
    return {
        'value': value if available else None,
        'available': available,
        'comparable': available,
        'status': status,
        'textbook_title': title,
        'window': window or dict(CURRENT),
    }


def _subject(
    key='math',
    name='수학',
    *,
    page=40,
    title='수학 3-2',
    recorded_on=date(2026, 12, 10),
    stale=False,
    snapshot_available=True,
    current_advance=20,
    previous_advance=10,
    delta=10,
    advance_status='ok',
    current_available=True,
    previous_available=True,
    trend_comparable=True,
    peer_n=0,
    peer_median=None,
    peer_gap=None,
    peer_available=False,
    peer_status='no_peers',
    plan_status='no_plan',
    workload_kind=None,
    remaining=None,
    days=None,
    required=None,
    target=None,
    weekday_source='center_default',
    weekdays=(0, 1, 2, 3, 4),
    plan_id=40404,
    snapshot_id=50505,
):
    return {
        'subject_key': key,
        'subject_name': name,
        'current_snapshot': {
            'textbook_title': title if snapshot_available else None,
            'page': page if snapshot_available else None,
            'recorded_on': recorded_on if snapshot_available else None,
            'age_days': 5 if snapshot_available else None,
            'stale': stale,
            'available': snapshot_available,
        },
        'page_advance': {
            'current': _advance(
                current_advance,
                status=advance_status if current_available else advance_status,
                available=current_available,
                title=title,
                window=dict(CURRENT),
            ),
            'previous': _advance(
                previous_advance,
                status='ok' if previous_available else 'no_baseline',
                available=previous_available,
                title=title,
                window=dict(PREV),
            ),
            'delta': delta if trend_comparable else None,
            'comparable': trend_comparable,
            'status': advance_status,
        },
        'peer': {
            'textbook_title': title,
            'current_page': page,
            'peer_median': peer_median,
            'peer_n': peer_n,
            'gap': peer_gap,
            'available': peer_available,
            'status': peer_status,
        },
        'plan': {
            'status': plan_status,
            'plan_id': plan_id,
            'snapshot_id': snapshot_id,
            'textbook_title': title,
            'workload_kind': workload_kind,
            'remaining_workload': remaining,
            'remaining_planned_study_days': days,
            'required_per_planned_day': required,
            'target_completion_date': target,
            'weekday_source': weekday_source,
            'effective_weekdays': list(weekdays) if weekdays is not None else None,
        },
    }


def _learning(*, subjects=None, observed=(4, 2)):
    return {
        'as_of': AS_OF,
        'window_days': 30,
        'current_window': dict(CURRENT),
        'previous_window': dict(PREV),
        'max_snapshot_age_days': 21,
        'observed_study_days': {
            'current': observed[0],
            'previous': observed[1],
            'source': 'daily_points.date',
            'proxy': 'point_activity_days',
            'attendance': False,
        },
        'subjects': subjects if subjects is not None else {'math': _subject()},
    }


def _window_fact(start, end, value, *, title=None, available=True):
    return {
        'start': start,
        'end': end,
        'value': value if available else None,
        'available': available,
        'comparable': available,
        'textbook_title': title,
    }


def _rwb(current, prev1, prev2, *, status='ok', title=None):
    if status != 'ok':
        return {
            'current': _window_fact(CURRENT['start'], CURRENT['end'], None, available=False),
            'previous_1': _window_fact(PREV1['start'], PREV1['end'], None, available=False),
            'previous_2': _window_fact(PREV2['start'], PREV2['end'], None, available=False),
            'historical_best': None,
            'historical_best_window': None,
            'margin': None,
            'is_recent_window_best': None,
            'status': status,
        }
    historical = max(prev1, prev2)
    return {
        'current': _window_fact(CURRENT['start'], CURRENT['end'], current, title=title),
        'previous_1': _window_fact(PREV1['start'], PREV1['end'], prev1, title=title),
        'previous_2': _window_fact(PREV2['start'], PREV2['end'], prev2, title=title),
        'historical_best': historical,
        'historical_best_window': dict(PREV1) if prev1 >= prev2 else dict(PREV2),
        'margin': current - historical,
        'is_recent_window_best': current > historical,
        'status': 'ok',
    }


def _recent(**kwargs):
    missing = _rwb(0, 0, 0, status='insufficient_history')
    return {
        'as_of': AS_OF,
        'window_days': 30,
        'window_count': 3,
        'lookback_days': 90,
        'current_window': dict(CURRENT),
        'previous_1_window': dict(PREV1),
        'previous_2_window': dict(PREV2),
        'reading_days': kwargs.get('reading_days', missing),
        'reading_completions': kwargs.get('completions', missing),
        'points': kwargs.get('points', missing),
        'learning': kwargs.get('learning') or {},
    }


def _bundle(**kwargs):
    payload = {
        'reading': kwargs.get('reading', _reading()),
        'progress': kwargs.get('progress', _progress()),
        'points': kwargs.get('points', _points()),
        'learning': kwargs.get('learning', _learning()),
        'recent_window_bests': kwargs.get('recent', _recent()),
    }
    if 'point_composition' in kwargs:
        payload['point_composition'] = kwargs['point_composition']
    return payload


def _packet(bundle=None, **kwargs):
    return build_teacher_evidence_packet(bundle or _bundle(), **kwargs)


def _walk_keys(node, found=None):
    found = found if found is not None else set()
    if isinstance(node, dict):
        for key, value in node.items():
            found.add(str(key))
            _walk_keys(value, found)
    elif isinstance(node, list):
        for item in node:
            _walk_keys(item, found)
    return found


def _walk_strings(node, found=None):
    found = found if found is not None else []
    if isinstance(node, str):
        found.append(node)
    elif isinstance(node, dict):
        for key, value in node.items():
            found.append(str(key))
            _walk_strings(value, found)
    elif isinstance(node, list):
        for item in node:
            _walk_strings(item, found)
    return found


class EvidencePacketContractTests(unittest.TestCase):
    def _assert_jsonable(self, packet):
        encoded = json.dumps(packet)
        loaded = json.loads(encoded)
        self.assertEqual(loaded, packet)

    def _assert_privacy(self, packet, extra_sentinels=()):
        keys = {key.lower() for key in _walk_keys(packet)}
        for forbidden in FORBIDDEN_KEYS:
            self.assertNotIn(forbidden, keys, forbidden)
        blob = json.dumps(packet)
        for sentinel in (SENTINEL_NAME, SENTINEL_SLUG, SENTINEL_REVIEW, SENTINEL_URL, *extra_sentinels):
            self.assertNotIn(sentinel, blob)
        for text in _walk_strings(packet):
            lowered = text.lower()
            self.assertFalse(lowered.startswith('http://') or lowered.startswith('https://'))
            self.assertNotIn('/nfc/', lowered)

    def _assert_ids(self, packet):
        ids = collect_evidence_ids(packet)
        self.assertEqual(len(ids), len(set(ids)), ids)
        registered = set(ids)
        for item in packet['selected_insights']:
            for evidence_id in item['evidence_ids']:
                self.assertIn(evidence_id, registered, evidence_id)

    def _assert_contract(self, packet):
        self.assertEqual(SCHEMA_VERSION, 'growth_teacher_evidence_v2')
        self.assertEqual(packet['schema_version'], SCHEMA_VERSION)
        self.assertEqual(packet['audience'], AUDIENCE_TEACHER)
        self.assertRegex(packet['as_of'], r'^\d{4}-\d{2}-\d{2}$')
        self.assertIn('scope', packet)
        self.assertIn('selected_insights', packet)
        self.assertIn('supporting_facts', packet)
        self.assertEqual(set(packet['supporting_facts']), {'reading', 'points', 'learning', 'rewards'})
        self.assertIn('center_context', packet)
        self.assertNotIn('evidence_id', packet['center_context'])
        self._assert_jsonable(packet)
        self._assert_privacy(packet)
        self._assert_ids(packet)

    def test_limit_matches_growth_service(self):
        self.assertEqual(SELECTED_INSIGHT_LIMIT, INSIGHT_LIMIT)

    def test_builder_is_projection_not_provider(self):
        source = inspect.getsource(inspect.getmodule(build_teacher_evidence_packet))
        self.assertNotIn('metrics_bundle(', source)
        self.assertNotIn('point_composition_from_events', source)
        self.assertNotIn('from features.growth.point_composition', source)
        self.assertNotIn('.query', source)
        self.assertNotIn('openai', source.lower())
        self.assertNotIn('anthropic', source.lower())
        self.assertNotIn('Content Safety', source)
        service_src = inspect.getsource(inspect.getmodule(build_growth_view_model))
        self.assertNotIn('evidence_packet', service_src)

    def test_normal_reading_points_learning_shape(self):
        packet = _packet(grade=3)
        self._assert_contract(packet)
        self.assertEqual(packet['grade'], 3)
        reading = packet['supporting_facts']['reading']
        self.assertEqual(reading['activity_days']['current']['value'], 4)
        self.assertEqual(reading['activity_days']['previous']['value'], 2)
        self.assertEqual(reading['activity_days']['delta']['value'], 2)
        self.assertTrue(reading['activity_days']['comparable'])
        points = packet['supporting_facts']['points']
        self.assertEqual(points['period']['current']['value'], 400)
        self.assertEqual(points['cumulative_as_of']['value'], 1200)
        math = packet['supporting_facts']['learning']['subjects']['math']
        self.assertEqual(math['current_snapshot']['page']['value'], 40)
        self.assertEqual(math['page_advance']['current']['value'], 20)
        observed = packet['supporting_facts']['learning']['observed_study_days']
        self.assertFalse(observed['attendance'])
        self.assertEqual(observed['proxy'], 'point_activity_days')
        self.assertNotIn('recent_windows', packet['scope'])
        encoded = json.dumps(packet)
        self.assertNotIn('99999', encoded)
        self.assertNotIn('40404', encoded)

    def test_actual_zero_keeps_value(self):
        packet = _packet(_bundle(
            reading=_reading(days=(0, 0), completed=(0, 0)),
            points=_points(values=(0, 0), cumulative=0),
            learning=_learning(
                observed=(0, 0),
                subjects={'math': _subject(current_advance=0, previous_advance=0, delta=0)},
            ),
        ))
        self._assert_contract(packet)
        days = packet['supporting_facts']['reading']['activity_days']['current']
        self.assertTrue(days['available'])
        self.assertEqual(days['value'], 0)
        self.assertNotIn('status', days)
        advance = packet['supporting_facts']['learning']['subjects']['math']['page_advance']['current']
        self.assertTrue(advance['available'])
        self.assertEqual(advance['value'], 0)
        cumulative = packet['supporting_facts']['points']['cumulative_as_of']
        self.assertTrue(cumulative['available'])
        self.assertEqual(cumulative['value'], 0)

    def test_unavailable_omits_numeric_value(self):
        packet = _packet(_bundle(
            reading=_reading(comparable=False),
            points=_points(comparable=False, cumulative=None),
            progress=_progress(comparable=False),
        ))
        self._assert_contract(packet)
        days = packet['supporting_facts']['reading']['activity_days']
        self.assertFalse(days['comparable'])
        self.assertFalse(days['current']['available'])
        self.assertNotIn('value', days['current'])
        self.assertEqual(days['current']['status'], 'insufficient_history')
        cumulative = packet['supporting_facts']['points']['cumulative_as_of']
        self.assertFalse(cumulative['available'])
        self.assertNotIn('value', cumulative)

    def test_stale_progress_is_not_zero(self):
        packet = _packet(_bundle(learning=_learning(subjects={'math': _subject(
            stale=True,
            current_available=False,
            previous_available=False,
            trend_comparable=False,
            current_advance=None,
            previous_advance=None,
            delta=None,
            advance_status='stale_endpoint',
        )})))
        advance = packet['supporting_facts']['learning']['subjects']['math']['page_advance']['current']
        self.assertFalse(advance['available'])
        self.assertNotIn('value', advance)
        self.assertEqual(
            packet['supporting_facts']['learning']['subjects']['math']['current_snapshot']['stale'],
            True,
        )

    def test_cross_book_has_no_advance_value(self):
        packet = _packet(_bundle(learning=_learning(subjects={'math': _subject(
            current_available=False,
            previous_available=False,
            trend_comparable=False,
            current_advance=None,
            delta=None,
            advance_status='cross_book',
        )})))
        current = packet['supporting_facts']['learning']['subjects']['math']['page_advance']['current']
        self.assertFalse(current['available'])
        self.assertNotIn('value', current)
        self.assertEqual(current['status'], 'cross_book')

    def test_peer_available_and_small_n_kept(self):
        packet = _packet(_bundle(learning=_learning(subjects={'math': _subject(
            peer_n=1,
            peer_median=30,
            peer_gap=10,
            peer_available=True,
            peer_status='ok',
        )})))
        peer = packet['supporting_facts']['learning']['subjects']['math']['peer']
        self.assertTrue(peer['available'])
        self.assertEqual(peer['n']['value'], 1)
        self.assertEqual(peer['median']['value'], 30)
        self.assertEqual(peer['gap']['value'], 10)

    def test_peer_n0_omits_median(self):
        packet = _packet(_bundle(learning=_learning(subjects={'math': _subject(
            peer_n=0,
            peer_median=None,
            peer_available=False,
            peer_status='no_peers',
        )})))
        peer = packet['supporting_facts']['learning']['subjects']['math']['peer']
        self.assertFalse(peer['available'])
        self.assertEqual(peer['status'], 'no_peers')
        self.assertEqual(peer['n']['value'], 0)
        self.assertNotIn('median', peer)
        self.assertNotIn('gap', peer)

    def test_exact_and_estimated_plan(self):
        estimated = _packet(_bundle(learning=_learning(subjects={'math': _subject(
            plan_status='active',
            workload_kind=WORKLOAD_KIND_ESTIMATED,
            remaining=80,
            days=20,
            required=4,
            target=date(2026, 12, 20),
        )})))
        plan = estimated['supporting_facts']['learning']['subjects']['math']['plan']
        self.assertEqual(plan['workload_kind'], 'estimated')
        self.assertEqual(plan['remaining_workload']['value'], 80)
        exact = _packet(_bundle(learning=_learning(subjects={'math': _subject(
            plan_status='active',
            workload_kind=WORKLOAD_KIND_EXACT,
            remaining=40,
            days=10,
            required=4,
            target=date(2026, 12, 20),
        )})))
        self.assertEqual(
            exact['supporting_facts']['learning']['subjects']['math']['plan']['workload_kind'],
            'exact',
        )

    def test_no_planned_days_keeps_zero_days_without_fake_rate(self):
        packet = _packet(_bundle(learning=_learning(subjects={'math': _subject(
            plan_status='no_remaining_planned_days',
            workload_kind='exact',
            remaining=40,
            days=0,
            required=None,
            weekdays=(),
        )})))
        plan = packet['supporting_facts']['learning']['subjects']['math']['plan']
        self.assertEqual(plan['remaining_planned_days']['value'], 0)
        self.assertNotIn('required_per_planned_day', plan)
        self.assertEqual(plan['effective_weekdays'], [])

    def test_recent_window_selected_insight_ids_resolve(self):
        bundle = _bundle(
            reading=_reading(days=(4, 4)),
            recent=_recent(reading_days=_rwb(15, 13, 10)),
        )
        packet = _packet(bundle)
        self._assert_contract(packet)
        ids = [item['id'] for item in packet['selected_insights']]
        self.assertIn(READING_DAYS_RECENT_WINDOW_BEST, ids)
        rwb = packet['supporting_facts']['reading']['recent_window_activity_days']
        self.assertEqual(rwb['current']['value'], 15)
        self.assertEqual(rwb['margin']['value'], 2)
        self.assertIn('recent_windows', packet['scope'])
        self.assertTrue(all('headline' not in item for item in packet['selected_insights']))

    def test_multi_subject_learning_recent_window(self):
        bundle = _bundle(
            reading=_reading(days=(1, 1), completed=(0, 0)),
            points=_points(values=(50, 50)),
            learning=_learning(subjects={
                'korean': _subject(key='korean', name='국어', title='국어 3-2', current_advance=28),
                'math': _subject(key='math', name='수학', title='수학 3-2', current_advance=44),
            }),
            recent=_recent(learning={
                'korean': _rwb(28, 21, 10, title='국어 3-2'),
                'math': _rwb(44, 32, 20, title='수학 3-2'),
            }),
        )
        packet = _packet(bundle)
        self._assert_contract(packet)
        selected = packet['selected_insights'][0]
        self.assertEqual(selected['id'], LEARNING_PAGE_ADVANCE_RECENT_WINDOW_BEST)
        subjects = packet['supporting_facts']['learning']['subjects']
        self.assertIn('recent_window', subjects['korean'])
        self.assertIn('recent_window', subjects['math'])
        self.assertEqual(subjects['math']['recent_window']['margin']['value'], 12)

    def test_negative_page_correction_is_preserved(self):
        packet = _packet(_bundle(learning=_learning(subjects={'math': _subject(
            current_advance=-5,
            previous_advance=10,
            delta=-15,
        )})))
        current = packet['supporting_facts']['learning']['subjects']['math']['page_advance']['current']
        self.assertTrue(current['available'])
        self.assertEqual(current['value'], -5)

    def test_insufficient_history_recent_window_not_dumped(self):
        packet = _packet(_bundle(recent=_recent()))
        self._assert_contract(packet)
        self.assertNotIn('recent_window_activity_days', packet['supporting_facts']['reading'])
        self.assertNotIn('recent_windows', packet['scope'])

    def test_dates_are_iso_strings(self):
        packet = _packet()
        dumped = json.dumps(packet)
        self.assertNotIn('datetime.date', dumped)
        self.assertIn('"as_of": "2026-12-15"', dumped)

    def test_grade_is_optional_and_name_is_never_added(self):
        packet = _packet()
        self.assertNotIn('grade', packet)
        self.assertNotIn('name', _walk_keys(packet))


def _composition_side(
    *,
    net=0,
    earn=0,
    spend=0,
    subjects=None,
    textbook=0,
    praise=0,
    help_points=0,
    extra=0,
    extra_by_subject=None,
):
    return {
        'net_points': net,
        'total_earn_points': earn,
        'total_spend_points': spend,
        'subjects': subjects or {},
        'manual': {
            'earn_points': 999,
            'earn_count': 9,
            'spend_points': -999,
            'spend_count': 9,
        },
        'textbook': {'points': textbook, 'count': 7, 'by_subject': {'ssen': {'points': textbook, 'count': 7}}},
        'praise': {'points': praise, 'count': 3},
        'help': {'points': help_points, 'count': 2},
        'extra_learning': {
            'points': extra,
            'count': 4,
            'by_subject': extra_by_subject or {},
        },
        'material': {
            'points': -50,
            'count': 1,
            'by_item': {'print': {'points': -50, 'count': 1}},
        },
        'stationery': {
            'points': -300,
            'count': 1,
            'by_item': {'pencil': {'points': -300, 'count': 1}},
        },
        'unclassified': {
            'earn_points': 80,
            'earn_count': 1,
            'spend_points': 0,
            'spend_count': 0,
        },
        'raw_subject': '원문과목유출금지',
        'raw_reason': '원문사유유출금지',
    }


def _composition_payload(*, current=None, previous=None):
    return {
        'as_of': AS_OF,
        'window_days': 30,
        'current_window': dict(CURRENT),
        'previous_window': dict(PREV),
        'current': current if current is not None else _composition_side(),
        'previous': previous if previous is not None else _composition_side(),
    }


class EvidencePacketCompositionTests(unittest.TestCase):
    def _packet(self, **kwargs):
        comparable = kwargs.pop('comparable', True)
        points = kwargs.pop('points', _points(comparable=comparable))
        composition = kwargs.pop(
            'point_composition',
            _composition_payload(
                current=_composition_side(
                    net=800,
                    earn=1100,
                    spend=-300,
                    subjects={
                        'korean': {'points': 200, 'active_days': 4},
                        'math': {'points': 150, 'active_days': 3},
                    },
                    textbook=3000,
                    praise=100,
                    help_points=80,
                    extra=400,
                    extra_by_subject={
                        'math': {'points': 300, 'count': 2},
                        'korean': {'points': 100, 'count': 1},
                    },
                ),
                previous=_composition_side(
                    net=250,
                    earn=350,
                    spend=-100,
                    subjects={
                        'korean': {'points': 100, 'active_days': 2},
                    },
                    textbook=0,
                    praise=50,
                    help_points=0,
                    extra=0,
                    extra_by_subject={},
                ),
            ),
        )
        return _packet(_bundle(points=points, point_composition=composition, **kwargs))

    def test_composition_values_project_without_recalc(self):
        packet = self._packet()
        composition = packet['supporting_facts']['points']['composition']
        totals = composition['totals']
        self.assertEqual(totals['net_points']['current']['value'], 800)
        self.assertEqual(totals['net_points']['previous']['value'], 250)
        self.assertEqual(totals['net_points']['delta']['value'], 550)
        self.assertTrue(totals['net_points']['comparable'])
        self.assertEqual(totals['total_earn_points']['current']['value'], 1100)
        self.assertEqual(totals['total_earn_points']['previous']['value'], 350)
        self.assertEqual(totals['total_earn_points']['delta']['value'], 750)
        self.assertEqual(totals['total_spend_points']['current']['value'], -300)
        self.assertEqual(totals['total_spend_points']['previous']['value'], -100)
        self.assertEqual(totals['total_spend_points']['delta']['value'], -200)

    def test_subject_points_and_active_days(self):
        packet = self._packet()
        subjects = packet['supporting_facts']['points']['composition']['subjects']
        self.assertEqual(set(subjects), {'korean', 'math'})
        korean = subjects['korean']
        self.assertEqual(korean['points']['current']['value'], 200)
        self.assertEqual(korean['points']['previous']['value'], 100)
        self.assertEqual(korean['points']['delta']['value'], 100)
        self.assertEqual(korean['active_days']['current']['value'], 4)
        self.assertEqual(korean['active_days']['previous']['value'], 2)
        self.assertEqual(korean['active_days']['delta']['value'], 2)
        math = subjects['math']
        self.assertEqual(math['points']['current']['value'], 150)
        self.assertEqual(math['points']['previous']['value'], 0)
        self.assertEqual(math['points']['delta']['value'], 150)
        self.assertEqual(math['active_days']['current']['value'], 3)
        self.assertEqual(math['active_days']['previous']['value'], 0)

    def test_category_and_extra_learning_by_subject(self):
        packet = self._packet()
        composition = packet['supporting_facts']['points']['composition']
        self.assertEqual(composition['textbook']['points']['current']['value'], 3000)
        self.assertEqual(composition['textbook']['points']['previous']['value'], 0)
        self.assertEqual(composition['textbook']['points']['delta']['value'], 3000)
        self.assertEqual(composition['praise']['points']['current']['value'], 100)
        self.assertEqual(composition['praise']['points']['previous']['value'], 50)
        self.assertEqual(composition['praise']['points']['delta']['value'], 50)
        self.assertEqual(composition['help']['points']['current']['value'], 80)
        self.assertEqual(composition['help']['points']['previous']['value'], 0)
        extra = composition['extra_learning']
        self.assertEqual(extra['points']['current']['value'], 400)
        self.assertEqual(extra['points']['previous']['value'], 0)
        self.assertEqual(extra['points']['delta']['value'], 400)
        by_subject = extra['by_subject']
        self.assertEqual(set(by_subject), {'korean', 'math'})
        self.assertEqual(by_subject['math']['points']['current']['value'], 300)
        self.assertEqual(by_subject['math']['points']['previous']['value'], 0)
        self.assertEqual(by_subject['korean']['points']['current']['value'], 100)
        self.assertEqual(by_subject['korean']['points']['previous']['value'], 0)

    def test_material_stationery_and_raw_text_are_not_leaked(self):
        packet = self._packet()
        composition = packet['supporting_facts']['points']['composition']
        self.assertEqual(
            set(composition),
            {'totals', 'subjects', 'textbook', 'praise', 'help', 'extra_learning'},
        )
        blob = json.dumps(packet, ensure_ascii=False)
        for forbidden in (
            'material', 'stationery', 'unclassified', 'by_item', 'print', 'pencil',
            'raw_subject', 'raw_reason', '원문과목유출금지', '원문사유유출금지',
            'manual_history',
        ):
            self.assertNotIn(forbidden, blob)
        self.assertNotIn('earn_count', blob)
        self.assertNotIn('"count": 7', blob)
        self.assertNotIn('"count": 4', blob)

    def test_evidence_ids_are_indexed_with_correct_units(self):
        from features.growth.ai.validator import collect_evidence_index
        packet = self._packet()
        ids = collect_evidence_ids(packet)
        expected = [
            'points.composition.totals.net_points.current',
            'points.composition.totals.net_points.previous',
            'points.composition.totals.net_points.delta',
            'points.composition.totals.total_earn_points.current',
            'points.composition.totals.total_earn_points.previous',
            'points.composition.totals.total_earn_points.delta',
            'points.composition.totals.total_spend_points.current',
            'points.composition.totals.total_spend_points.previous',
            'points.composition.totals.total_spend_points.delta',
            'points.composition.subjects.korean.active_days.current',
            'points.composition.subjects.korean.points.current',
            'points.composition.subjects.math.active_days.current',
            'points.composition.subjects.math.points.current',
            'points.composition.textbook.points.current',
            'points.composition.praise.points.current',
            'points.composition.help.points.current',
            'points.composition.extra_learning.points.current',
            'points.composition.extra_learning.by_subject.korean.points.current',
            'points.composition.extra_learning.by_subject.math.points.current',
        ]
        for evidence_id in expected:
            self.assertIn(evidence_id, ids, evidence_id)
        index = collect_evidence_index(packet)
        self.assertEqual(index['points.composition.totals.net_points.current'].unit, 'point')
        self.assertEqual(index['points.composition.subjects.korean.points.current'].unit, 'point')
        self.assertEqual(index['points.composition.textbook.points.current'].unit, 'point')
        self.assertEqual(index['points.composition.extra_learning.by_subject.math.points.current'].unit, 'point')
        self.assertEqual(index['points.composition.subjects.korean.active_days.current'].unit, 'day')
        self.assertEqual(index['points.composition.subjects.math.active_days.delta'].unit, 'day')

    def test_missing_composition_is_omitted(self):
        packet = _packet(_bundle())
        self.assertNotIn('composition', packet['supporting_facts']['points'])

    def test_incomparable_points_hide_composition_values(self):
        packet = self._packet(comparable=False)
        net = packet['supporting_facts']['points']['composition']['totals']['net_points']
        self.assertFalse(net['comparable'])
        self.assertFalse(net['current']['available'])
        self.assertNotIn('value', net['current'])
        days = packet['supporting_facts']['points']['composition']['subjects']['korean']['active_days']
        self.assertFalse(days['current']['available'])
        self.assertNotIn('value', days['current'])


class EvidencePacketCenterPolicyTests(unittest.TestCase):
    def test_current_center_policy_text_is_in_packet(self):
        from features.growth.center_policy import CURRENT_CENTER_POLICY_TEXT
        packet = _packet()
        context = packet['center_context']
        self.assertTrue(context['available'])
        self.assertEqual(context['policy_text'], CURRENT_CENTER_POLICY_TEXT)
        self.assertIn('200점', context['policy_text'])
        self.assertIn('쎈', context['policy_text'])
        self.assertIn('독서기록장', context['policy_text'])
        self.assertNotIn('evidence_id', context)

    def test_missing_policy_does_not_invent_text(self):
        with patch(
            'features.growth.evidence_packet.get_current_center_policy_text',
            return_value=None,
        ):
            packet = _packet()
        context = packet['center_context']
        self.assertFalse(context['available'])
        self.assertIsNone(context['policy_text'])
        self.assertNotIn('200점', json.dumps(packet, ensure_ascii=False))

    def test_policy_is_not_collected_as_evidence(self):
        from features.growth.ai.validator import collect_evidence_index
        packet = _packet()
        self.assertIn('200점', packet['center_context']['policy_text'])
        ids = collect_evidence_ids(packet)
        self.assertNotIn('center_context.policy_text', ids)
        self.assertFalse(any(item.startswith('center_context') for item in ids))
        index = collect_evidence_index(packet)
        values = {
            fact.value for fact in index.values()
            if fact.available and not isinstance(fact.value, bool)
        }
        self.assertNotIn(200, values)
        self.assertNotIn('200점', index)

    def test_policy_numbers_do_not_justify_child_score_claims(self):
        from features.growth.ai.validator import (
            CODE_UNSUPPORTED_NUMERIC_CLAIM,
            validate_teacher_interpretation,
        )
        from tests.test_growth_ai_validator import _output
        packet = _packet()
        result = validate_teacher_interpretation(
            packet,
            _output(
                summary='이 아동은 최근 200점을 받았습니다.',
                summary_ids=['points.period.current'],
            ),
        )
        self.assertFalse(result.valid)
        self.assertIn(CODE_UNSUPPORTED_NUMERIC_CLAIM, [item.code for item in result.violations])

    def test_overlong_policy_is_clipped(self):
        from features.growth.center_policy import MAX_CENTER_POLICY_TEXT_LEN, normalize_center_policy_text
        text = '가' * (MAX_CENTER_POLICY_TEXT_LEN + 50)
        self.assertEqual(len(normalize_center_policy_text(text)), MAX_CENTER_POLICY_TEXT_LEN)
        self.assertIsNone(normalize_center_policy_text('   '))
        self.assertIsNone(normalize_center_policy_text(None))


class EvidencePacketDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.ctx = app.app_context()
        self.ctx.push()
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.assertNotEqual(resolved_engine_sqlite_path(db), local_development_sqlite_path())
        self.teacher = User(
            username='packet_teacher',
            name='패킷교사',
            role='돌봄선생님',
            email='packet@example.test',
            password_hash='',
        )
        self.child = Child(
            name=SENTINEL_NAME,
            grade=3,
            viewer_slug=SENTINEL_SLUG,
        )
        db.session.add_all([self.teacher, self.child])
        db.session.commit()
        ensure_default_subjects()
        self.math = LearningSubject.query.filter_by(key='math').one()
        self.korean = LearningSubject.query.filter_by(key='korean').one()

    def tearDown(self):
        db.session.remove()
        self.ctx.pop()

    def _progress(self, on, *, page, title='우등생 수학 3-2', subject=None, child=None):
        row = LearningProgressEntry(
            child_id=(child or self.child).id,
            learning_subject_id=(subject or self.math).id,
            recorded_on=on,
            textbook_title=title,
            page=page,
            created_by_user_id=self.teacher.id,
        )
        db.session.add(row)
        db.session.commit()
        return row

    def _daily(self, on, *, korean=100, child=None):
        row = DailyPoints(
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
        )
        db.session.add(row)
        db.session.commit()
        return row

    def _reading_day(self, on):
        book = Book(title='패킷책', normalized_key='패킷책', is_active=True, grade_band='2-3')
        db.session.add(book)
        db.session.flush()
        reading = ChildReading(
            child_id=self.child.id,
            book_id=book.id,
            started_on=on,
            status='in_progress',
            policy_version=POLICY_VERSION_GENERAL_V2,
            created_by_user_id=self.teacher.id,
            actor_type=ACTOR_TEACHER,
        )
        db.session.add(reading)
        db.session.flush()
        db.session.add(ReadingDay(
            child_reading_id=reading.id,
            date=on,
            review_text=SENTINEL_REVIEW,
            created_by_user_id=self.teacher.id,
            actor_type=ACTOR_TEACHER,
            policy_version=POLICY_VERSION_GENERAL_V2,
        ))
        db.session.commit()

    def _packet(self, as_of=date(2026, 8, 22)):
        bundle = metrics_bundle(self.child.id, as_of=as_of, window_days=30)
        return bundle, build_teacher_evidence_packet(bundle, grade=self.child.grade)

    def test_privacy_sentinels_and_plan_id_are_stripped(self):
        self._reading_day(date(2026, 8, 20))
        self._progress(date(2026, 7, 20), page=80)
        self._progress(date(2026, 8, 15), page=120)
        self._daily(date(2026, 8, 20), korean=100)
        plan = create_workbook_plan(
            grade=3,
            learning_subject_id=self.math.id,
            textbook_title='우등생 수학 3-2',
            start_page=10,
            end_page=184,
            start_date=date(2026, 7, 1),
            target_completion_date=date(2026, 12, 20),
            exclusion_ranges_text=None,
        )
        bundle, packet = self._packet()
        encoded = json.dumps(packet)
        self.assertNotIn(SENTINEL_NAME, encoded)
        self.assertNotIn(SENTINEL_SLUG, encoded)
        self.assertNotIn(SENTINEL_REVIEW, encoded)
        self.assertNotIn('plan_id', encoded)
        self.assertNotIn('plan_id', _walk_keys(packet))
        self.assertNotIn(SENTINEL_URL, encoded)
        self.assertEqual(packet['grade'], 3)
        self.assertEqual(bundle['learning']['subjects']['math']['plan']['plan_id'], plan.id)

    def test_packet_copies_canonical_numbers_without_recalc(self):
        self._progress(date(2026, 7, 20), page=80)
        self._progress(date(2026, 8, 15), page=120)
        self._daily(date(2026, 8, 20), korean=200)
        bundle, packet = self._packet()
        math = bundle['learning']['subjects']['math']
        packet_math = packet['supporting_facts']['learning']['subjects']['math']
        self.assertEqual(
            packet_math['page_advance']['current']['value'],
            math['page_advance']['current']['value'],
        )
        period = packet['supporting_facts']['points']['period']
        if bundle['points']['comparable']['points'] is True:
            self.assertEqual(period['current']['value'], bundle['points']['current']['period_points'])
        else:
            self.assertFalse(period['current']['available'])
            self.assertNotIn('value', period['current'])
        cumulative = packet['supporting_facts']['points']['cumulative_as_of']
        if bundle['points']['cumulative_as_of'] is None:
            self.assertFalse(cumulative['available'])
            self.assertNotIn('value', cumulative)
        else:
            self.assertEqual(cumulative['value'], bundle['points']['cumulative_as_of'])
        composition = packet['supporting_facts']['points']['composition']
        current = bundle['point_composition']['current']
        if bundle['points']['comparable']['points'] is True:
            self.assertEqual(
                composition['totals']['net_points']['current']['value'],
                current['net_points'],
            )
            korean = (current.get('subjects') or {}).get('korean') or {}
            if korean:
                self.assertEqual(
                    composition['subjects']['korean']['points']['current']['value'],
                    korean['points'],
                )
        self.assertNotIn('material', composition)
        self.assertNotIn('stationery', composition)
        self.assertNotIn('unclassified', composition)

    def test_view_model_path_does_not_use_packet(self):
        self._progress(date(2026, 8, 15), page=40)
        view = build_growth_view_model(self.child, as_of=date(2026, 8, 22))
        self.assertIn('insights', view)
        self.assertIn('bundle', view)
        self.assertNotIn('schema_version', view)
        self.assertEqual(view['child'].name, SENTINEL_NAME)

    def test_peer_and_empty_weekdays_from_live_metrics(self):
        as_of = date(2026, 8, 22)
        self._progress(date(2026, 8, 20), page=40)
        peer = Child(name='동료패킷', grade=3, viewer_slug='packetpeerchildslugxxxxx')
        db.session.add(peer)
        db.session.commit()
        self._progress(date(2026, 8, 19), page=30, child=peer)
        create_workbook_plan(
            grade=3,
            learning_subject_id=self.math.id,
            textbook_title='우등생 수학 3-2',
            start_page=1,
            end_page=100,
            start_date=date(2026, 7, 1),
            target_completion_date=date(2026, 12, 20),
            exclusion_ranges_text='90-95',
        )
        set_child_weekdays_override(self.child.id, [])
        bundle, packet = self._packet(as_of)
        peer_fact = packet['supporting_facts']['learning']['subjects']['math']['peer']
        self.assertTrue(peer_fact['available'])
        self.assertEqual(peer_fact['n']['value'], 1)
        self.assertEqual(peer_fact['median']['value'], 30)
        plan = packet['supporting_facts']['learning']['subjects']['math']['plan']
        self.assertEqual(plan['workload_kind'], 'exact')
        self.assertEqual(plan['effective_weekdays'], [])
        self.assertEqual(plan['remaining_planned_days']['value'], 0)
        self.assertNotIn('required_per_planned_day', plan)
        self.assertNotIn('동료패킷', json.dumps(packet))

    def test_empty_history_is_unavailable_not_zero(self):
        bundle, packet = self._packet()
        days = packet['supporting_facts']['reading']['activity_days']['current']
        self.assertFalse(days['available'])
        self.assertNotIn('value', days)
        self.assertFalse(packet['supporting_facts']['points']['cumulative_as_of']['available'])
        snapshot = packet['supporting_facts']['learning']['subjects']['math']['current_snapshot']
        self.assertFalse(snapshot['available'])
        self.assertNotIn('value', snapshot['page'])
        self.assertEqual(bundle['reading']['current']['reading_days'], 0)
        composition = packet['supporting_facts']['points'].get('composition')
        if composition:
            self.assertFalse(composition['totals']['net_points']['current']['available'])
            self.assertNotIn('value', composition['totals']['net_points']['current'])
