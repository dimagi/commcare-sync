from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from reversion.models import Version

from apps.db.models import Database as ExportDatabase

from ..models import RefreshConfig, RefreshRun


@pytest.mark.django_db
class TestRefreshConfig:
    def test_str_method(self, refresh_config):
        assert str(refresh_config) == 'Test Refresh Config'

    def test_last_run_with_no_runs(self, refresh_config):
        assert refresh_config.last_run is None

    def test_last_run_excludes_queued_runs(self, refresh_config):
        RefreshRun.objects.create(
            refresh_config=refresh_config,
            status=RefreshRun.Status.QUEUED,
        )
        assert refresh_config.last_run is None

    def test_last_run_returns_most_recent_non_queued(self, refresh_config):
        RefreshRun.objects.create(
            refresh_config=refresh_config,
            status=RefreshRun.Status.COMPLETED,
        )
        run2 = RefreshRun.objects.create(
            refresh_config=refresh_config,
            status=RefreshRun.Status.COMPLETED,
        )
        assert refresh_config.last_run == run2

    def test_has_queued_runs(self, refresh_config):
        RefreshRun.objects.create(
            refresh_config=refresh_config,
            status=RefreshRun.Status.QUEUED,
        )
        assert refresh_config.has_queued_runs()

    def test_has_queued_runs_false(self, refresh_config):
        RefreshRun.objects.create(
            refresh_config=refresh_config,
            status=RefreshRun.Status.COMPLETED,
        )
        assert not refresh_config.has_queued_runs()

    def test_latest_version_returns_version(self, refresh_config):
        version = refresh_config.latest_version
        assert version is not None
        assert isinstance(version, Version)

    def test_details_url(self, refresh_config):
        expected = f'/refreshes/{refresh_config.id}/'
        assert refresh_config.details_url == expected

    def test_save_creates_revision(self, refresh_config):
        initial_count = Version.objects.get_for_object(refresh_config).count()
        refresh_config.materialized_views = ['public.view1']
        refresh_config.save()
        new_count = Version.objects.get_for_object(refresh_config).count()
        assert new_count == initial_count + 1

    def test_validation_rejects_non_postgresql(self, user):
        db = ExportDatabase.objects.create(
            name='MySQL DB',
            connection_string='mysql://localhost/test',
            owner=user,
        )
        config = RefreshConfig(
            name='Invalid',
            database=db,
            materialized_views=['view1'],
            created_by=user,
        )
        with pytest.raises(ValidationError) as exc_info:
            config.full_clean()
        assert 'database' in exc_info.value.error_dict

    def test_validation_rejects_empty_views(self, user, database):
        config = RefreshConfig(
            name='Invalid',
            database=database,
            materialized_views=[],
            created_by=user,
        )
        with pytest.raises(ValidationError) as exc_info:
            config.full_clean()
        assert 'materialized_views' in exc_info.value.error_dict


@pytest.mark.django_db
class TestRefreshRun:
    def test_default_status_is_queued(self, refresh_config):
        run = RefreshRun.objects.create(refresh_config=refresh_config)
        assert run.status == RefreshRun.Status.QUEUED

    def test_str_method(self, refresh_config):
        run = RefreshRun.objects.create(refresh_config=refresh_config)
        assert refresh_config.name in str(run)

    def test_duration_calculation(self, refresh_config):
        run = RefreshRun.objects.create(
            refresh_config=refresh_config,
            status=RefreshRun.Status.STARTED,
            started_at=timezone.now(),
        )
        run.completed_at = run.started_at + timedelta(minutes=5)
        run.save()
        assert run.duration == timedelta(minutes=5)

    def test_duration_none_when_not_complete(self, refresh_config):
        run = RefreshRun.objects.create(
            refresh_config=refresh_config,
            status=RefreshRun.Status.STARTED,
            started_at=timezone.now(),
        )
        assert run.duration is None

    def test_mark_skipped_success(self, refresh_config):
        run = RefreshRun.objects.create(
            refresh_config=refresh_config,
            status=RefreshRun.Status.QUEUED,
        )
        run.mark_skipped()
        run.refresh_from_db()
        assert run.status == RefreshRun.Status.SKIPPED
        assert run.completed_at is not None

    def test_mark_skipped_raises_exception_when_started(self, refresh_config):
        run = RefreshRun.objects.create(
            refresh_config=refresh_config,
            status=RefreshRun.Status.STARTED,
        )
        with pytest.raises(ValueError):
            run.mark_skipped()
