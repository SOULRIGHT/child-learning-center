"""Step 6 reading input + Growth reading panel Playwright smoke. Live AI is not called."""
from __future__ import annotations

from playwright.sync_api import Page

from smoke_step3 import StepFailure, _goto


SENTINEL_REVIEW = 'QA-STEP6-REVIEW-UNIQUE-PHRASE'
BOOK_TITLE = 'QA Step6 Book'


def run_authenticated_steps(page: Page, *, base_url: str, state: dict) -> list[tuple[str, str]]:
    passed: list[tuple[str, str]] = []
    child_id = int(state['child_id'])
    slug = str(state['viewer_slug'])

    def mark(name: str) -> None:
        passed.append((name, 'PASS'))

    confirm_url = f'{base_url}/viewer/report/{slug}/reading/confirm'
    _goto(page, confirm_url, 'child_reading_save')
    if '/login' in (page.url or ''):
        raise StepFailure('child_reading_save', f'redirected to login: {page.url}')
    yes = page.locator('button[name="confirm"][value="yes"]')
    if yes.count() != 1:
        raise StepFailure('child_reading_save', 'confirm yes button missing')
    with page.expect_navigation(wait_until='domcontentloaded'):
        yes.click()
    title = page.locator('#title')
    review = page.locator('#review_text_new')
    if title.count() != 1 or review.count() != 1:
        raise StepFailure('child_reading_save', 'reading start form missing')
    title.fill(BOOK_TITLE)
    review.fill(SENTINEL_REVIEW)
    with page.expect_navigation(wait_until='domcontentloaded'):
        page.locator('#start-book-form button[type="submit"]').click()
    history_url = f'{base_url}/viewer/report/{slug}/reading/history'
    _goto(page, history_url, 'child_reading_save')
    body = page.inner_text('body')
    if BOOK_TITLE not in body:
        raise StepFailure('child_reading_save', 'saved book title missing from viewer history')
    if SENTINEL_REVIEW not in body:
        raise StepFailure('child_reading_save', 'saved review missing from viewer history')
    mark('child_reading_save')

    teacher_history = f'{base_url}/children/{child_id}/reading/history'
    _goto(page, teacher_history, 'teacher_reading_history')
    if '/login' in (page.url or ''):
        raise StepFailure('teacher_reading_history', f'redirected to login: {page.url}')
    teacher_body = page.inner_text('body')
    if BOOK_TITLE not in teacher_body:
        raise StepFailure('teacher_reading_history', 'saved book title missing from teacher history')
    if SENTINEL_REVIEW not in teacher_body:
        raise StepFailure('teacher_reading_history', 'saved review missing from teacher history')
    mark('teacher_reading_history')

    _goto(page, f'{base_url}/children/{child_id}/growth', 'growth_reading_panel')
    if '/login' in (page.url or ''):
        raise StepFailure('growth_reading_panel', f'redirected to login: {page.url}')
    analysis = page.locator('[data-testid="growth-reading-analysis"]')
    recent = page.locator('[data-testid="growth-reading-recent"]')
    ai_block = page.locator('[data-testid="growth-reading-ai"]')
    if analysis.count() != 1:
        raise StepFailure('growth_reading_panel', 'reading analysis block missing')
    if recent.count() != 1:
        raise StepFailure('growth_reading_panel', 'recent reading metadata missing')
    if ai_block.count() != 1:
        raise StepFailure('growth_reading_panel', 'reading AI block missing')
    if page.locator('[data-growth-learning]').count() != 1:
        raise StepFailure('growth_reading_panel', 'learning section missing after reading panel')
    if page.locator('[data-testid="canonical-peer-points"]').count() != 1:
        raise StepFailure('growth_reading_panel', 'peer points section missing after reading panel')
    if not ai_block.get_attribute('data-ai-state'):
        raise StepFailure('growth_reading_panel', 'reading AI state missing')
    growth_body = page.inner_text('body')
    if SENTINEL_REVIEW in growth_body:
        raise StepFailure('growth_reading_panel', 'raw review text dumped on Growth page')
    if BOOK_TITLE not in recent.inner_text():
        raise StepFailure('growth_reading_panel', 'recent metadata missing book title')
    mark('growth_reading_panel')
    return passed
