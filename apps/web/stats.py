from apps.exports.models import (
    ExportConfig,
    ExportRun,
    MultiProjectExportConfig,
    MultiProjectExportRun,
)
from apps.forwarding.models import ForwardingConfig, ForwardingRun
from apps.refreshes.models import RefreshConfig, RefreshRun


def _get_export_statistics(since_datetime):
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
        recent_export_runs.filter(status=ExportRun.Status.COMPLETED).count() +
        recent_multi_runs.filter(status=MultiProjectExportRun.Status.COMPLETED).count()
    )
    failed_runs = (
        recent_export_runs.filter(status=ExportRun.Status.FAILED).count() +
        recent_multi_runs.filter(status=MultiProjectExportRun.Status.FAILED).count()
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

    return {
        'total_configs': total_configs,
        'configs': configs,
        'last_24h_runs': total_runs,
        'success_rate': round(success_rate, 1),
        'successful_count': successful_runs,
        'failed_count': failed_runs,
        'status': status,
    }


def _get_refresh_statistics(since_datetime):
    """Calculate refresh pipeline statistics."""
    total_configs = RefreshConfig.objects.count()

    recent_runs = RefreshRun.objects.filter(
        created_at__gte=since_datetime
    ).exclude(status=RefreshRun.Status.QUEUED)

    total_runs = recent_runs.count()
    successful_runs = recent_runs.filter(
        status=RefreshRun.Status.COMPLETED
    ).count()
    failed_runs = recent_runs.filter(status=RefreshRun.Status.FAILED).count()

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

    return {
        'total_configs': total_configs,
        'configs': configs,
        'last_24h_runs': total_runs,
        'success_rate': round(success_rate, 1),
        'successful_count': successful_runs,
        'failed_count': failed_runs,
        'status': status,
    }


def _get_forwarding_statistics(since_datetime):
    """Calculate forwarding pipeline statistics."""
    total_configs = ForwardingConfig.objects.count()

    recent_runs = ForwardingRun.objects.filter(
        created_at__gte=since_datetime
    ).exclude(status=ForwardingRun.Status.QUEUED)

    total_runs = recent_runs.count()
    successful_runs = recent_runs.filter(
        status=ForwardingRun.Status.COMPLETED
    ).count()
    failed_runs = recent_runs.filter(status=ForwardingRun.Status.FAILED).count()

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

    return {
        'total_configs': total_configs,
        'configs': configs,
        'last_24h_runs': total_runs,
        'success_rate': round(success_rate, 1),
        'successful_count': successful_runs,
        'failed_count': failed_runs,
        'status': status,
    }
