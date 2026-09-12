"""Thin teacher assistant Playwright smoke. Step 3~7 suites are not re-run here."""
from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page

from smoke_step3 import StepFailure


def _ok(response, step: str, url: str) -> None:
    if response is None:
        raise StepFailure(step, f'no HTTP response for {url}')
    if response.status >= 400:
        raise StepFailure(step, f'{url} returned {response.status}')


def _goto(page: Page, url: str, step: str):
    response = page.goto(url, wait_until='domcontentloaded')
    _ok(response, step, url)
    return response


def _shot(page: Page, name: str) -> None:
    artifacts = Path(__file__).resolve().parents[2] / 'qa-results'
    artifacts.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(artifacts / name), full_page=False)


def _open_drawer(page: Page) -> None:
    drawer = page.locator('#teacherAssistantDrawer')
    classes = (drawer.get_attribute('class') or '').split()
    if 'show' not in classes and 'showing' not in classes:
        page.locator('[data-testid="teacher-assistant-launcher"]').click(force=True)
    page.wait_for_selector('#teacherAssistantDrawer.show', timeout=5000)


def run_authenticated_steps(page: Page, *, base_url: str, state: dict) -> list[tuple[str, str]]:
    passed: list[tuple[str, str]] = []
    child_id = int(state['child_id'])

    def mark(name: str) -> None:
        passed.append((name, 'PASS'))

    page.set_viewport_size({'width': 1280, 'height': 800})
    _goto(page, f'{base_url}/dashboard', 'dashboard_launcher')
    launcher = page.locator('[data-testid="teacher-assistant-launcher"]')
    if launcher.count() != 1:
        raise StepFailure('dashboard_launcher', 'teacher assistant launcher missing')
    drawer = page.locator('[data-testid="teacher-assistant-drawer"]')
    if drawer.count() != 1:
        raise StepFailure('dashboard_launcher', 'teacher assistant drawer missing')
    _shot(page, 'assistant-dashboard.png')
    mark('dashboard_launcher')

    _open_drawer(page)
    if not drawer.is_visible():
        raise StepFailure('dashboard_drawer', 'drawer did not open')
    if page.locator('#teacherAssistantTitle').inner_text().strip() != '뮤온':
        raise StepFailure('dashboard_drawer', 'drawer header is not 뮤온')
    page.get_by_text('센터 설정 이어서 하기').wait_for(timeout=8000)
    _shot(page, 'assistant-drawer.png')
    mark('dashboard_drawer')

    page.get_by_text('센터 설정 이어서 하기').click()
    open_btn = drawer.locator('[data-assistant-nav]')
    open_btn.first.wait_for(timeout=8000)
    href = open_btn.first.get_attribute('data-assistant-nav') or ''
    if not href.startswith('/settings/'):
        raise StepFailure('setup_continue', f'unexpected setup href {href!r}')
    mark('setup_continue')

    _goto(page, f'{base_url}/children/{child_id}', 'child_growth_nav')
    _open_drawer(page)
    page.locator('#teacherAssistantInput').wait_for(timeout=5000)
    page.fill('#teacherAssistantInput', '성장 리포트 열어줘')
    with page.expect_navigation(wait_until='domcontentloaded', timeout=8000):
        page.locator('[data-assistant-role="send"]').click()
    if '/growth' not in (page.url or ''):
        raise StepFailure('child_growth_nav', f'did not navigate to growth: {page.url}')
    mark('child_growth_nav')

    _goto(page, f'{base_url}/dashboard', 'help_rag_no_nav')
    _open_drawer(page)
    page.fill('#teacherAssistantInput', '기본 학습요일이 무슨 뜻이야?')
    page.locator('[data-assistant-role="send"]').click()
    page.get_by_text('월~금', exact=False).wait_for(timeout=8000)
    if '/settings/' in (page.url or ''):
        raise StepFailure('help_rag_no_nav', f'help question navigated away: {page.url}')
    help_chip = page.locator('[data-testid="assistant-sources"] .assistant-source.is-help')
    if help_chip.count() < 1:
        raise StepFailure('help_rag_no_nav', 'help source chip missing')
    mark('help_rag_no_nav')

    _goto(page, f'{base_url}/children/{child_id}', 'child_facts_sources')
    _open_drawer(page)
    page.fill('#teacherAssistantInput', '학습 요약 알려줘')
    page.locator('[data-assistant-role="send"]').click()
    last = page.locator('.assistant-bubble.is-assistant').last
    last.locator('.assistant-source.is-data').first.wait_for(timeout=8000)
    if last.locator('.assistant-source.is-help').count() != 0:
        raise StepFailure('child_facts_sources', 'data answer showed help sources')
    mark('child_facts_sources')

    page.set_viewport_size({'width': 390, 'height': 844})
    _goto(page, f'{base_url}/dashboard', 'mobile_sheet')
    _open_drawer(page)
    box = page.locator('#teacherAssistantDrawer').bounding_box()
    if box is None or box['width'] < 350:
        raise StepFailure('mobile_sheet', f'drawer not near-full width: {box}')
    _shot(page, 'assistant-mobile.png')
    mark('mobile_sheet')
    return passed
