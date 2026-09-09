"""Growth vNext Step 7: Evidence Packet v3 / selector / reading adapter.

전체 unittest discover가 아니다. 이 파일은 packet/selector/reading-safe/hash 계약을 본다.
"""
from __future__ import annotations

import json
import unittest
from datetime import date

from tests.helpers import bootstrap_test_app

app, db = bootstrap_test_app()

from features.growth.ai.hashing import packet_hash
from features.growth.evidence_packet import (
    SCHEMA_VERSION,
    SELECTED_INSIGHT_LIMIT,
    build_teacher_evidence_packet,
    collect_evidence_ids,
)
from features.growth.evidence_selector import (
    TIER_MAJOR_LABEL,
    TIER_REFERENCE,
    TIER_SUPPORTING,
    TIER_UNAVAILABLE,
    select_evidence_candidates,
    select_major_insights,
)
from features.growth.reading_evidence import growth_reading_evidence
from tests.test_growth_evidence_packet import (
    SENTINEL_REVIEW,
    _bundle,
    _canonical,
    _canonical_subject,
    _composition_payload,
    _composition_side,
    _packet,
    _points,
    _reading,
)


def _blob(packet):
    return json.dumps(packet, ensure_ascii=False)


class EvidencePacketV3Tests(unittest.TestCase):
    def test_schema_version_v3(self):
        packet = _packet()
        self.assertEqual(SCHEMA_VERSION, 'growth_teacher_evidence_v3')
        self.assertEqual(packet['schema_version'], SCHEMA_VERSION)

    def test_step3_performance_canonical_source(self):
        packet = _packet()
        perf = packet['supporting_facts']['learning']['subjects']['math']['performance']['current']
        self.assertEqual(perf['expected_days']['value'], 10)
        self.assertEqual(perf['studied_days']['value'], 8)
        self.assertEqual(perf['explicit_not_studied_days']['value'], 1)
        self.assertEqual(perf['unknown_days']['value'], 1)
        self.assertEqual(perf['performance_rate']['value'], 0.8)
        self.assertEqual(perf['confirmation_rate']['value'], 0.9)

    def test_daily_points_study_day_proxy_absent(self):
        packet = _packet()
        blob = _blob(packet)
        self.assertNotIn('observed_study_days', blob)
        self.assertNotIn('daily_points.date', blob)
        self.assertNotIn('point_activity_days', packet['supporting_facts']['learning'])

    def test_step4_unique_coverage_canonical(self):
        progress = _packet()['supporting_facts']['learning']['subjects']['math']['progress']
        self.assertEqual(progress['coverage_ratio']['value'], 0.5)
        self.assertEqual(progress['observed_page_count']['value'], 40)
        self.assertEqual(progress['assigned_covered_page_count']['value'], 40)
        self.assertEqual(progress['assigned_denominator']['value'], 80)

    def test_learning_progress_entry_snapshot_absent(self):
        math = _packet()['supporting_facts']['learning']['subjects']['math']
        self.assertNotIn('current_snapshot', math)
        self.assertNotIn('page_advance', math)
        self.assertEqual(math['progress']['latest_observed_end_page']['role'], 'reference_position')

    def test_step5_performance_and_coverage_and_points_peer(self):
        packet = _packet()
        math = packet['supporting_facts']['learning']['subjects']['math']
        self.assertEqual(math['performance_peer']['display_tier'], 'primary')
        self.assertEqual(math['coverage_peer']['display_tier'], 'primary')
        self.assertEqual(packet['supporting_facts']['points']['peer']['display_tier'], 'primary')
        self.assertNotIn('peer', math)

    def test_rank_percentile_keys_absent(self):
        keys = _blob(_packet())
        for forbidden in ('percentile', '"rank"', 'above_average', 'below_average', 'leaderboard'):
            self.assertNotIn(forbidden, keys)

    def test_raw_review_text_absent(self):
        packet = _packet(_bundle(canonical=_canonical(reading={
            'ai_status': 'current',
            'facts': {
                'recent_count': 8,
                'previous_count': 8,
                'sufficiency': 'major',
                'recent_records': [{'record_id': 1, 'date': '2026-12-01', 'book_title': '책'}],
                'previous_records': [],
            },
            'observations': [{
                'dimension': 'expression',
                'observation': '문장 길이가 늘어난 기록이 있습니다.',
                'evidence_refs': [{'record_id': 1, 'date': '2026-12-01', 'book_title': '책'}],
            }],
            'limitations': [],
            'allowed_evidence_refs': [{'record_id': 1, 'date': '2026-12-01', 'book_title': '책'}],
        })))
        self.assertNotIn(SENTINEL_REVIEW, _blob(packet))
        self.assertNotIn('review_text', _blob(packet).lower())
        analysis = packet['supporting_facts']['reading']['analysis']
        self.assertEqual(analysis['ai_status'], 'current')
        self.assertEqual(analysis['observations'][0]['value'], '문장 길이가 늘어난 기록이 있습니다.')

    def test_stale_reading_observation_absent(self):
        packet = _packet(_bundle(canonical=_canonical(reading={
            'ai_status': 'stale',
            'facts': {'recent_count': 8, 'previous_count': 8, 'sufficiency': 'major', 'recent_records': [], 'previous_records': []},
            'observations': [{'dimension': 'expression', 'observation': 'stale-obs', 'evidence_refs': []}],
            'limitations': ['stale-limit'],
            'allowed_evidence_refs': [],
        })))
        analysis = packet['supporting_facts']['reading']['analysis']
        self.assertEqual(analysis['ai_status'], 'stale')
        self.assertEqual(analysis['observations'], [])
        self.assertNotIn('stale-obs', _blob(packet))

    def test_reading_unavailable_keeps_deterministic_facts(self):
        packet = _packet(_bundle(canonical=_canonical(reading={
            'ai_status': 'unavailable',
            'facts': {
                'recent_count': 4,
                'previous_count': 4,
                'sufficiency': 'limited',
                'completed_count': 2,
                'recent_records': [],
                'previous_records': [],
            },
            'observations': [{'observation': 'should-skip'}],
            'limitations': [],
            'allowed_evidence_refs': [],
        })))
        analysis = packet['supporting_facts']['reading']['analysis']
        self.assertEqual(analysis['ai_status'], 'unavailable')
        self.assertEqual(analysis['recent_count']['value'], 4)
        self.assertEqual(analysis['completed_count']['value'], 2)
        self.assertEqual(analysis['observations'], [])

    def test_same_as_of_window_and_no_future_leakage_keys(self):
        packet = _packet()
        self.assertEqual(packet['as_of'], '2026-12-15')
        self.assertEqual(packet['scope']['current_window']['end'], '2026-12-15')
        self.assertLessEqual(packet['scope']['current_window']['end'], packet['as_of'])

    def test_old_planner_estimated_completion_not_canonical_forecast(self):
        plan = _packet()['supporting_facts']['learning']['subjects']['math']['plan']
        self.assertNotIn('remaining_workload', plan)
        self.assertNotIn('workload_kind', plan)
        forecast = _packet()['supporting_facts']['learning']['subjects']['math']['forecast']
        self.assertIn('earliest_date', forecast)
        self.assertIn('latest_date', forecast)

    def test_genuine_zero_keeps_zero_unavailable_stays_unavailable(self):
        zero = _packet(_bundle(
            points=_points(values=(0, 0), cumulative=0),
            point_composition=_composition_payload(
                current=_composition_side(net=0, earn=0, spend=0, praise=0),
                previous=_composition_side(net=0, earn=0, spend=0, praise=0),
            ),
            canonical=_canonical(subjects={'math': _canonical_subject(
                studied=(0, 0),
                not_studied=(10, 10),
                unknown=(0, 0),
                extra=(0, 0),
                performance=(0.0, 0.0),
                coverage_ratio=0.0,
                observed_pages=0,
                assigned_covered=0,
                latest_page=None,
            )}),
        ))
        math = zero['supporting_facts']['learning']['subjects']['math']
        self.assertTrue(math['performance']['current']['studied_days']['available'])
        self.assertEqual(math['performance']['current']['studied_days']['value'], 0)
        self.assertTrue(math['performance']['current']['performance_rate']['available'])
        self.assertEqual(math['performance']['current']['performance_rate']['value'], 0.0)
        self.assertTrue(math['progress']['coverage_ratio']['available'])
        self.assertEqual(math['progress']['coverage_ratio']['value'], 0.0)
        self.assertFalse(math['progress']['latest_observed_end_page']['available'])
        self.assertNotIn('value', math['progress']['latest_observed_end_page'])
        self.assertEqual(zero['supporting_facts']['points']['period']['current']['value'], 0)
        self.assertEqual(
            zero['supporting_facts']['points']['composition']['praise']['points']['current']['value'],
            0,
        )

        missing = _canonical_subject(
            progress_available=False,
            coverage_ratio=None,
            observed_pages=None,
            assigned_covered=None,
            assigned_denom=None,
            latest_page=None,
            forecast_available=False,
            earliest=None,
            latest=None,
            perf_child=None,
            perf_median=None,
            perf_peer_n=0,
            perf_peer_tier='none',
            cov_child=None,
            cov_median=None,
            cov_peer_n=0,
            cov_peer_tier='none',
        )
        missing['performance_current'] = {'available': False}
        missing['performance_previous'] = {'available': False}
        unavailable = _packet(_bundle(
            points=_points(comparable=False, values=(None, None), cumulative=None),
            canonical=_canonical(subjects={'math': missing}),
        ))
        math = unavailable['supporting_facts']['learning']['subjects']['math']
        self.assertFalse(math['performance']['current']['studied_days']['available'])
        self.assertNotIn('value', math['performance']['current']['studied_days'])
        self.assertFalse(math['performance']['current']['performance_rate']['available'])
        self.assertNotIn('value', math['performance']['current']['performance_rate'])
        self.assertFalse(math['progress']['coverage_ratio']['available'])
        self.assertNotIn('value', math['progress']['coverage_ratio'])
        self.assertFalse(math['forecast']['earliest_date']['available'])
        self.assertNotIn('value', math['forecast']['earliest_date'])
        self.assertFalse(math['coverage_peer']['peer_median']['available'])
        self.assertNotIn('value', math['coverage_peer']['peer_median'])
        self.assertFalse(unavailable['supporting_facts']['points']['period']['current']['available'])
        self.assertNotIn('value', unavailable['supporting_facts']['points']['period']['current'])

    def test_selected_insights_are_major_only_and_cite_packet_ids(self):
        packet = _packet()
        known = set(collect_evidence_ids(packet))
        self.assertLessEqual(len(packet['selected_insights']), 4)
        for insight in packet['selected_insights']:
            self.assertEqual(insight['tier'], 'major')
            self.assertNotIn(insight['tier'], ('supporting', 'reference', 'unavailable'))
            for evidence_id in insight['evidence_ids']:
                self.assertIn(evidence_id, known)


