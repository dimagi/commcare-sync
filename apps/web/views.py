from datetime import timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from apps.exports.models import ExportConfig, MultiProjectExportConfig, ExportRun, MultiProjectExportRun
from apps.forwarding.models import ForwardingConfig, ForwardingRun


def home(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect(reverse('web:dashboard'))
    else:
        return render(request, 'web/landing_page.html')


@login_required
def dashboard(request):
    """
    Main dashboard showing pipeline status overview.
    """
    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    export_stats = _get_export_statistics(last_24h)
    forwarding_stats = _get_forwarding_statistics(last_24h)
    context = {
        'active_tab': 'dashboard',
        'export_stats': export_stats,
        'forwarding_stats': forwarding_stats,
    }
    return render(request, 'web/dashboard.html', context)


def _get_export_statistics(since_datetime):
    """Calculate export pipeline statistics."""
    export_configs = ExportConfig.objects.count()
    multi_export_configs = MultiProjectExportConfig.objects.count()
    total_configs = export_configs + multi_export_configs

    recent_export_runs = ExportRun.objects.filter(
        created_at__gte=since_datetime
    ).exclude(status=ExportRun.QUEUED)

    recent_multi_runs = MultiProjectExportRun.objects.filter(
        created_at__gte=since_datetime
    ).exclude(status=MultiProjectExportRun.QUEUED)

    total_runs = recent_export_runs.count() + recent_multi_runs.count()
    successful_runs = (
        recent_export_runs.filter(status=ExportRun.COMPLETED).count() +
        recent_multi_runs.filter(status=MultiProjectExportRun.COMPLETED).count()
    )
    failed_runs = (
        recent_export_runs.filter(status=ExportRun.FAILED).count() +
        recent_multi_runs.filter(status=MultiProjectExportRun.FAILED).count()
    )

    success_rate = (successful_runs / total_runs * 100) if total_runs > 0 else 0

    recent_runs = list(  # Combines both exports and multi-project exports
        ExportRun.objects.select_related(
            'base_export_config',
            'base_export_config__project',
        )
        .exclude(status=ExportRun.QUEUED)
        .order_by('-created_at')[:10]
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
        'recent_runs': recent_runs,
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

    recent_run_list = list(
        ForwardingRun.objects.select_related(
            'forwarding_config',
            'forwarding_config__destination',
        )
        .exclude(status=ForwardingRun.Status.QUEUED)
        .order_by('-created_at')[:10]
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
        'recent_runs': recent_run_list,
        'last_24h_runs': total_runs,
        'success_rate': round(success_rate, 1),
        'successful_count': successful_runs,
        'failed_count': failed_runs,
        'status': status,
    }


@login_required
def admin_required(request):
    if request.user.is_superuser:
        return HttpResponseRedirect(request.GET.get('next', reverse('web:home')))
    else:
        return render(request, 'web/admin_required.html', {'dev_mode': settings.DEBUG})
