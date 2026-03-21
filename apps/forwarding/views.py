import hashlib

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, Paginator
from django.db import transaction
from django.db.models import Prefetch
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from apps.web.decorators import admin_required
from apps.web.stats import (
    _get_export_statistics,
    _get_forwarding_statistics,
    _get_refresh_statistics,
)
from apps.web.templatetags.dateformat_tags import readable_timedelta
from commcare_sync.views import (
    get_config_page_size,
    get_page_from_request,
    get_run_statuses_from_request,
)

from .forms import (
    CreateForwardingDestinationForm,
    EditForwardingDestinationForm,
    ForwardingConfigForm,
)
from .models import ForwardingConfig, ForwardingDestination, ForwardingRun
from .tasks import run_forwarding_task


def _compute_forwarding_etag(configs_list):
    parts = []
    for config in configs_list:
        all_runs = getattr(config, '_all_runs', None)
        run = (
            all_runs[0]
            if all_runs
            else config.runs.order_by('-created_at').first()
        )
        if run:
            parts.append(f'{run.id}:{run.created_at.isoformat()}:{run.status}')
        else:
            parts.append(f'config:{config.id}:no-runs')
    return hashlib.md5('|'.join(parts).encode()).hexdigest()


@login_required
def forwarders(request):
    """List all forwarding configurations."""
    now = timezone.now()
    period = settings.DASHBOARD_STATS_PERIOD
    current_start = now - period
    previous_start = current_start - period

    page_size = get_config_page_size(request)
    page_num = get_page_from_request(request)
    configs_qs = ForwardingConfig.objects.order_by(
        '-updated_at'
    ).prefetch_related(
        Prefetch(
            'runs',
            queryset=ForwardingRun.objects.order_by('-created_at'),
            to_attr='_all_runs',
        )
    )
    paginator = Paginator(configs_qs, page_size)
    try:
        page_obj = paginator.page(page_num)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    etag = _compute_forwarding_etag(page_obj.object_list)

    return render(
        request,
        'forwarding/forwarders.html',
        {
            'active_tab': 'forwarders',
            'configs': page_obj,
            'page_size': page_size,
            'page_sizes': [10, 20, 50],
            'etag': etag,
            'stats_period': readable_timedelta(period, short=True),
            'export_stats': _get_export_statistics(
                current_start, previous_start
            ),
            'refresh_stats': _get_refresh_statistics(
                current_start, previous_start
            ),
            'forwarding_stats': _get_forwarding_statistics(
                current_start, previous_start
            ),
        },
    )


@login_required
@require_GET
def config_table(request):
    """HTMX endpoint: paginated + ETag-guarded forwarding config table partial."""
    page_size = get_config_page_size(request)
    page_num = get_page_from_request(request)
    configs_qs = ForwardingConfig.objects.order_by(
        '-updated_at'
    ).prefetch_related(
        Prefetch(
            'runs',
            queryset=ForwardingRun.objects.order_by('-created_at'),
            to_attr='_all_runs',
        )
    )
    paginator = Paginator(configs_qs, page_size)
    try:
        page_obj = paginator.page(page_num)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    etag = _compute_forwarding_etag(page_obj.object_list)
    if request.GET.get('etag') == etag:
        response = HttpResponse()
        response['HX-Reswap'] = 'none'
        return response

    return render(
        request,
        'forwarding/partials/config_table.html',
        {
            'configs': page_obj,
            'page_size': page_size,
            'page_sizes': [10, 20, 50],
            'etag': etag,
        },
    )


@login_required
@require_GET
def run_log(request, run_id):
    """HTMX endpoint: log fragment for a ForwardingRun."""
    run = get_object_or_404(ForwardingRun, id=run_id)
    return render(request, 'forwarding/partials/run_log.html', {'run': run})


@login_required
def create_forwarding_config(request):
    """Create a new forwarding configuration."""

    if request.method == 'POST':
        config_form = ForwardingConfigForm(request.POST)

        if config_form.is_valid():
            with transaction.atomic():
                config = config_form.save()

            messages.success(
                request,
                _(
                    'Forwarding configuration "{}" was successfully created.'
                ).format(config.name),
            )
            return HttpResponseRedirect(
                reverse('forwarding:forwarder_details', args=[config.id])
            )
    else:
        config_form = ForwardingConfigForm()

    return render(
        request,
        'forwarding/create_forwarding.html',
        {
            'active_tab': 'create_forwarder',
            'config_form': config_form,
        },
    )


