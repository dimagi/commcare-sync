from datetime import timedelta

from django.db import connection
from django.test import Client, RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from unmagic import fixture, use

from apps.commcare.models import RunBaseModel
from apps.exports.models import MultiProjectPartialExportRun
from apps.forwarding.models import ForwardingRun
from apps.forwarding.tests.fixtures import destination, forwarding_config
from apps.refreshes.models import RefreshConfig, RefreshRun
from apps.web.failed_runs import (
    DISMISSED_AT_SESSION_KEY,
    MAX_ENTRIES,
    recent_failed_runs,
)
from apps.web.templatetags.failed_runs_tags import failed_runs_banner
from tests.fixtures import authed_client, commcare_project, database, user

FAILED = RunBaseModel.Status.FAILED
INTERRUPTED = RunBaseModel.Status.INTERRUPTED


@fixture
@use('db')
def refresh_config():
    yield RefreshConfig.objects.create(
        name='Nightly Views', database=database(), materialized_views=['v']
    )


def ago(**kwargs):
    return timezone.now() - timedelta(**kwargs)


def forwarding_run(status, completed_at=None):
    return ForwardingRun.objects.create(
        config=forwarding_config(), status=status, completed_at=completed_at
    )


@use(database, destination, forwarding_config, refresh_config)
class TestRecentFailedRuns:
    def test_collects_failed_and_interrupted_runs_across_models(self):
        forwarding_run(FAILED, ago(hours=2))
        RefreshRun.objects.create(
            config=refresh_config(),
            status=INTERRUPTED,
            completed_at=ago(hours=1),
        )

        failed = recent_failed_runs(since=ago(hours=24))

        assert failed.total_count == 2
        assert [(e.label, e.kind, e.status) for e in failed.entries] == [
            ('Nightly Views', 'refresh run', 'Interrupted'),
            ('Test Forwarder', 'forwarding run', 'Failed'),
        ]

    def test_ignores_runs_that_did_not_fail(self):
        for status in RunBaseModel.Status:
            if status not in RunBaseModel.FAILED_STATUSES:
                forwarding_run(status, ago(hours=1))

        assert recent_failed_runs(since=ago(hours=24)).total_count == 0

    def test_ignores_failures_before_since(self):
        forwarding_run(FAILED, ago(hours=25))

        assert recent_failed_runs(since=ago(hours=24)).total_count == 0

    def test_counts_every_failure_but_lists_only_the_newest(self):
        for hours in range(MAX_ENTRIES + 2):
            forwarding_run(FAILED, ago(hours=hours))

        failed = recent_failed_runs(since=ago(hours=24))

        assert failed.total_count == MAX_ENTRIES + 2
        assert len(failed.entries) == MAX_ENTRIES
        assert failed.entries[0].completed_at > failed.entries[-1].completed_at

    @use(commcare_project)
    def test_a_partial_export_run_is_labelled_by_its_project(self):
        MultiProjectPartialExportRun.objects.create(
            project=commcare_project(), status=FAILED, completed_at=ago()
        )

        [entry] = recent_failed_runs(since=ago(hours=24)).entries

        assert entry.label == str(commcare_project())


@use(database, destination, forwarding_config)
class TestFailedRunsBanner:
    @use(user)
    def test_nothing_for_anonymous_users(self):
        forwarding_run(FAILED, ago(hours=1))
        request = RequestFactory().get('/')
        request.user = Client().get(reverse('login')).wsgi_request.user

        assert failed_runs_banner({'request': request}) == {
            'failed_runs': None
        }

    @use(authed_client)
    def test_nothing_without_a_recent_failure(self):
        forwarding_run(FAILED, ago(hours=25))

        response = authed_client().get(reverse('exports:home'))

        assert 'failed-runs-banner' not in response.content.decode()

    @use(authed_client)
    def test_lists_recent_failures_on_every_app_page(self):
        forwarding_run(INTERRUPTED, ago(hours=1))

        response = authed_client().get(reverse('exports:home'))

        content = response.content.decode()
        assert 'id="failed-runs-banner"' in content
        assert 'A run did not finish' in content
        assert 'Test Forwarder' in content
        assert 'Interrupted' in content
        assert 'an hour ago' in content

    @use(authed_client)
    def test_says_how_many_more_than_it_lists(self):
        for hours in range(MAX_ENTRIES + 2):
            forwarding_run(FAILED, ago(hours=hours))

        response = authed_client().get(reverse('exports:home'))

        content = response.content.decode()
        assert f'{MAX_ENTRIES + 2} runs did not finish' in content
        assert 'and 2 more' in content

    @use(authed_client)
    def test_dismissing_hides_it_until_a_newer_failure(self):
        forwarding_run(FAILED, ago(hours=1))
        client = authed_client()
        assert (
            'failed-runs-banner'
            in client.get(reverse('exports:home')).content.decode()
        )

        response = client.post(reverse('web:dismiss_failed_runs_banner'))

        assert response.status_code == 204
        assert DISMISSED_AT_SESSION_KEY in client.session
        assert (
            'failed-runs-banner'
            not in client.get(reverse('exports:home')).content.decode()
        )

        forwarding_run(FAILED, timezone.now())
        content = client.get(reverse('exports:home')).content.decode()
        assert 'A run did not finish' in content

    @use(authed_client)
    def test_a_dismissal_it_cannot_read_is_ignored(self):
        forwarding_run(FAILED, ago(hours=1))
        client = authed_client()
        session = client.session
        session[DISMISSED_AT_SESSION_KEY] = 'yesterday-ish'
        session.save()

        response = client.get(reverse('exports:home'))

        assert response.status_code == 200
        assert 'failed-runs-banner' in response.content.decode()

    @use(user)
    def test_dismissing_requires_a_signed_in_user(self):
        response = Client().post(reverse('web:dismiss_failed_runs_banner'))

        assert response.status_code == 302
        assert response.url.startswith(reverse('login'))

    @use(authed_client)
    def test_a_partial_page_update_pays_nothing_for_it(self):
        forwarding_run(FAILED, ago(hours=1))
        url = reverse(
            'forwarding:run_history_table', args=[forwarding_config().id]
        )

        with CaptureQueriesContext(connection) as queries:
            authed_client().get(url, headers={'HX-Request': 'true'})

        # The banner looks at every run model; the partial, at one.
        assert not any('refreshes_refreshrun' in q['sql'] for q in queries)
