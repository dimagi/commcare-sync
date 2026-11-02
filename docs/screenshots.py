"""
Take the screenshots for the guides in this directory.

Run it against a running instance that holds the demo data below, and it
writes one PNG per guide to ``docs/images/``::

    COMMCARE_SYNC_URL=http://127.0.0.1:8000 \\
    COMMCARE_SYNC_EMAIL=admin@example.com \\
    COMMCARE_SYNC_PASSWORD=... \\
    uv run python docs/screenshots.py

The demo data, created by hand through the app before running this:

- A CommCare server ``Local CommCare HQ`` at ``http://localhost:8000``,
  added in the Django admin.
- A project ``demo`` on that server, and an account
  ``admin@example.com`` with an API key for it.
- A database ``Pipeline (PostgreSQL)``.
- An export ``Cases`` of the project's ``case`` export into that
  database, with a few completed runs, and one failed run as the latest
  (point the database at a wrong port for one run, then restore it).
- A materialized view ``case_counts`` in the database, and a refresh
  ``Case counts`` that refreshes it, with one completed run.
- A destination ``DHIS2 (example)`` and a forwarder
  ``OPV3 coverage to DHIS2``.
- A second user, ``maria@example.com``.

``install.png`` is not taken here: the setup page exists only before the
admin account does. Start the app with an empty data directory and run
``uv run python docs/screenshots.py install <setup link>`` instead.
"""

import os
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

IMAGES = Path(__file__).parent / 'images'
CHROMIUM = '/snap/bin/chromium'
VIEWPORT = {'width': 1280, 'height': 900}
CARD = 'section.app-card'
FAKE_API_KEY = '0123456789abcdef0123456789abcdef01234567'


def shoot(page, name, selector, max_height=None):
    page.wait_for_load_state('networkidle')
    element = page.locator(selector).first
    if max_height is None:
        element.screenshot(path=IMAGES / f'{name}.png')
    else:
        box = element.bounding_box()
        box['height'] = min(box['height'], max_height)
        page.screenshot(path=IMAGES / f'{name}.png', clip=box)
    print(name)


def select_by_text(page, selector, text):
    for option in page.locator(f'{selector} option').all():
        if text in option.inner_text():
            page.select_option(selector, option.get_attribute('value'))
            return
    raise LookupError(f'{text!r} is not an option of {selector}')


def login(page, base, email, password):
    page.goto(f'{base}/accounts/login/')
    page.fill('#id_username', email)
    page.fill('#id_password', password)
    page.click('form button[type=submit]')
    page.wait_for_load_state('networkidle')


def install(page, setup_link):
    page.goto(setup_link)
    page.fill('#id_email', 'admin@example.com')
    shoot(page, 'install', '#fullpage-form')


def add_commcare_project(page, base):
    page.goto(f'{base}/commcare/projects/create/')
    select_by_text(page, '#id_server', 'Local CommCare HQ')
    page.fill('#id_domain', 'demo')
    shoot(page, 'add-commcare-project', CARD)


def add_commcare_account(page, base):
    page.goto(f'{base}/commcare/accounts/create/')
    select_by_text(page, '#id_server', 'Local CommCare HQ')
    page.fill('#id_username', 'admin@example.com')
    page.fill('#id_api_key', FAKE_API_KEY)
    shoot(page, 'add-commcare-account', CARD)


def add_database(page, base):
    page.goto(f'{base}/databases/create/')
    page.fill('#id_name', 'Pipeline (PostgreSQL)')
    page.fill(
        '#id_connection_string',
        'postgresql://pipeline:secret@db.example.org:5432/pipeline',
    )
    shoot(page, 'add-database', CARD)


def fill_export_form(page):
    page.fill('#id_name', 'Cases')
    select_by_text(page, '#id_account', 'admin@example.com')
    page.wait_for_function(
        "document.querySelectorAll('#id_config_file_select option').length > 1"
    )
    select_by_text(page, '#id_config_file_select', 'case (')
    select_by_text(page, '#id_database', 'Pipeline')


