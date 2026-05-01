from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from reversion.models import Version
from unmagic import use

from apps.db.models import Database
from tests.fixtures import database

from ..models import RefreshConfig, RefreshRun
from .fixtures import refresh_config as _refresh_config


@use('db')
class TestRefreshConfig:
    @use(_refresh_config)
    def test_str_method(self):
        assert str(_refresh_config()) == 'Test Refresh Config'

    @use(_refresh_config)
    def test_last_run_with_no_runs(self):
        assert _refresh_config().last_run is None

    @use(_refresh_config)
    def test_last_run_excludes_queued_runs(self):
        config = _refresh_config()
        RefreshRun.objects.create(
            refresh_config=config,
            status=RefreshRun.Status.QUEUED,
        )
        assert config.last_run is None

    @use(_refresh_config)
    def test_last_run_returns_most_recent_non_queued(self):
        config = _refresh_config()
        RefreshRun.objects.create(
            refresh_config=config,
            status=RefreshRun.Status.COMPLETED,
        )
        run2 = RefreshRun.objects.create(
            refresh_config=config,
            status=RefreshRun.Status.COMPLETED,
        )
        assert config.last_run == run2

    @use(_refresh_config)
    def test_has_queued_runs(self):
        config = _refresh_config()
        RefreshRun.objects.create(
            refresh_config=config,
            status=RefreshRun.Status.QUEUED,
        )
        assert config.has_queued_runs()

    @use(_refresh_config)
    def test_has_queued_runs_false(self):
        config = _refresh_config()
        RefreshRun.objects.create(
            refresh_config=config,
            status=RefreshRun.Status.COMPLETED,
        )
        assert not config.has_queued_runs()

    @use(_refresh_config)
    def test_latest_version_returns_version(self):
        version = _refresh_config().latest_version
        assert version is not None
        assert isinstance(version, Version)

    @use(_refresh_config)
    def test_details_url(self):
        config = _refresh_config()
        expected = f'/refreshes/{config.id}/'
        assert config.details_url == expected

    @use(_refresh_config)
    def test_save_creates_revision(self):
        config = _refresh_config()
        initial_count = Version.objects.get_for_object(config).count()
        config.materialized_views = ['public.view1']
        config.save()
        new_count = Version.objects.get_for_object(config).count()
        assert new_count == initial_count + 1

    def test_validation_rejects_non_postgresql(self):
        db = Database.objects.create(
            name='MySQL DB',
            connection_string='mysql://localhost/test',
        )
        config = RefreshConfig(
            name='Invalid',
            database=db,
            materialized_views=['view1'],
        )
        with pytest.raises(ValidationError) as exc_info:
            config.full_clean()
        assert 'database' in exc_info.value.error_dict

    @use(database)
    def test_validation_rejects_empty_views(self):
        config = RefreshConfig(
            name='Invalid',
            database=database(),
            materialized_views=[],
        )
        with pytest.raises(ValidationError) as exc_info:
            config.full_clean()
        assert 'materialized_views' in exc_info.value.error_dict


@use('db')
class TestRefreshRun:
    @use(_refresh_config)
    def test_default_status_is_queued(self):
        run = RefreshRun.objects.create(refresh_config=_refresh_config())
        assert run.status == RefreshRun.Status.QUEUED

    @use(_refresh_config)
    def test_str_method(self):
        config = _refresh_config()
        run = RefreshRun.objects.create(refresh_config=config)
        assert config.name in str(run)

    @use(_refresh_config)
    def test_duration_calculation(self):
        run = RefreshRun.objects.create(
            refresh_config=_refresh_config(),
            status=RefreshRun.Status.STARTED,
            started_at=timezone.now(),
        )
        run.completed_at = run.started_at + timedelta(minutes=5)
        run.save()
        assert run.duration == timedelta(minutes=5)

    @use(_refresh_config)
    def test_duration_none_when_not_complete(self):
        run = RefreshRun.objects.create(
            refresh_config=_refresh_config(),
            status=RefreshRun.Status.STARTED,
            started_at=timezone.now(),
        )
        assert run.duration is None

    @use(_refresh_config)
    def test_mark_skipped_success(self):
        run = RefreshRun.objects.create(
            refresh_config=_refresh_config(),
            status=RefreshRun.Status.QUEUED,
        )
        run.mark_skipped()
        run.refresh_from_db()
        assert run.status == RefreshRun.Status.SKIPPED
        assert run.completed_at is not None

    @use(_refresh_config)
    def test_mark_skipped_raises_exception_when_started(self):
        run = RefreshRun.objects.create(
            refresh_config=_refresh_config(),
            status=RefreshRun.Status.STARTED,
        )
        with pytest.raises(ValueError):
            run.mark_skipped()


@use('db')
class TestRefreshConfigHasActiveRun:
    @use(_refresh_config)
    def test_false_with_no_runs(self):
        assert _refresh_config().has_active_run is False

    @use(_refresh_config)
    def test_false_when_run_is_completed(self):
        config = _refresh_config()
        RefreshRun.objects.create(
            refresh_config=config,
            status=RefreshRun.Status.COMPLETED,
        )
        assert config.has_active_run is False

    @use(_refresh_config)
    def test_false_when_run_is_failed(self):
        config = _refresh_config()
        RefreshRun.objects.create(
            refresh_config=config,
            status=RefreshRun.Status.FAILED,
        )
        assert config.has_active_run is False

    @use(_refresh_config)
    def test_true_when_run_is_queued(self):
        config = _refresh_config()
        RefreshRun.objects.create(
            refresh_config=config,
            status=RefreshRun.Status.QUEUED,
        )
        assert config.has_active_run is True

    @use(_refresh_config)
    def test_true_when_run_is_started(self):
        config = _refresh_config()
        RefreshRun.objects.create(
            refresh_config=config,
            status=RefreshRun.Status.STARTED,
        )
        assert config.has_active_run is True

    @use(_refresh_config)
    def test_uses_prefetched_runs_without_db_query(self):
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        config = _refresh_config()
        run = RefreshRun.objects.create(
            refresh_config=config,
            status=RefreshRun.Status.QUEUED,
        )
        config._all_runs = [run]
        with CaptureQueriesContext(connection) as ctx:
            result = config.has_active_run
        assert len(ctx) == 0
        assert result is True