class EvidenceSelectorV3Tests(unittest.TestCase):
    def _candidates(self, **canonical_kw):
        packet = _packet(_bundle(canonical=_canonical(**canonical_kw)))
        return select_evidence_candidates(packet['supporting_facts']), packet

    def test_major_max_four_and_zero_valid(self):
        self.assertEqual(SELECTED_INSIGHT_LIMIT, 4)
        empty = _packet(_bundle(canonical=_canonical(subjects={'math': _canonical_subject(
            enough_days=False,
            major_eligible=False,
            delta_pp=0,
            cov_peer_n=0,
            cov_peer_tier='none',
            perf_peer_n=0,
            perf_peer_tier='none',
            cov_median=None,
            perf_median=None,
        )})))
        majors = [item for item in empty['selected_insights'] if item['tier'] == 'major']
        self.assertEqual(majors, empty['selected_insights'])
        self.assertLessEqual(len(empty['selected_insights']), 4)

        many = {}
        for key in ('korean', 'math', 'ssen', 'english', 'science'):
            many[key] = _canonical_subject(key=key, name=key, delta_pp=12.0, cov_child=0.8, cov_median=0.5)
        packed = _packet(_bundle(canonical=_canonical(subjects=many)))
        self.assertLessEqual(len(packed['selected_insights']), 4)
        self.assertTrue(all(item['tier'] == 'major' for item in packed['selected_insights']))

    def test_expected_days_insufficient_no_period_change_major(self):
        candidates, _packet_out = self._candidates(subjects={'math': _canonical_subject(
            expected=(7, 7),
            enough_days=False,
            major_eligible=False,
            delta_pp=20.0,
            cov_peer_n=0,
            cov_peer_tier='none',
            cov_median=None,
        )})
        period = next(item for item in candidates if item.id.endswith('period_change.performance'))
        self.assertEqual(period.tier, TIER_UNAVAILABLE)
        self.assertFalse(any(
            item.tier == TIER_MAJOR_LABEL and 'period_change' in item.id
            for item in candidates
        ))

    def test_confirmation_bands(self):
        forbidden, _ = self._candidates(subjects={'math': _canonical_subject(
            band='forbidden', enough_days=True, major_eligible=False, delta_pp=20.0,
            cov_peer_n=0, cov_peer_tier='none', cov_median=None,
        )})
        self.assertEqual(next(item for item in forbidden if 'period_change' in item.id).tier, TIER_UNAVAILABLE)
        limited, _ = self._candidates(subjects={'math': _canonical_subject(
            band='limited', enough_days=True, major_eligible=False, delta_pp=20.0,
            cov_peer_n=0, cov_peer_tier='none', cov_median=None,
        )})
        self.assertEqual(next(item for item in limited if 'period_change' in item.id).tier, TIER_SUPPORTING)
        small, _ = self._candidates(subjects={'math': _canonical_subject(
            band='primary', enough_days=True, major_eligible=False, delta_pp=9.0,
            cov_peer_n=0, cov_peer_tier='none', cov_median=None,
        )})
        self.assertEqual(next(item for item in small if 'period_change' in item.id).tier, TIER_REFERENCE)

    def test_peer_n_and_coverage_difference_tiers(self):
        n2, packet = self._candidates(subjects={'math': _canonical_subject(
            major_eligible=False, delta_pp=0,
            cov_peer_n=2, cov_peer_tier='reference_only', cov_child=0.8, cov_median=0.5,
            perf_peer_n=2, perf_peer_tier='reference_only',
        )})
        coverage = next(item for item in n2 if item.metric_key == 'coverage_ratio')
        self.assertEqual(coverage.tier, TIER_REFERENCE)
        self.assertEqual(packet['supporting_facts']['learning']['subjects']['math']['coverage_peer']['display_tier'], 'reference_only')

        n3, _ = self._candidates(subjects={'math': _canonical_subject(
            major_eligible=False, delta_pp=0,
            cov_peer_n=3, cov_peer_tier='primary', cov_child=0.8, cov_median=0.79,
        )})
        coverage = next(item for item in n3 if item.metric_key == 'coverage_ratio')
        self.assertEqual(coverage.tier, TIER_REFERENCE)

        exact_ref, _ = self._candidates(subjects={'math': _canonical_subject(
            major_eligible=False, delta_pp=0,
            cov_peer_n=3, cov_peer_tier='primary', cov_child=0.54, cov_median=0.50,
        )})
        self.assertEqual(
            next(item for item in exact_ref if item.metric_key == 'coverage_ratio').tier,
            TIER_REFERENCE,
        )

        exact_five, _ = self._candidates(subjects={'math': _canonical_subject(
            major_eligible=False, delta_pp=0,
            cov_peer_n=3, cov_peer_tier='primary', cov_child=0.55, cov_median=0.50,
        )})
        self.assertEqual(
            next(item for item in exact_five if item.metric_key == 'coverage_ratio').tier,
            TIER_SUPPORTING,
        )

        mid, _ = self._candidates(subjects={'math': _canonical_subject(
            major_eligible=False, delta_pp=0,
            cov_peer_n=3, cov_peer_tier='primary', cov_child=0.56, cov_median=0.50,
        )})
        self.assertEqual(next(item for item in mid if item.metric_key == 'coverage_ratio').tier, TIER_SUPPORTING)

        exact_ten, _ = self._candidates(subjects={'math': _canonical_subject(
            major_eligible=False, delta_pp=0,
            cov_peer_n=3, cov_peer_tier='primary', cov_child=0.60, cov_median=0.50,
        )})
        self.assertEqual(
            next(item for item in exact_ten if item.metric_key == 'coverage_ratio').tier,
            TIER_MAJOR_LABEL,
        )

        major, _ = self._candidates(subjects={'math': _canonical_subject(
            major_eligible=False, delta_pp=0,
            cov_peer_n=3, cov_peer_tier='primary', cov_child=0.70, cov_median=0.50,
        )})
        self.assertEqual(next(item for item in major if item.metric_key == 'coverage_ratio').tier, TIER_MAJOR_LABEL)

    def test_points_delta_does_not_promote_major(self):
        packet = _packet(_bundle(points=_points(values=(5000, 0)), canonical=_canonical(
            subjects={'math': _canonical_subject(major_eligible=False, delta_pp=0, cov_peer_n=0, cov_peer_tier='none', cov_median=None, perf_peer_n=0, perf_peer_tier='none', perf_median=None)},
            points_peer={'available': True, 'display_tier': 'primary', 'peer_sample_count': 5, 'child_value': 5000, 'peer_median': 10, 'difference': 4990, 'reason': 'ok'},
        )))
        majors = select_major_insights(packet['supporting_facts'])
        self.assertFalse(any(item.category == 'points' for item in majors))
        self.assertFalse(any(item.id == 'points.peer.period_points' and item.tier == TIER_MAJOR_LABEL for item in select_evidence_candidates(packet['supporting_facts'])))

    def test_reading_major_limited_insufficient(self):
        def reading(status, recent, previous, sufficiency, observations=True):
            return {
                'ai_status': status,
                'facts': {
                    'recent_count': recent,
                    'previous_count': previous,
                    'sufficiency': sufficiency,
                    'recent_records': [],
                    'previous_records': [],
                },
                'observations': [{'dimension': 'expression', 'observation': 'obs', 'evidence_refs': []}] if observations else [],
                'limitations': [],
                'allowed_evidence_refs': [],
            }
        major, _ = self._candidates(reading=reading('current', 8, 8, 'major'))
        self.assertEqual(next(item for item in major if item.category == 'reading').tier, TIER_MAJOR_LABEL)
        limited, _ = self._candidates(reading=reading('current', 4, 4, 'limited'))
        self.assertEqual(next(item for item in limited if item.category == 'reading').tier, TIER_SUPPORTING)
        low, _ = self._candidates(reading=reading('current', 2, 8, 'no_change_conclusion'))
        self.assertEqual(next(item for item in low if item.category == 'reading').tier, TIER_UNAVAILABLE)
        stale, _ = self._candidates(reading=reading('stale', 8, 8, 'major'))
        self.assertEqual(next(item for item in stale if item.category == 'reading').tier, TIER_UNAVAILABLE)

    def test_no_statistical_outlier_removal(self):
        packet = _packet(_bundle(canonical=_canonical(subjects={'math': _canonical_subject(
            perf_child=0.99, perf_median=0.10, perf_peer_n=3, perf_peer_tier='primary',
            major_eligible=False, delta_pp=0,
        )})))
        peer = packet['supporting_facts']['learning']['subjects']['math']['performance_peer']
        self.assertEqual(peer['child_value']['value'], 0.99)
        self.assertEqual(peer['peer_median']['value'], 0.10)


