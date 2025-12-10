from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.utils.translation import gettext as _

from apps.schedules.forms import ScheduleForm

from .forms import (
    ForwardingConfigForm,
    CreateForwardingDestinationForm,
    EditForwardingDestinationForm,
)
from .models import ForwardingDestination


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
                reverse('forwarding:forwarding_details', args=[config.id])
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
