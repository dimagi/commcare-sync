"""
Shared helper functions for Playwright tests.
"""
from django.urls import reverse

from apps.exports.models import ExportRun


def login(page, live_server, user):
    """Helper to log in a user."""
    page.goto(f'{live_server.url}{reverse("login")}')
    page.fill('input[name="username"]', user.email)
    page.fill('input[name="password"]', 'testpass')
    page.click('button[type="submit"]')
    page.wait_for_url(lambda url: reverse('login') not in url)


def navigate_to_create_export(page, live_server):
    """Helper to navigate to the create export page."""
    page.goto(f'{live_server.url}{reverse("exports:create_export_config")}')


def navigate_to_export_details(page, live_server, export_id):
    """Helper to navigate to export details page."""
    page.goto(f'{live_server.url}{reverse(
        "exports:export_details",
        args=[export_id],
    )}')


def route_run_trigger(page, export):
    """Answer the Run button of ``export`` as if a run had started.

    The response names a status URL, which ``route_run_status`` answers.
    """
    page.route(
        f'**/exports/api/run/{export.id}/**',
        lambda route: route.fulfill(
            json={'poll_url': '/exports/runs/1/status/'}
        ),
    )


def route_run_status(page, *statuses):
    """Answer status polls for a run in each of ``statuses`` in turn.

    The last status repeats. Returns the URLs polled, as they are polled.
    """
    polls = []

    def fulfill(route):
        polls.append(route.request.url)
        status = statuses[min(len(polls), len(statuses)) - 1]
        route.fulfill(json=status_payload(status))

    page.route('**/runs/**/status/', fulfill)
    return polls


def status_payload(status):
    """Return the status endpoint's JSON for a run in ``status``."""
    run = ExportRun(status=status)
    return {
        'status': run.status,
        'label': run.get_status_display(),
        'tone': run.tone,
        'complete': run.is_terminal,
    }
