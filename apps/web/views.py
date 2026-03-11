from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from apps.web.stats import (
    _get_export_statistics,
    _get_forwarding_statistics,
    _get_refresh_statistics,
)


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
    period = settings.DASHBOARD_STATS_PERIOD
    current_start = now - period
    previous_start = current_start - period
    export_stats = _get_export_statistics(current_start, previous_start)
    refresh_stats = _get_refresh_statistics(current_start, previous_start)
    forwarding_stats = _get_forwarding_statistics(current_start, previous_start)
    context = {
        'active_tab': 'dashboard',
        'export_stats': export_stats,
        'refresh_stats': refresh_stats,
        'forwarding_stats': forwarding_stats,
    }
    return render(request, 'web/dashboard.html', context)


@login_required
def admin_required(request):
    if request.user.is_superuser:
        return HttpResponseRedirect(request.GET.get('next', reverse('web:home')))
    else:
        return render(request, 'web/admin_required.html', {'dev_mode': settings.DEBUG})
