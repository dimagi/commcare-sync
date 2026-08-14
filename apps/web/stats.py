from datetime import timedelta

from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F

from apps.exports.models import (
    ExportConfig,
    ExportRun,
    MultiProjectExportConfig,
    MultiProjectExportRun,
)
from apps.web.templatetags.dateformat_tags import readable_timedelta
from apps.forwarding.models import ForwardingConfig, ForwardingRun
from apps.refreshes.models import RefreshConfig, RefreshRun


def _avg_runtime_for_runs(*queryset_status_pairs):
    """Compute weighted average runtime for completed runs across multiple querysets.

    Each argument is a (queryset, completed_status_value) pair.
    Returns the average as a timedelta, or None if there are no completed runs.
    """
    total_seconds = 0.0
    total_count = 0
    for qs, completed_status in queryset_status_pairs:
        result = qs.filter(
            status=completed_status,
            started_at__isnull=False,
            completed_at__isnull=False,
        ).aggregate(
            avg=Avg(ExpressionWrapper(
                F('completed_at') - F('started_at'),
                output_field=DurationField()
            )),
            count=Count('id'),
        )
        if result['avg'] and result['count']:
            total_seconds += result['avg'].total_seconds() * result['count']
            total_count += result['count']
    if total_count > 0:
        return timedelta(seconds=total_seconds / total_count)
    return None


def _get_success_trend(current_rate, previous_rate):
    """Compare current and previous success rates, return trend direction."""
    if current_rate > previous_rate:
        return 'up'
    elif current_rate < previous_rate:
        return 'down'
    return 'flat'


def _get_export_statistics(since_datetime, previous_start=None):
    """Calculate export pipeline statistics."""
    export_configs = ExportConfig.objects.count()
    multi_export_configs = MultiProjectExportConfig.objects.count()
    total_configs = export_configs + multi_export_configs

    recent_export_runs = ExportRun.objects.filter(
        created_at__gte=since_datetime
    ).exclude(status=ExportRun.Status.QUEUED)

    recent_multi_runs = MultiProjectExportRun.objects.filter(
        created_at__gte=since_datetime
    ).exclude(status=MultiProjectExportRun.Status.QUEUED)

    total_runs = recent_export_runs.count() + recent_multi_runs.count()
    successful_runs = (
        recent_export_runs
        .filter(status=ExportRun.Status.COMPLETED)
        .count()
    ) + (
        recent_multi_runs
        .filter(status=MultiProjectExportRun.Status.COMPLETED)
        .count()
    )
    failed_statuses = [
        ExportRun.Status.FAILED,
        ExportRun.Status.TIMEOUT,
    ]
    failed_runs = (
        recent_export_runs
        .filter(status__in=failed_statuses)
        .count()
    ) + (
        recent_multi_runs
        .filter(status__in=failed_statuses)
        .count()
    )

    success_rate = (successful_runs / total_runs * 100) if total_runs > 0 else 0

    configs = list(
        ExportConfig.objects.select_related('project')
        .order_by('-updated_at')[:10]
    )

    if total_runs == 0:
        status = 'neutral'
    elif success_rate >= 95:
        status = 'healthy'
    elif success_rate >= 80:
        status = 'warning'
    else:
        status = 'error'

    prev_success_rate = 0
    if previous_start is not None:
        prev_export_runs = ExportRun.objects.filter(
            created_at__gte=previous_start, created_at__lt=since_datetime,
        ).exclude(status=ExportRun.Status.QUEUED)
        prev_multi_runs = MultiProjectExportRun.objects.filter(
            created_at__gte=previous_start, created_at__lt=since_datetime,
        ).exclude(status=MultiProjectExportRun.Status.QUEUED)
        prev_total = prev_export_runs.count() + prev_multi_runs.count()
        if prev_total > 0:
            prev_successful = (
                prev_export_runs
                .filter(status=ExportRun.Status.COMPLETED)
                .count()
            ) + (
                prev_multi_runs
                .filter(status=MultiProjectExportRun.Status.COMPLETED)
                .count()
            )
            prev_success_rate = prev_successful / prev_total * 100

    avg_runtime = _avg_runtime_for_runs(
        (recent_export_runs, ExportRun.Status.COMPLETED),
        (recent_multi_runs, MultiProjectExportRun.Status.COMPLETED),
    )
    return {
        'total_configs': total_configs,
        'configs': configs,
        'last_24h_runs': total_runs,
        'success_rate': round(success_rate, 1),
        'success_trend': _get_success_trend(success_rate, prev_success_rate),
        'successful_count': successful_runs,
        'failed_count': failed_runs,
        'status': status,
        'avg_runtime': readable_timedelta(avg_runtime, short=True),
    }


