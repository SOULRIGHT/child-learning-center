"""Step 7 Overall Growth AI v3 Playwright smoke. Live AI is not called."""
from __future__ import annotations

from playwright.sync_api import Page

from smoke_step3 import StepFailure, _goto


def run_authenticated_steps(page: Page, *, base_url: str, state: dict) -> list[tuple[str, str]]:
    passed: list[tuple[str, str]] = []
    child_id = int(state['child_id'])

    def mark(name: str) -> None:
        passed.append((name, 'PASS'))

    _goto(page, f'{base_url}/children/{child_id}/growth', 'growth_get_canonical')
    if '/login' in (page.url or ''):
        raise StepFailure('growth_get_canonical', f'redirected to login: {page.url}')
    if page.locator('#growth-ai-card').count() != 1:
        raise StepFailure('growth_get_canonical', 'Overall AI card missing')
    if page.locator('[data-growth-learning]').count() != 1:
        raise StepFailure('growth_get_canonical', 'deterministic learning section missing')
    mark('growth_get_canonical')

    ai_state = page.locator('#growth-ai-card').get_attribute('data-ai-state')
    if ai_state != 'stale':
        raise StepFailure('growth_stale_no_regen', f'expected stale, got {ai_state!r}')
    if page.locator('[data-ai-panel="stale"]').count() != 1:
        raise StepFailure('growth_stale_no_regen', 'stale panel missing')
    mark('growth_stale_no_regen')

    reading_ai = page.locator('[data-testid="growth-reading-ai"]')
    if reading_ai.count() != 1:
        raise StepFailure('reading_unavailable_overall_ok', 'reading AI block missing')
    reading_state = reading_ai.get_attribute('data-ai-state') or ''
    if reading_state in ('',):
        raise StepFailure('reading_unavailable_overall_ok', 'reading AI state missing')
    mark('reading_unavailable_overall_ok')

    generate = page.locator('[data-ai-panel="stale"] [data-ai-action="generate"]')
    if generate.count() != 1:
        raise StepFailure('growth_fake_generate', 'stale generate button missing')
    generate.click()
    try:
        page.locator('#growth-ai-card[data-ai-state="success"]').wait_for(timeout=15000)
    except Exception as exc:
        raise StepFailure(
            'growth_fake_generate',
            f'fake generate did not reach success: {page.locator("#growth-ai-card").get_attribute("data-ai-state")!r} {exc}',
        ) from exc
    summary = page.locator('[data-ai-role="summary"]').inner_text()
    if not summary.strip():
        raise StepFailure('growth_fake_generate', 'generated interpretation text missing')
    mark('growth_fake_generate')
    return passed
