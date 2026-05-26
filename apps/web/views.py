from datetime import timedelta

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
    last_24h = now - timedelta(hours=24)
    export_stats = _get_export_statistics(last_24h)
    refresh_stats = _get_refresh_statistics(last_24h)
    forwarding_stats = _get_forwarding_statistics(last_24h)
    context = {
        'active_tab': 'dashboard',
        'export_stats': export_stats,
        'refresh_stats': refresh_stats,
        'forwarding_stats': forwarding_stats,
    }
    return render(request, 'web/dashboard.html', context)