def set_up_export(page, base):
    page.goto(f'{base}/exports/create/')
    select_by_text(page, '#id_project', 'demo')
    fill_export_form(page)
    page.select_option('#id_schedule_type', 'interval')
    page.fill('#id_interval_value', '1')
    page.select_option('#id_interval_unit', 'days')
    shoot(page, 'set-up-export', CARD)


def multi_project_export(page, base):
    page.goto(f'{base}/exports/create/multi-project/')
    page.check('input[name=projects]')
    fill_export_form(page)
    shoot(page, 'multi-project-export', CARD)


def schedules(page, base):
    page.goto(f'{base}/exports/create/')
    page.select_option('#id_schedule_type', 'weekly')
    page.fill('#id_first_run_date', '2026-12-07')
    page.fill('#id_first_run_time', '06:00')
    page.check('input[name=days_of_week][value="1"]')
    page.check('input[name=days_of_week][value="4"]')
    shoot(page, 'schedules', '.card:has(#id_schedule_type)')


def refresh_materialized_views(page, base):
    page.goto(f'{base}/refreshes/create/')
    page.fill('#id_name', 'Case counts')
    select_by_text(page, '#id_database', 'Pipeline')
    page.locator('#id_database').dispatch_event('change')
    page.locator('button', has_text='case_counts').first.click()
    page.select_option('#id_schedule_type', 'interval')
    page.fill('#id_interval_value', '6')
    page.select_option('#id_interval_unit', 'hours')
    shoot(page, 'refresh-materialized-views', CARD)


def forward_data(page, base):
    page.goto(f'{base}/forwarding/create/')
    page.fill('#id_name', 'OPV3 coverage to DHIS2')
    select_by_text(page, '#id_database', 'Pipeline')
    select_by_text(page, '#id_destination', 'DHIS2')
    page.fill(
        '#id_query',
        'SELECT json_payload FROM opv3_coverage_payload_view\n'
        "WHERE period = TO_CHAR(CURRENT_DATE - INTERVAL '1 month', 'YYYYMM');",
    )
    page.select_option('#id_schedule_type', 'monthly')
    page.fill('#id_first_run_date', '2026-12-01')
    page.fill('#id_first_run_time', '06:00')
    shoot(page, 'forward-data', CARD)


def monitor_runs(page, base):
    page.goto(f'{base}/exports/')
    shoot(page, 'monitor-runs', CARD)


def manage_users(page, base):
    page.goto(f'{base}/admin/users/customuser/add/')
    page.fill('#id_email', 'maria@example.com')
    shoot(page, 'manage-users', '#content')


def troubleshooting(page, base):
    page.goto(f'{base}/exports/view/1/')
    page.locator('#run-table tbody tr').first.get_by_text('Log').click()
    page.wait_for_selector('#run-table pre')
    shoot(page, 'troubleshooting', f'{CARD}:has(#run-table)', max_height=400)


SHOTS = (
    add_commcare_project,
    add_commcare_account,
    add_database,
    set_up_export,
    multi_project_export,
    schedules,
    refresh_materialized_views,
    forward_data,
    monitor_runs,
    manage_users,
    troubleshooting,
)


def browser_page(playwright) -> Page:
    executable = CHROMIUM if os.path.exists(CHROMIUM) else None
    browser = playwright.chromium.launch(executable_path=executable)
    return browser.new_page(viewport=VIEWPORT, device_scale_factor=1)


def main(argv):
    IMAGES.mkdir(exist_ok=True)
    with sync_playwright() as playwright:
        page = browser_page(playwright)
        if argv[:1] == ['install']:
            install(page, argv[1])
            return
        base = os.environ['COMMCARE_SYNC_URL'].rstrip('/')
        login(
            page,
            base,
            os.environ['COMMCARE_SYNC_EMAIL'],
            os.environ['COMMCARE_SYNC_PASSWORD'],
        )
        for shot in SHOTS:
            shot(page, base)


if __name__ == '__main__':
    main(sys.argv[1:])
