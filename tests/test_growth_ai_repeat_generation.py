"""Repeated Growth AI generation loading/controller regression.

JS 타이머·AbortController·in_progress freeze를 Python으로 재현한다.
실제 OpenAI/AWS 호출 없음.
"""
from __future__ import annotations

import re
import unittest

from tests.helpers import PROJECT_ROOT


JS_PATH = PROJECT_ROOT / 'static' / 'js' / 'growth-ai.js'
CARD_PATH = PROJECT_ROOT / 'templates' / 'growth' / '_ai_card.html'
COPY_PATH = PROJECT_ROOT / 'features' / 'growth' / 'ai' / 'copy.py'


def _success(generation_id=1):
    return {
        'ok': True,
        'started': True,
        'state': 'success',
        'generation_id': generation_id,
        'interpretation': {
            'priority_insight': '첫 해석' if generation_id == 1 else '두 번째 해석',
            'summary': '요약',
        },
    }


class GrowthAiLoadingMachine:
    STAGE_MS = 2000
    MIN_HOLD_MS = 8000
    STAGE_COUNT = 4
    DEADLINE_MS = 21000

    def __init__(self):
        self.now = 0
        self.timers = []
        self.focus = 0
        self.state = 'idle'
        self.waiting = False
        self.disabled = False
        self.in_flight = False
        self.request_seq = 0
        self.controller_generation = 0
        self.aborted_controllers = []
        self.active_controller = None
        self.presentation = None
        self.rendered = None
        self.waiting_title = ''
        self.waiting_hint = ''
        self.stage_history = []

    def _clear_timers(self):
        self.timers = []

    def _apply_focus(self, index):
        bounded = max(0, min(self.STAGE_COUNT - 1, index))
        self.focus = bounded
        self.stage_history.append((self.now, bounded + 1))

    def _set_waiting_copy(self, title, hint):
        self.waiting_title = title
        self.waiting_hint = hint

    def start_presentation(self):
        self._clear_timers()
        self.waiting = False
        self._set_waiting_copy(
            '성장 해석을 꼼꼼하게 마무리하고 있어요...',
            '거의 다 준비됐어요. 잠시만 기다려주세요.',
        )
        self.presentation = {'hold_done': False, 'payload': None}
        self._apply_focus(0)
        for step in range(1, self.STAGE_COUNT):
            due = self.now + self.STAGE_MS * step
            self.timers.append((due, self._make_focus_timer(step)))
        self.timers.append((self.now + self.MIN_HOLD_MS, self._hold_done))
        self.timers.sort(key=lambda item: item[0])

    def _make_focus_timer(self, step):
        def _fire():
            if not self.presentation:
                return
            self._apply_focus(step)
        return _fire

    def _hold_done(self):
        if not self.presentation:
            return
        self.presentation['hold_done'] = True
        if not self.presentation['payload']:
            self._apply_focus(self.STAGE_COUNT - 1)
            self.waiting = True
            return
        self.reveal(self.presentation['payload'])

    def is_preflight(self, payload):
        if not payload:
            return False
        if payload.get('started') is True:
            return False
        state = payload.get('state')
        return state in ('disabled', 'quota', 'in_progress', 'cooldown', 'failure_limit') or (
            state == 'success' and payload.get('cached') is True
        )

    def reveal(self, payload):
        self.in_flight = False
        self._clear_timers()
        self.presentation = None
        self.waiting = False
        self.disabled = False
        if payload and payload.get('ok') and payload.get('state') == 'success':
            self.state = 'success'
            self.rendered = payload
            return
        state = (payload or {}).get('state') or 'error'
        if state == 'in_progress':
            message = (payload or {}).get('message') or ''
            parts = message.split('\n')
            self._set_waiting_copy(
                parts[0] or '다른 AI 성장 해석을 준비하고 있어요.',
                parts[1] if len(parts) > 1 else '완료된 뒤 다시 시도해주세요.',
            )
            self.state = 'loading'
            self._apply_focus(self.STAGE_COUNT - 1)
            self.waiting = True
            return
        if state in ('quota', 'stale', 'disabled'):
            self.state = state
            return
        self.state = 'timeout' if state == 'timeout' else 'error'
        self.rendered = payload

    def settle(self, payload, seq):
        if seq != self.request_seq:
            return
        if self.is_preflight(payload):
            self.reveal(payload)
            return
        if not self.presentation:
            self.reveal(payload)
            return
        self.presentation['payload'] = payload
        if self.presentation['hold_done']:
            self.reveal(payload)

    def generate(self):
        if self.in_flight:
            return None
        self.in_flight = True
        self.request_seq += 1
        seq = self.request_seq
        if self.active_controller is not None:
            self.aborted_controllers.append(self.active_controller)
        self.disabled = True
        self.state = 'loading'
        self.rendered = None
        self.stage_history = []
        self.start_presentation()
        self.controller_generation += 1
        self.active_controller = self.controller_generation
        return seq

    def tick(self, ms):
        target = self.now + ms
        while True:
            due_now = [item for item in self.timers if item[0] <= target]
            if not due_now:
                break
            due_now.sort(key=lambda item: item[0])
            due, fn = due_now[0]
            self.timers.remove((due, fn))
            self.now = due
            fn()
        self.now = target

    def stage_sequence(self):
        seen = []
        for _, stage in self.stage_history:
            if not seen or seen[-1] != stage:
                seen.append(stage)
        return seen


