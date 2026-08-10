from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django_q.tasks import fetch


def home(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect(reverse('exports:home'))
    else:
        return render(request, 'web/landing_page.html')


def run_response(request, run):
    """Return the standard response for a run-trigger endpoint.

    HTMX callers get 204 + an HX-Trigger that fires an immediate table
    refresh, whether or not a run was started: the refreshed table shows
    the active run either way.

    Direct callers (the detail-page JS) get JSON naming the run to poll,
    or 409 when ``run`` is None because one was already active.
    """
    if request.headers.get('HX-Request'):
        return HttpResponse(status=204, headers={'HX-Trigger': 'runStarted'})
    if run is None:
        return JsonResponse({'error': 'already_running'}, status=409)
    # The run button only reads `poll_url`. `run_id` is part of the
    # published contract for other callers -- scripts and tests that name
    # the run without parsing the URL -- so it stays.
    return JsonResponse({'run_id': run.id, 'poll_url': run.status_url})


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
