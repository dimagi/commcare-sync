from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.humanize.templatetags.humanize import naturaltime
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET

from apps.commcare.models import RunBaseModel


def run_started_response(request, run):
    """Return a run-trigger endpoint's response for a started ``run``.

    HTMX callers get ``htmx_run_started_response()``. Direct callers (the
    detail-page JS) get JSON naming the run to poll.
    """
    if request.headers.get('HX-Request'):
        return htmx_run_started_response()
    return JsonResponse({'poll_url': run.status_url})


def run_refused_response(request, active_run):
    """Return a run-trigger endpoint's response when ``active_run``
    prevented a new run from starting.

    Both HTMX and direct callers get 409 and a message saying why nothing
    was started. HTMX callers get it as an alert, swapped out of band into
    the page's messages, with the table refresh that shows the active run.
    Direct callers get it as JSON.
    """
    message = already_running_message(active_run)
    if request.headers.get('HX-Request'):
        messages.warning(request, message)
        response = render(
            request, 'web/components/messages_oob.html', status=409
        )
        response['HX-Trigger'] = 'refreshRuns'
        return response
    return JsonResponse(
        {'error': 'already_running', 'message': message}, status=409
    )


def htmx_run_started_response():
    """Return 204 + an HX-Trigger that fires an immediate table refresh."""
    return HttpResponse(status=204, headers={'HX-Trigger': 'refreshRuns'})


def already_running_message(active_run):
    """Say why a manual run was not started: ``active_run`` was active."""
    if active_run.status == RunBaseModel.Status.QUEUED:
        what = _('Not started: another run is already waiting to start.')
    else:
        what = _('Not started: another run is already running.')
    when = naturaltime(active_run.created_at)
    if active_run.triggered_by is not None:
        who = _('%(user)s requested it %(when)s.') % {
            'user': active_run.triggered_by.get_display_name(),
            'when': when,
        }
    else:
        who = _('It was requested %(when)s.') % {'when': when}
    return f'{what} {who}'


@login_required
@require_GET
def run_status(request, model, run_id):
    """Poll endpoint for the Run button watching a run of ``model``.

    One view for all run models. ``status`` identifies the outcome,
    ``label`` and ``tone`` carry its wording and color so the frontend
    doesn't have to enumerate statuses, and ``complete`` is what stops
    polling.
    """
    run = get_object_or_404(model, id=run_id)
    response = JsonResponse({
        'status': run.status,
        'label': run.get_status_display(),
        'tone': run.tone,
        'complete': run.is_terminal,
    })
    # A poll that reads a cached row would report a finished run as
    # still running, indefinitely.
    response['Cache-Control'] = 'no-store'
    return response
