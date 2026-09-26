from django.conf import settings
from django.test import override_settings

from apps.schedules.checks import check_retry_outlasts_reaping


def test_the_configured_retry_outlasts_reaping():
    assert check_retry_outlasts_reaping(None) == []


def test_a_retry_that_comes_before_reaping_is_an_error():
    q_cluster = {**settings.Q_CLUSTER, 'retry': settings.Q_CLUSTER['timeout']}

    with override_settings(Q_CLUSTER=q_cluster):
        errors = check_retry_outlasts_reaping(None)

    assert [error.id for error in errors] == ['schedules.E001']
