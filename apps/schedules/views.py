from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET


def run_response(request, task_id=None):
    """Return the standard response for a run-trigger endpoint.

    HTMX callers get 204 + an HX-Trigger that fires an immediate table
    refresh. Direct callers (e.g. the detail-page JS) get the Django-Q task
    ID.
    """
    if request.headers.get('HX-Request'):
        return HttpResponse(status=204, headers={'HX-Trigger': 'runStarted'})
    return HttpResponse(task_id)


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
