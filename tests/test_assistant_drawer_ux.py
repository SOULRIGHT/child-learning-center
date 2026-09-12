"""Teacher assistant drawer UX polish. live API 호출 없음."""
from __future__ import annotations

import re
import unittest

from tests.helpers import PROJECT_ROOT


def ordinal_user_display(value):
    raw = str(value or '').strip()
    match = re.fullmatch(r'(\d+)\s*번째', raw)
    return f'{match.group(1)}번째 아동' if match else raw


def should_submit_on_enter(
    key,
    *,
    shift=False,
    is_composing=False,
    key_code=None,
    composing=False,
    in_flight=False,
):
    if key != 'Enter':
        return False
    if shift:
        return False
    if is_composing or composing or key_code == 229:
        return False
    if in_flight:
        return False
    return True


def composer_uses_scroll(scroll_height, max_height):
    return scroll_height > max_height


class DrawerUxHelperTests(unittest.TestCase):
    def test_ordinal_display_is_friendlier_than_payload_value(self):
        self.assertEqual(ordinal_user_display('7번째'), '7번째 아동')
        self.assertEqual(ordinal_user_display('2번째'), '2번째 아동')
        self.assertEqual(ordinal_user_display(' 7번째 '), '7번째 아동')
        self.assertEqual(ordinal_user_display('2번'), '2번')
        self.assertEqual(ordinal_user_display('두 번째'), '두 번째')
        self.assertEqual(ordinal_user_display('시드-독서감소'), '시드-독서감소')

    def test_enter_sends_once_and_shift_enter_does_not(self):
        self.assertTrue(should_submit_on_enter('Enter'))
        self.assertFalse(should_submit_on_enter('Enter', shift=True))
        self.assertFalse(should_submit_on_enter('Enter', in_flight=True))
        self.assertFalse(should_submit_on_enter('a'))

    def test_ime_composing_enter_does_not_submit(self):
        self.assertFalse(should_submit_on_enter('Enter', is_composing=True))
        self.assertFalse(should_submit_on_enter('Enter', composing=True))
        self.assertFalse(should_submit_on_enter('Enter', key_code=229))

    def test_scroll_only_after_max_height(self):
        self.assertFalse(composer_uses_scroll(80, 80))
        self.assertFalse(composer_uses_scroll(79, 80))
        self.assertTrue(composer_uses_scroll(81, 80))


class DrawerUxSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = (PROJECT_ROOT / 'static' / 'js' / 'assistant.js').read_text(encoding='utf-8')
        cls.css = (PROJECT_ROOT / 'static' / 'css' / 'assistant.css').read_text(encoding='utf-8')

    def test_loading_stays_ephemeral_and_larger(self):
        self.assertIn('const MIN_VISIBLE_MS = 2000', self.js)
        self.assertIn('is-loading', self.js)
        self.assertIn("dots.textContent = '...'", self.js)
        self.assertNotIn("kind: 'loading'", self.js)
        self.assertNotIn("content: '...'", self.js)
        self.assertIn('.assistant-bubble.is-loading', self.css)
        self.assertIn('font-size: 1.38rem', self.css)
        self.assertNotIn('font-size: 1.7rem', self.css)
        self.assertIn('display: inline-flex', self.css)
        self.assertIn('align-items: center', self.css)
        self.assertIn('justify-content: center', self.css)
        self.assertIn('line-height: 1', self.css)
        self.assertIn('max-width: 4.75rem', self.css)
        self.assertIn('padding: 0.7rem 0.8rem', self.css)

    def test_drawer_header_title_is_muon(self):
        html = (PROJECT_ROOT / 'templates' / 'assistant' / '_drawer.html').read_text(encoding='utf-8')
        self.assertIn('id="teacherAssistantTitle">{{ assistant_display_name }}</h2>', html)
        self.assertNotIn('>조교</h2>', html)
        self.assertNotIn('조교', html)

    def test_question_count_is_neutral_pill_not_button(self):
        html = (PROJECT_ROOT / 'templates' / 'assistant' / '_drawer.html').read_text(encoding='utf-8')
        self.assertIn('질문 0 / 10', html)
        self.assertNotIn('대화 0 / 10', html)
        self.assertIn("textContent = '질문 ' + count + ' / ' + limit", self.js)
        self.assertNotIn("textContent = '대화 ' + count + ' / ' + limit", self.js)
        count_css = self.css.split('.assistant-question-count')[1].split('.assistant-header-actions')[0]
        self.assertIn('background: #f3f4f6', count_css)
        self.assertIn('border: 1px solid #d1d5db', count_css)
        self.assertIn('pointer-events: none', count_css)
        self.assertIn('padding: 0.12rem 0.45rem', count_css)
        self.assertNotIn('#2563eb', count_css)
        self.assertNotIn('#3b82f6', count_css)

    def test_loading_uses_flex_center_and_matching_bubble_padding(self):
        loading = self.css.split('.assistant-bubble.is-loading')[1].split('.assistant-loading-dots')[0]
        self.assertIn('display: inline-flex', loading)
        self.assertIn('align-items: center', loading)
        self.assertIn('justify-content: center', loading)
        self.assertIn('line-height: 1', loading)
        self.assertIn('padding: 0.7rem 0.8rem', loading)
        dots = self.css.split('.assistant-loading-dots')[1].split('.assistant-fact-p')[0]
        self.assertIn('display: inline-flex', dots)
        self.assertIn('align-items: center', dots)
        self.assertIn('justify-content: center', dots)

    def test_enter_shift_enter_and_ime_guards(self):
        self.assertIn('function shouldSubmitOnEnter', self.js)
        self.assertIn('event.key !== \'Enter\'', self.js)
        self.assertIn('event.shiftKey', self.js)
        self.assertIn('event.isComposing', self.js)
        self.assertIn('event.keyCode === 229', self.js)
        self.assertIn("addEventListener('compositionstart'", self.js)
        self.assertIn("addEventListener('compositionend'", self.js)
        self.assertIn('if (!text) return', self.js)
        self.assertIn('if (inFlight) return', self.js)

    def test_textarea_auto_grow_hides_scrollbar_until_max(self):
        self.assertIn('const COMPOSER_MAX_ROWS = 4', self.js)
        self.assertIn('function resizeComposerInput', self.js)
        self.assertIn("overflowY = 'hidden'", self.js)
        self.assertIn("overflowY = 'auto'", self.js)
        self.assertIn('overflow-y: hidden', self.css)
        self.assertIn('scrollbar-width: thin', self.css)
        self.assertIn('align-items: flex-end', self.css)

    def test_ordinal_display_and_reply_value_are_split(self):
        self.assertIn('function ordinalUserDisplay', self.js)
        self.assertIn("match[1] + '번째 아동'", self.js)
        self.assertIn('data-assistant-display', self.js)
        self.assertIn('data-assistant-reply', self.js)
        self.assertIn('sendChat(text, \'confirm\', display)', self.js)
        self.assertIn('content: sendText', self.js)
        self.assertIn('content: shown', self.js)
        self.assertIn("f'{index}번째'", (
            PROJECT_ROOT / 'features' / 'assistant' / 'conversation.py'
        ).read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
