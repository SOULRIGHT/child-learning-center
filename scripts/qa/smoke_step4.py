"""Step 4 teacher-only Playwright smoke. Domain math is not re-checked here."""
from __future__ import annotations

from datetime import date, timedelta

from playwright.sync_api import Page

from smoke_step3 import StepFailure, _goto


def run_authenticated_steps(page: Page, *, base_url: str, state: dict) -> list[tuple[str, str]]:
    passed: list[tuple[str, str]] = []
    child_id = int(state['child_id'])
    sparse_id = int(state['sparse_child_id'])
    subject_id = int(state['subject_id'])
    subject_key = str(state.get('subject_key') or 'math')
    as_of = date.fromisoformat(state['as_of'])

    def mark(name: str) -> None:
        passed.append((name, 'PASS'))

    _goto(page, f'{base_url}/settings/workbook-plans', 'workbook_exclusion_save')
    if '/login' in (page.url or ''):
        raise StepFailure('workbook_exclusion_save', f'redirected to login: {page.url}')
    form = page.locator('[data-testid="workbook-plan-create-form"]')
    if form.count() != 1:
        raise StepFailure('workbook_exclusion_save', 'workbook plan create form not found')
    exclusions = form.locator('[data-testid="workbook-plan-exclusions"]')
    if exclusions.count() != 1:
        raise StepFailure('workbook_exclusion_save', 'exclusion field not found')
    form.locator('#create-plan-grade').select_option('3')
    form.locator('#create-plan-subject').select_option(str(subject_id))
    form.locator('#create-plan-title').fill('QA Exclusion 교재')
    form.locator('#create-plan-start-page').fill('1')
    form.locator('#create-plan-end-page').fill('100')
    form.locator('#create-plan-start-date').fill((as_of - timedelta(days=10)).isoformat())
    form.locator('#create-plan-target-date').fill((as_of + timedelta(days=120)).isoformat())
    exclusions.fill('90-95')
    with page.expect_navigation(wait_until='domcontentloaded'):
        form.locator('[data-testid="workbook-plan-save"]').click()
    if '/login' in (page.url or ''):
        raise StepFailure('workbook_exclusion_save', 'redirected to login after save')
    body = page.locator('body')
    if body.filter(has_text='QA Exclusion 교재').count() == 0:
        raise StepFailure('workbook_exclusion_save', 'saved workbook plan title not listed')
    mark('workbook_exclusion_save')

    _goto(page, f'{base_url}/children/{child_id}', 'study_range_then_growth')
    wrap = page.locator('[data-testid="teacher-study-form"]')
    if wrap.count() != 1:
        raise StepFailure('study_range_then_growth', 'teacher study form wrapper not found')
    summary = wrap.locator('summary')
    if summary.count():
        summary.click()
    study_form = wrap.locator('#study-session-form-detail')
    if study_form.count() != 1 or not study_form.is_visible():
        raise StepFailure('study_range_then_growth', 'teacher study form not visible')
    study_form.locator('#learning_subject_id_detail').select_option(str(subject_id))
    study_form.locator('#start_page_detail').fill('1')
    study_form.locator('#end_page_detail').fill('10')
    with page.expect_navigation(wait_until='domcontentloaded'):
        study_form.locator('button[type="submit"]').click()
    if '/login' in (page.url or ''):
        raise StepFailure('study_range_then_growth', 'redirected to login after first range')

    wrap = page.locator('[data-testid="teacher-study-form"]')
    summary = wrap.locator('summary')
    if summary.count():
        summary.click()
    study_form = wrap.locator('#study-session-form-detail')
    if study_form.count() != 1:
        raise StepFailure('study_range_then_growth', 'teacher study form missing for second range')
    if not study_form.is_visible() and summary.count():
        summary.click()
    study_form.locator('#learning_subject_id_detail').select_option(str(subject_id))
    study_form.locator('#start_page_detail').fill('5')
    study_form.locator('#end_page_detail').fill('15')
    with page.expect_navigation(wait_until='domcontentloaded'):
        study_form.locator('button[type="submit"]').click()

    growth_url = f'{base_url}/children/{child_id}/growth'
    _goto(page, growth_url, 'study_range_then_growth')
    if page.locator('[data-growth-learning]').count() != 1:
        raise StepFailure('study_range_then_growth', 'Growth learning section missing')
    observed = page.locator(f'[data-testid="observed-progress-{subject_key}"]')
    if observed.count() != 1:
        raise StepFailure('study_range_then_growth', 'observed progress block missing')
    if observed.filter(has_text='관측 기반 진도').count() == 0:
        raise StepFailure('study_range_then_growth', 'observed progress label missing')
    mark('study_range_then_growth')

    _goto(page, f'{base_url}/children/{sparse_id}/growth', 'insufficient_forecast_na')
    if '/login' in (page.url or ''):
        raise StepFailure('insufficient_forecast_na', f'redirected to login: {page.url}')
    sparse_block = page.locator(f'[data-testid="observed-progress-{subject_key}"]')
    if sparse_block.count() != 1:
        raise StepFailure('insufficient_forecast_na', 'sparse child observed block missing')
    if sparse_block.locator('[data-testid="observed-forecast-unavailable"]').count() != 1:
        raise StepFailure('insufficient_forecast_na', 'expected N/A forecast, found a date range')
    if sparse_block.locator('[data-testid="observed-forecast-range"]').count() != 0:
        raise StepFailure('insufficient_forecast_na', 'forecast range was rendered without enough data')
    na_text = sparse_block.locator('[data-testid="observed-forecast-unavailable"]').inner_text()
    if 'N/A' not in na_text:
        raise StepFailure('insufficient_forecast_na', f'forecast unavailable text missing N/A: {na_text!r}')
    mark('insufficient_forecast_na')
    return passed
