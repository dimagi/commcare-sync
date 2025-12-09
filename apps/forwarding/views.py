from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext as _

from apps.schedules.forms import ScheduleForm

from .forms import ForwardingConfigForm


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
