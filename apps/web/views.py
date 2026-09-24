from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.humanize.templatetags.humanize import naturaltime
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django_q.tasks import fetch

from apps.commcare.models import RunBaseModel


def home(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect(reverse('exports:home'))
    else:
        return render(request, 'web/landing_page.html')


def run_response(request, config, run):
    """Return the standard response for a run-trigger endpoint.

    When a run was started, HTMX callers get 204 + an HX-Trigger that fires
    an immediate table refresh, and direct callers (the detail-page JS) get
    JSON naming the run to poll.

    When ``run`` is None because ``config`` already had an active run, both
    get 409 and a message saying why nothing was started. HTMX callers get
    it as an alert, swapped out of band into the page's messages, with the
    table refresh that shows the active run. Direct callers get it as JSON.
    """
    if run is None:
        message = already_running_message(config)
        if request.headers.get('HX-Request'):
            messages.warning(request, message)
            response = render(
                request, 'web/components/messages_oob.html', status=409
            )
            response['HX-Trigger'] = 'runStarted'
            return response
        return JsonResponse(
            {'error': 'already_running', 'message': message}, status=409
        )
    if request.headers.get('HX-Request'):
        return HttpResponse(status=204, headers={'HX-Trigger': 'runStarted'})
    # The run button only reads `poll_url`. `run_id` is part of the
    # published contract for other callers -- scripts and tests that name
    # the run without parsing the URL -- so it stays.
    return JsonResponse({'run_id': run.id, 'poll_url': run.status_url})


def already_running_message(config):
    """Say why a manual run of ``config`` was not started."""
    run = config.runs.filter(
        status__in=RunBaseModel.ACTIVE_STATUSES
    ).order_by('-created_at').first()
    if run is None:
        # The active run finished between the check and now.
        return _('Not started: another run was in progress.')
    if run.status == RunBaseModel.Status.QUEUED:
        what = _('Not started: another run is already waiting to start.')
    else:
        what = _('Not started: another run is already running.')
    when = naturaltime(run.created_at)
    if run.triggered_by is not None:
        who = _('%(user)s requested it %(when)s.') % {
            'user': run.triggered_by.get_display_name(),
            'when': when,
        }
    else:
        who = _('It was requested %(when)s.') % {'when': when}
    return f'{what} {who}'


def run_status_response(model, run_id):
    """Return the poll payload for one run row.

    One helper for all four endpoints, so the contract cannot drift
    between them. ``status`` keys presentation, ``label`` carries the
    wording so the browser never enumerates statuses for text, and
    ``complete`` is what stops the poll.
    """
    run = get_object_or_404(model, id=run_id)
    response = JsonResponse({
        'status': run.status,
        'label': run.get_status_display(),
        'complete': run.is_terminal,
    })
    # A poll that reads a cached row would report a finished run as
    # still running, indefinitely.
    response['Cache-Control'] = 'no-store'
    return response


@login_required
def task_status(request, task_id):
    """Poll endpoint for background task state, used by run buttons.

    A task id is only found once the task has finished (django-q2 stores
    completed tasks in the ORM); anything not found is still pending.
    """
    task = fetch(task_id)
    if task is None:
        return JsonResponse({
            'complete': False,
            'success': None,
            'result': None,
        })
    return JsonResponse({
        'complete': True,
        'success': task.success,
        # Failed tasks carry a traceback string; only expose dicts.
        'result': task.result if isinstance(task.result, dict) else None,
    })
