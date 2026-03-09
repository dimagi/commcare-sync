from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from commcare_sync.views import get_ui_page_size, get_hide_skipped_from_request

from .forms import (
    ForwardingConfigForm,
    CreateForwardingDestinationForm,
    EditForwardingDestinationForm,
)
from .models import ForwardingConfig, ForwardingDestination, ForwardingRun
from .tasks import run_forwarding_task


@login_required
def forwarders(request):
    """List all forwarding configurations."""
    fwd_configs = ForwardingConfig.objects.order_by('-updated_at')
    return render(
        request,
        'forwarding/forwarders.html',
        {
            'active_tab': 'forwarders',
            'forwarders': fwd_configs,
        },
    )


@login_required
def create_forwarding_config(request):
    """Create a new forwarding configuration."""

    if request.method == 'POST':
        config_form = ForwardingConfigForm(request.POST)

        if config_form.is_valid():
            with transaction.atomic():
                config = config_form.save(commit=False)
                config.created_by = request.user
                config.save()

            messages.success(
                request,
                _('Forwarding configuration "{}" was successfully created.').format(
                    config.name
                ),
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
                _('Forwarding configuration "{}" was successfully updated.').format(
                    forwarder.name
                ),
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
            _('Forwarding configuration "{}" was successfully deleted.').format(
                forwarder_name
            ),
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


@user_passes_test(lambda u: u.is_superuser, login_url='/admin-required')  # type: ignore[union-attr]
def create_destination(request):
    """Create a new forwarding destination."""
    if request.method == 'POST':
        form = CreateForwardingDestinationForm(request.POST)
        if form.is_valid():
            destination = form.save(commit=False)
            destination.owner = request.user
            destination.save()
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


@user_passes_test(lambda u: u.is_superuser)  # type: ignore[union-attr]
def edit_destination(request, destination_id):
    """Edit an existing forwarding destination."""
    destination = get_object_or_404(ForwardingDestination, id=destination_id)
    if request.method == 'POST':
        form = EditForwardingDestinationForm(request.POST, instance=destination)
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
    runs = forwarder.runs
    hide_skipped = get_hide_skipped_from_request(request)
    if hide_skipped:
        runs = runs.exclude(
            status__in=[ForwardingRun.Status.SKIPPED, ForwardingRun.Status.QUEUED]
        )

    return render(
        request,
        'forwarding/forwarder_details.html',
        {
            'active_tab': 'forwarders',
            'forwarder': forwarder,
            'runs': runs.order_by('-created_at')[: get_ui_page_size(request)],
            'hide_skipped': hide_skipped,
        },
    )


@login_required
def run_history_table(request, forwarder_id):
    """HTMX endpoint to refresh the run history table."""
    forwarder = get_object_or_404(ForwardingConfig, id=forwarder_id)
    runs = forwarder.runs
    hide_skipped = get_hide_skipped_from_request(request)

    if hide_skipped:
        runs = runs.exclude(
            status__in=[ForwardingRun.Status.SKIPPED, ForwardingRun.Status.QUEUED]
        )

    return render(
        request,
        'forwarding/partials/run_history_table.html',
        {
            'forwarder': forwarder,
            'runs': runs.order_by('-created_at')[: get_ui_page_size(request)],
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
        triggering_user=request.user,
    )

    result = run_forwarding_task.delay(forwarding_run.id)
    return HttpResponse(result.task_id)
