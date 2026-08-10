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


def run_response(request, task_id=None):
    """Return the standard response for a run-trigger endpoint.

    HTMX callers get 204 + an HX-Trigger that fires an immediate table
    refresh. Direct callers (e.g. the detail-page JS) get the Django-Q task
    ID.
    """
    if request.headers.get('HX-Request'):
        return HttpResponse(status=204, headers={'HX-Trigger': 'runStarted'})
    return HttpResponse(task_id)


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
