"""Growth AI result UI contracts. 네트워크 호출 없음."""
from __future__ import annotations

import unittest

from tests.helpers import PROJECT_ROOT


class GrowthAiResultUiTests(unittest.TestCase):
    def test_result_hierarchy_and_js_fillers(self):
        html = (PROJECT_ROOT / 'templates' / 'growth' / '_ai_card.html').read_text(encoding='utf-8')
        css = (PROJECT_ROOT / 'templates' / 'growth' / 'report.html').read_text(encoding='utf-8')
        js = (PROJECT_ROOT / 'static' / 'js' / 'growth-ai.js').read_text(encoding='utf-8')
        copy_src = (PROJECT_ROOT / 'features' / 'growth' / 'ai' / 'copy.py').read_text(encoding='utf-8')
        self.assertIn('growth-ai-priority', html)
        self.assertIn('data-ai-role="priority-card"', html)
        self.assertIn('왜 중요하게 보나요?', html)
        self.assertIn('growth-ai-action-card', html)
        self.assertIn('growth-ai-check', html)
        self.assertIn('data-ai-role="next-check-list"', html)
        self.assertIn('data-ai-role="observations-fold"', html)
        self.assertNotIn('<details class="growth-ai-obs-fold" open', html)
        self.assertNotIn('type="checkbox"', html)
        self.assertIn('max-width: 920px', css)
        self.assertIn('fillActions', js)
        self.assertIn('fillChecklist', js)
        self.assertIn('setObservationsSummary', js)
        self.assertIn('INTERPRETATION_TITLE = \'왜 중요하게 보나요?\'', copy_src)
        self.assertIn('OBS_TITLE = \'세부 관찰\'', copy_src)
        self.assertIn('growth_teacher_prompt_v4', (PROJECT_ROOT / 'features' / 'growth' / 'ai' / 'prompt.py').read_text(encoding='utf-8'))
        self.assertIn('최대 2문장', (PROJECT_ROOT / 'features' / 'growth' / 'ai' / 'prompt.py').read_text(encoding='utf-8'))