@login_required
def edit_forwarding_config(request, forwarder_id):
    """Edit an existing forwarding configuration."""
    forwarder = get_object_or_404(ForwardingConfig, id=forwarder_id)

    if request.method == 'POST':
        config_form = ForwardingConfigForm(request.POST, instance=forwarder)

        if config_form.is_valid():
            with transaction.atomic():
                config_form.save()

            messages.success(
                request,
                _(
                    'Forwarding configuration "{}" was successfully updated.'
                ).format(forwarder.name),
            )
            return HttpResponseRedirect(
                reverse('forwarding:forwarder_details', args=[forwarder.id])
            )
    else:
        config_form = ForwardingConfigForm(instance=forwarder)

    return render(
        request,
        'forwarding/edit_forwarding.html',
        {
            'active_tab': 'forwarders',
            'config_form': config_form,
            'forwarder': forwarder,
        },
    )


@login_required
def delete_forwarding_config(request, forwarder_id):
    """Delete an existing forwarding configuration."""
    forwarder = get_object_or_404(ForwardingConfig, id=forwarder_id)

    if request.method == 'POST':
        forwarder_name = forwarder.name
        forwarder.delete()
        messages.success(
            request,
            _(
                'Forwarding configuration "{}" was successfully deleted.'
            ).format(forwarder_name),
        )
        return HttpResponseRedirect(reverse('forwarding:forwarders'))

    return render(
        request,
        'forwarding/delete_forwarding.html',
        {
            'active_tab': 'forwarders',
            'forwarder': forwarder,
        },
    )


@login_required
def destinations(request):
    """List all forwarding destinations."""
    destinations = ForwardingDestination.objects.order_by('name')
    return render(
        request,
        'forwarding/destinations.html',
        {
            'active_tab': 'destinations',
            'destinations': destinations,
        },
    )


@admin_required
def create_destination(request):
    """Create a new forwarding destination."""
    if request.method == 'POST':
        form = CreateForwardingDestinationForm(request.POST)
        if form.is_valid():
            destination = form.save()
            messages.success(
                request,
                _('Destination "{}" was successfully created.').format(
                    destination.name
                ),
            )
            return HttpResponseRedirect(reverse('forwarding:destinations'))
    else:
        form = CreateForwardingDestinationForm()

    return render(
        request,
        'forwarding/create_destination.html',
        {
            'active_tab': 'destinations',
            'form': form,
        },
    )


@admin_required
def edit_destination(request, destination_id):
    """Edit an existing forwarding destination."""
    destination = get_object_or_404(ForwardingDestination, id=destination_id)
    if request.method == 'POST':
        form = EditForwardingDestinationForm(
            request.POST, instance=destination
        )
        if form.is_valid():
            destination = form.save()
            messages.success(
                request,
                _('Destination "{}" was successfully updated.').format(
                    destination.name
                ),
            )
            return HttpResponseRedirect(reverse('forwarding:destinations'))
    else:
        form = EditForwardingDestinationForm(instance=destination)

    return render(
        request,
        'forwarding/edit_destination.html',
        {
            'active_tab': 'destinations',
            'form': form,
            'destination': destination,
        },
    )


@login_required
def forwarder_details(request, forwarder_id):
    """Display details for a forwarding configuration."""
    forwarder = get_object_or_404(ForwardingConfig, id=forwarder_id)
    page_size = get_config_page_size(request)
    page_num = get_page_from_request(request)
    paginator = Paginator(forwarder.runs.order_by('-created_at'), page_size)
    try:
        page_obj = paginator.page(page_num)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    return render(
        request,
        'forwarding/forwarder_details.html',
        {
            'active_tab': 'forwarders',
            'forwarder': forwarder,
            'runs': page_obj,
            'run_history_url': reverse(
                'forwarding:run_history_table', args=[forwarder.id]
            ),
            'page_size': page_size,
            'page_sizes': [10, 20, 50],
        },
    )


@login_required
@require_GET
def run_history_table(request, forwarder_id):
    """HTMX endpoint to refresh the run history table."""
    forwarder = get_object_or_404(ForwardingConfig, id=forwarder_id)
    runs_qs = forwarder.runs.order_by('-created_at')
    statuses = get_run_statuses_from_request(request)
    if statuses is not None:
        runs_qs = runs_qs.filter(status__in=statuses)
    page_size = get_config_page_size(request)
    page_num = get_page_from_request(request)
    paginator = Paginator(runs_qs, page_size)
    try:
        page_obj = paginator.page(page_num)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    return render(
        request,
        'forwarding/partials/run_history_table.html',
        {
            'forwarder': forwarder,
            'runs': page_obj,
            'run_history_url': reverse(
                'forwarding:run_history_table', args=[forwarder.id]
            ),
            'page_size': page_size,
            'page_sizes': [10, 20, 50],
        },
    )


@login_required
@require_POST
def run_forwarding(request, forwarder_id):
    """Manually trigger a forwarding run."""
    forwarder = get_object_or_404(ForwardingConfig, id=forwarder_id)

    forwarding_run = ForwardingRun.objects.create(
        forwarding_config=forwarder,
        forwarding_config_version=forwarder.latest_version,
        triggered_from_ui=True,
        triggered_by=request.user,
    )

    result = run_forwarding_task.delay(forwarding_run.id)
    return HttpResponse(result.task_id)