class GrowthAiRepeatGenerationTests(unittest.TestCase):
    def test_js_and_copy_contracts(self):
        js = JS_PATH.read_text(encoding='utf-8')
        card = CARD_PATH.read_text(encoding='utf-8')
        copy_src = COPY_PATH.read_text(encoding='utf-8')
        self.assertIn('const STAGE_MS = 2000', js)
        self.assertIn('const MIN_HOLD_MS = 8000', js)
        self.assertIn('21000', js)
        self.assertIn('let requestSeq = 0', js)
        self.assertIn('let inFlight = false', js)
        self.assertIn('if (inFlight) return', js)
        self.assertIn('activeController.abort()', js)
        self.assertIn('if (seq !== requestSeq) return', js)
        self.assertIn('STAGE_MS * step', js)
        self.assertNotIn('setTimeout(function (step)', js)
        self.assertIn('applyFocus(STAGE_COUNT - 1)', js)
        in_progress_blocks = re.findall(
            r"if \(state === 'in_progress'\) \{.*?return;\n                \}",
            js,
            flags=re.S,
        )
        self.assertEqual(len(in_progress_blocks), 1)
        self.assertIn('applyFocus(STAGE_COUNT - 1)', in_progress_blocks[0])
        self.assertNotIn('applyFocus(0)', in_progress_blocks[0])
        self.assertNotIn('|| payload.started === false', js)
        self.assertIn('성장 해석을 꼼꼼하게 마무리하고 있어요...', card)
        self.assertIn('거의 다 준비됐어요. 잠시만 기다려주세요.', card)
        self.assertIn('보통 5~10초 정도 걸려요.', card)
        self.assertIn('MSG_LOADING_WAITING = \'성장 해석을 꼼꼼하게 마무리하고 있어요...\'', copy_src)
        self.assertIn('거의 다 준비됐어요. 잠시만 기다려주세요.', copy_src)

    def test_first_success_then_second_generation_starts_clean(self):
        machine = GrowthAiLoadingMachine()
        seq1 = machine.generate()
        self.assertEqual(machine.focus, 0)
        self.assertEqual(machine.state, 'loading')
        machine.tick(1500)
        self.assertEqual(machine.focus, 0)
        machine.settle(_success(1), seq1)
        self.assertIsNone(machine.rendered)
        machine.tick(500)
        self.assertEqual(machine.stage_sequence(), [1, 2])
        machine.tick(2000)
        self.assertEqual(machine.stage_sequence(), [1, 2, 3])
        machine.tick(2000)
        self.assertEqual(machine.stage_sequence(), [1, 2, 3, 4])
        machine.tick(2000)
        self.assertEqual(machine.state, 'success')
        self.assertEqual(machine.rendered['generation_id'], 1)
        self.assertFalse(machine.in_flight)
        self.assertFalse(machine.disabled)

        seq2 = machine.generate()
        self.assertNotEqual(seq2, seq1)
        self.assertEqual(machine.state, 'loading')
        self.assertEqual(machine.focus, 0)
        self.assertIsNone(machine.rendered)
        self.assertEqual(machine.timers.__len__() > 0, True)
        machine.tick(2000)
        self.assertEqual(machine.focus, 1)
        machine.tick(2000)
        self.assertEqual(machine.focus, 2)
        machine.tick(2000)
        self.assertEqual(machine.focus, 3)
        machine.settle(_success(2), seq2)
        self.assertEqual(machine.state, 'loading')
        machine.tick(2000)
        self.assertEqual(machine.state, 'success')
        self.assertEqual(machine.rendered['generation_id'], 2)
        self.assertEqual(machine.stage_sequence(), [1, 2, 3, 4])

    def test_in_flight_second_click_does_not_reset_first_timers(self):
        machine = GrowthAiLoadingMachine()
        seq1 = machine.generate()
        first_controller = machine.active_controller
        ignored = machine.generate()
        self.assertIsNone(ignored)
        self.assertEqual(machine.request_seq, 1)
        self.assertEqual(machine.active_controller, first_controller)
        self.assertEqual(machine.aborted_controllers, [])
        machine.tick(2000)
        self.assertEqual(machine.focus, 1)
        machine.settle(_success(1), seq1)
        machine.tick(6000)
        self.assertEqual(machine.state, 'success')
        self.assertEqual(machine.rendered['generation_id'], 1)

    def test_stale_in_progress_does_not_clobber_success(self):
        machine = GrowthAiLoadingMachine()
        seq1 = machine.generate()
        machine.tick(8000)
        machine.settle(_success(1), seq1)
        self.assertEqual(machine.state, 'success')
        seq2 = machine.generate()
        machine.settle({'ok': False, 'started': False, 'state': 'in_progress'}, seq1)
        self.assertEqual(machine.state, 'loading')
        self.assertEqual(machine.focus, 0)
        self.assertIsNone(machine.rendered)
        machine.tick(2000)
        self.assertEqual(machine.focus, 1)
        machine.settle(_success(2), seq2)
        machine.tick(6000)
        self.assertEqual(machine.state, 'success')
        self.assertEqual(machine.rendered['generation_id'], 2)

    def test_in_progress_does_not_freeze_on_stage_one(self):
        machine = GrowthAiLoadingMachine()
        seq = machine.generate()
        self.assertEqual(machine.focus, 0)
        machine.settle({'ok': False, 'started': False, 'state': 'in_progress', 'message': '다른 AI 성장 해석을 준비하고 있어요.\n완료된 뒤 다시 시도해주세요.'}, seq)
        self.assertEqual(machine.state, 'loading')
        self.assertEqual(machine.focus, 3)
        self.assertTrue(machine.waiting)
        self.assertFalse(machine.in_flight)
        self.assertIn('다른 AI 성장 해석', machine.waiting_title)
        self.assertEqual(machine.timers, [])

    def test_preflight_cache_skips_eight_second_hold(self):
        machine = GrowthAiLoadingMachine()
        seq = machine.generate()
        machine.settle({
            'ok': True,
            'started': False,
            'state': 'success',
            'cached': True,
            'generation_id': 9,
            'interpretation': {'priority_insight': '캐시'},
        }, seq)
        self.assertEqual(machine.now, 0)
        self.assertEqual(machine.state, 'success')
        self.assertEqual(machine.rendered['generation_id'], 9)

    def test_early_started_response_waits_for_stage_four(self):
        machine = GrowthAiLoadingMachine()
        seq = machine.generate()
        machine.tick(1000)
        machine.settle(_success(4), seq)
        self.assertEqual(machine.state, 'loading')
        self.assertIsNone(machine.rendered)
        machine.tick(7000)
        self.assertEqual(machine.state, 'success')
        self.assertEqual(machine.stage_sequence(), [1, 2, 3, 4])

    def test_js_in_progress_block_has_single_listener(self):
        js = JS_PATH.read_text(encoding='utf-8')
        self.assertEqual(len(re.findall(r"addEventListener\('DOMContentLoaded'", js)), 1)
        self.assertEqual(len(re.findall(r"card\.addEventListener\('click'", js)), 1)
        self.assertEqual(js.count("action === 'generate'"), 1)


if __name__ == '__main__':
    unittest.main()