class PacketHashV3Tests(unittest.TestCase):
    def test_learning_peer_reading_and_version_change_hash(self):
        base = _packet()
        learning = _packet(_bundle(canonical=_canonical(subjects={'math': _canonical_subject(studied=(9, 7))})))
        self.assertNotEqual(packet_hash(base), packet_hash(learning))
        peer = _packet(_bundle(canonical=_canonical(subjects={'math': _canonical_subject(perf_median=0.55)})))
        self.assertNotEqual(packet_hash(base), packet_hash(peer))
        reading = _packet(_bundle(canonical=_canonical(reading={
            'ai_status': 'current',
            'facts': {'recent_count': 8, 'previous_count': 8, 'sufficiency': 'major', 'recent_records': [], 'previous_records': []},
            'observations': [{'dimension': 'content', 'observation': 'changed-obs', 'evidence_refs': []}],
            'limitations': [],
            'allowed_evidence_refs': [],
        })))
        self.assertNotEqual(packet_hash(base), packet_hash(reading))
        other = dict(base)
        other['schema_version'] = 'growth_teacher_evidence_v2'
        self.assertNotEqual(packet_hash(base), packet_hash(other))

    def test_get_loader_does_not_generate(self):
        import inspect
        from features.growth.ai.runtime import load_teacher_ai_view
        source = inspect.getsource(load_teacher_ai_view)
        self.assertNotIn('generate_teacher_growth_interpretation', source)


class ReadingAdapterImportTests(unittest.TestCase):
    def test_adapter_rejects_review_text_in_payload(self):
        from features.growth import reading_evidence as module
        with self.assertRaises(RuntimeError):
            module._assert_no_raw({'review_text': 'secret'})
        with self.assertRaises(RuntimeError):
            module._assert_no_raw({'raw_texts': ['a']})
