"""Step 5 teacher-only Playwright smoke. Domain math is not re-checked here."""
from __future__ import annotations

from playwright.sync_api import Page

from smoke_step3 import StepFailure, _goto


BANNED_PEER_COPY = ('순위', '상위권', '백분위', '우수', '열등', '평균 이상', '뒤처짐', '몇 등')


def run_authenticated_steps(page: Page, *, base_url: str, state: dict) -> list[tuple[str, str]]:
    passed: list[tuple[str, str]] = []
    child_id = int(state['peer_ready_child_id'])
    lonely_id = int(state['lonely_child_id'])
    subject_key = str(state.get('subject_key') or 'math')

    def mark(name: str) -> None:
        passed.append((name, 'PASS'))

    _goto(page, f'{base_url}/children/{child_id}/growth', 'canonical_peer_eligible')
    if '/login' in (page.url or ''):
        raise StepFailure('canonical_peer_eligible', f'redirected to login: {page.url}')
    if page.locator('[data-growth-learning]').count() != 1:
        raise StepFailure('canonical_peer_eligible', 'Growth learning section missing')
    performance = page.locator(f'[data-testid="canonical-peer-performance-{subject_key}"]')
    coverage = page.locator(f'[data-testid="canonical-peer-coverage-{subject_key}"]')
    points = page.locator('[data-testid="canonical-peer-points"]')
    if performance.count() != 1:
        raise StepFailure('canonical_peer_eligible', 'performance peer block missing')
    if coverage.count() != 1:
        raise StepFailure('canonical_peer_eligible', 'coverage peer block missing')
    if points.count() != 1:
        raise StepFailure('canonical_peer_eligible', 'points peer block missing')
    if performance.get_attribute('data-display-tier') != 'primary':
        raise StepFailure('canonical_peer_eligible', 'expected primary performance peer')
    if coverage.get_attribute('data-display-tier') != 'primary':
        raise StepFailure('canonical_peer_eligible', 'expected primary coverage peer')
    if points.get_attribute('data-display-tier') != 'primary':
        raise StepFailure('canonical_peer_eligible', 'expected primary points peer')
    if performance.filter(has_text='같은 학년 또래 중앙값').count() == 0:
        raise StepFailure('canonical_peer_eligible', 'performance median copy missing')
    if coverage.filter(has_text='같은 교재 또래 중앙값').count() == 0:
        raise StepFailure('canonical_peer_eligible', 'coverage median copy missing')
    if points.filter(has_text='같은 학년 또래 중앙값').count() == 0:
        raise StepFailure('canonical_peer_eligible', 'points median copy missing')
    combined = performance.inner_text() + '\n' + coverage.inner_text() + '\n' + points.inner_text()
    for banned in BANNED_PEER_COPY:
        if banned in combined:
            raise StepFailure('canonical_peer_eligible', f'banned ranking copy in canonical peer: {banned}')
    mark('canonical_peer_eligible')

    _goto(page, f'{base_url}/children/{lonely_id}/growth', 'canonical_peer_unavailable')
    if '/login' in (page.url or ''):
        raise StepFailure('canonical_peer_unavailable', f'redirected to login: {page.url}')
    lonely_perf = page.locator(f'[data-testid="canonical-peer-performance-{subject_key}"]')
    lonely_cov = page.locator(f'[data-testid="canonical-peer-coverage-{subject_key}"]')
    lonely_points = page.locator('[data-testid="canonical-peer-points"]')
    if lonely_perf.count() != 1 or lonely_cov.count() != 1 or lonely_points.count() != 1:
        raise StepFailure('canonical_peer_unavailable', 'canonical peer blocks missing for lonely child')
    for block in (lonely_perf, lonely_cov, lonely_points):
        text = block.inner_text()
        if '비교 자료 없음' not in text and '비교 자료가 적어' not in text:
            raise StepFailure('canonical_peer_unavailable', f'expected unavailable copy, got {text!r}')
        if '또래 중앙값 0%' in text or '또래 중앙값 0점' in text:
            raise StepFailure('canonical_peer_unavailable', f'false zero median rendered: {text!r}')
        if block.get_attribute('data-display-tier') == 'primary':
            raise StepFailure('canonical_peer_unavailable', 'lonely child should not show primary peer')
    mark('canonical_peer_unavailable')
    return passed