def _get_refresh_statistics(since_datetime, previous_start=None):
    """Calculate refresh pipeline statistics."""
    total_configs = RefreshConfig.objects.count()

    recent_runs = RefreshRun.objects.filter(
        created_at__gte=since_datetime
    ).exclude(status=RefreshRun.Status.QUEUED)

    total_runs = recent_runs.count()
    successful_runs = recent_runs.filter(
        status=RefreshRun.Status.COMPLETED
    ).count()
    failed_statuses = [RefreshRun.Status.FAILED, RefreshRun.Status.TIMEOUT]
    failed_runs = recent_runs.filter(status__in=failed_statuses).count()

    success_rate = (successful_runs / total_runs * 100) if total_runs > 0 else 0

    configs = list(
        RefreshConfig.objects.select_related('database')
        .order_by('-updated_at')[:10]
    )

    if total_runs == 0:
        status = 'neutral'
    elif success_rate >= 95:
        status = 'healthy'
    elif success_rate >= 80:
        status = 'warning'
    else:
        status = 'error'

    prev_success_rate = 0
    if previous_start is not None:
        prev_runs = RefreshRun.objects.filter(
            created_at__gte=previous_start, created_at__lt=since_datetime,
        ).exclude(status=RefreshRun.Status.QUEUED)
        prev_total = prev_runs.count()
        if prev_total > 0:
            prev_successful = prev_runs.filter(
                status=RefreshRun.Status.COMPLETED
            ).count()
            prev_success_rate = prev_successful / prev_total * 100

    avg_runtime = _avg_runtime_for_runs(
        (recent_runs, RefreshRun.Status.COMPLETED),
    )
    return {
        'total_configs': total_configs,
        'configs': configs,
        'last_24h_runs': total_runs,
        'success_rate': round(success_rate, 1),
        'success_trend': _get_success_trend(success_rate, prev_success_rate),
        'successful_count': successful_runs,
        'failed_count': failed_runs,
        'status': status,
        'avg_runtime': readable_timedelta(avg_runtime, short=True),
    }


def _get_forwarding_statistics(since_datetime, previous_start=None):
    """Calculate forwarding pipeline statistics."""
    total_configs = ForwardingConfig.objects.count()

    recent_runs = ForwardingRun.objects.filter(
        created_at__gte=since_datetime
    ).exclude(status=ForwardingRun.Status.QUEUED)

    total_runs = recent_runs.count()
    successful_runs = recent_runs.filter(
        status=ForwardingRun.Status.COMPLETED
    ).count()
    failed_statuses = [ForwardingRun.Status.FAILED, ForwardingRun.Status.TIMEOUT]
    failed_runs = (
        recent_runs
        .filter(status__in=failed_statuses)
        .count()
    )

    success_rate = (successful_runs / total_runs * 100) if total_runs > 0 else 0

    configs = list(
        ForwardingConfig.objects.select_related('destination')
        .order_by('-updated_at')[:10]
    )

    if total_runs == 0:
        status = 'neutral'
    elif success_rate >= 95:
        status = 'healthy'
    elif success_rate >= 80:
        status = 'warning'
    else:
        status = 'error'

    prev_success_rate = 0
    if previous_start is not None:
        prev_runs = ForwardingRun.objects.filter(
            created_at__gte=previous_start, created_at__lt=since_datetime,
        ).exclude(status=ForwardingRun.Status.QUEUED)
        prev_total = prev_runs.count()
        if prev_total > 0:
            prev_successful = prev_runs.filter(
                status=ForwardingRun.Status.COMPLETED
            ).count()
            prev_success_rate = prev_successful / prev_total * 100

    avg_runtime = _avg_runtime_for_runs(
        (recent_runs, ForwardingRun.Status.COMPLETED),
    )
    return {
        'total_configs': total_configs,
        'configs': configs,
        'last_24h_runs': total_runs,
        'success_rate': round(success_rate, 1),
        'success_trend': _get_success_trend(success_rate, prev_success_rate),
        'successful_count': successful_runs,
        'failed_count': failed_runs,
        'status': status,
        'avg_runtime': readable_timedelta(avg_runtime, short=True),
    }
