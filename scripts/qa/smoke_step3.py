"""Step 3 teacher-only Playwright smoke. Domain math is not re-checked here."""
from __future__ import annotations

from playwright.sync_api import Page


class StepFailure(Exception):
    def __init__(self, step: str, message: str, results: list[tuple[str, str]] | None = None):
        super().__init__(message)
        self.step = step
        self.message = message
        self.results = list(results or [])


def _ok(response, step: str, url: str) -> None:
    if response is None:
        raise StepFailure(step, f'no HTTP response for {url}')
    if response.status >= 400:
        raise StepFailure(step, f'{url} returned {response.status}')


def _goto(page: Page, url: str, step: str):
    response = page.goto(url, wait_until='domcontentloaded')
    _ok(response, step, url)
    return response


def login_load(page: Page, base_url: str) -> None:
    _goto(page, f'{base_url}/login', 'login_load')
    if page.locator('#firebaseui-auth-container').count() == 0:
        raise StepFailure('login_load', 'login page missing #firebaseui-auth-container')


def run_authenticated_steps(page: Page, *, base_url: str, state: dict) -> list[tuple[str, str]]:
    passed: list[tuple[str, str]] = []
    child_id = int(state['child_id'])
    subject_id = int(state['subject_id'])
    as_of = state['as_of']
    ns_day = state['non_study_day']
    ns_year = int(state['non_study_year'])
    ns_month = int(state['non_study_month'])
    ns_label = state['non_study_label']

    def mark(name: str) -> None:
        passed.append((name, 'PASS'))

    _goto(page, f'{base_url}/settings/subject-weekdays', 'teacher_session')
    if '/login' in (page.url or ''):
        raise StepFailure('teacher_session', f'redirected to login: {page.url}')
    mark('teacher_session')

    form = page.locator('[data-testid="subject-weekdays-form"]')
    if form.count() != 1:
        raise StepFailure('subject_weekdays_save', 'subject weekdays form not found')
    with page.expect_navigation(wait_until='domcontentloaded'):
        form.locator('button[type="submit"]').click()
    if page.locator('[data-testid="subject-weekdays-form"]').count() == 0:
        raise StepFailure('subject_weekdays_save', 'form missing after save')
    mark('subject_weekdays_save')

    ns_url = f'{base_url}/settings/non-study-days?year={ns_year}&month={ns_month}'
    _goto(page, ns_url, 'non_study_add_list_delete')
    add_form = page.locator('[data-testid="non-study-add-form"]')
    if add_form.count() != 1:
        raise StepFailure('non_study_add_list_delete', 'non-study add form not found')
    add_form.locator('#non-study-day').fill(ns_day)
    add_form.locator('#non-study-label').fill(ns_label)
    with page.expect_navigation(wait_until='domcontentloaded'):
        add_form.locator('button[type="submit"]').click()
    day_input = page.locator(f'input[type="hidden"][name="day"][value="{ns_day}"]')
    if day_input.count() == 0:
        raise StepFailure('non_study_add_list_delete', f'added day {ns_day} not listed')
    restore_form = day_input.locator('xpath=ancestor::form')
    with page.expect_navigation(wait_until='domcontentloaded'):
        restore_form.locator('button[type="submit"]').click()
    if page.locator(f'input[type="hidden"][name="day"][value="{ns_day}"]').count() != 0:
        raise StepFailure('non_study_add_list_delete', f'day {ns_day} still listed after delete')
    mark('non_study_add_list_delete')

    _goto(page, f'{base_url}/children/{child_id}', 'child_study_form')
    wrap = page.locator('[data-testid="teacher-study-form"]')
    if wrap.count() != 1:
        raise StepFailure('child_study_form', 'teacher study form wrapper not found')
    summary = wrap.locator('summary')
    if summary.count():
        summary.click()
    study_form = wrap.locator('#study-session-form-detail')
    if study_form.count() != 1 or not study_form.is_visible():
        raise StepFailure('child_study_form', 'teacher study form not visible')
    mark('child_study_form')

    post_url = f'{base_url}/children/{child_id}/study-post-entry?study_date={as_of}'
    _goto(page, post_url, 'post_entry_open')
    post_form = page.locator('[data-testid="teacher-post-entry-form"]')
    if post_form.count() != 1:
        raise StepFailure('post_entry_open', 'teacher post-entry form not found')
    status = post_form.locator(f'input[name="study_status_{subject_id}"][value="studied"]')
    if status.count() == 0:
        raise StepFailure(
            'post_entry_open',
            f'no post-entry row for subject {subject_id} on {as_of}',
        )
    mark('post_entry_open')

    status.check()
    post_form.locator(f'#start_page_{subject_id}').fill('10')
    post_form.locator(f'#end_page_{subject_id}').fill('12')
    with page.expect_navigation(wait_until='domcontentloaded'):
        post_form.locator('button[type="submit"]').click()
    if '/login' in (page.url or ''):
        raise StepFailure('post_entry_save', 'redirected to login after save')
    leftover = page.locator(f'input[name="study_status_{subject_id}"]')
    if leftover.count() != 0:
        raise StepFailure('post_entry_save', 'post-entry row still present after save')
    if page.locator('body').count() == 0:
        raise StepFailure('post_entry_save', 'page body missing after save')
    mark('post_entry_save')
    return passed


def mint_session_cookie(secret_key: str, user_id: int) -> str:
    from flask import Flask
    from flask.sessions import SecureCookieSessionInterface

    signer_app = Flask('clc-qa-session')
    signer_app.secret_key = secret_key
    serializer = SecureCookieSessionInterface().get_signing_serializer(signer_app)
    if serializer is None:
        raise RuntimeError('Could not create Flask session serializer.')
    return serializer.dumps({'_user_id': str(user_id), '_fresh': True})
