from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.utils.translation import gettext as _

from apps.schedules.forms import ScheduleForm
from commcare_sync.views import get_ui_page_size, get_hide_skipped_from_request

from .forms import (
    ForwardingConfigForm,
    CreateForwardingDestinationForm,
    EditForwardingDestinationForm,
)
from .models import ForwardingConfig, ForwardingDestination, ForwardingRun


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
        schedule_form = ScheduleForm(request.POST)

        if config_form.is_valid() and schedule_form.is_valid():
            # Save the schedule first
            schedule = schedule_form.save()

            # Save the forwarding config and associate the schedule
            config = config_form.save(commit=False)
            config.created_by = request.user
            config.schedule = schedule
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
        schedule_form = ScheduleForm()

    return render(
        request,
        'forwarding/create_forwarding.html',
        {
            'active_tab': 'create_forwarder',
            'config_form': config_form,
            'schedule_form': schedule_form,
        },
    )


@login_required
def edit_forwarding_config(request, forwarder_id):
    """Edit an existing forwarding configuration."""
    forwarder = get_object_or_404(ForwardingConfig, id=forwarder_id)

    if request.method == 'POST':
        config_form = ForwardingConfigForm(request.POST, instance=forwarder)
        schedule_form = ScheduleForm(
            request.POST,
            instance=forwarder.schedule if forwarder.schedule else None,
        )

        if config_form.is_valid() and schedule_form.is_valid():
            schedule = schedule_form.save()
            config = config_form.save(commit=False)
            config.schedule = schedule
            config.save()

            messages.success(
                request,
                _('Forwarding configuration "{}" was successfully updated.').format(
                    config.name
                ),
            )
            return HttpResponseRedirect(
                reverse('forwarding:forwarder_details', args=[config.id])
            )
    else:
        config_form = ForwardingConfigForm(instance=forwarder)
        schedule_form = ScheduleForm(
            instance=forwarder.schedule if forwarder.schedule else None
        )

    return render(
        request,
        'forwarding/edit_forwarding.html',
        {
            'active_tab': 'forwarders',
            'config_form': config_form,
            'schedule_form': schedule_form,
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
