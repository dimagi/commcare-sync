from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET


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

    HTMX callers get the same response as for a started run: the
    refreshed table shows the active run either way. Direct callers get
    409.
    """
    if request.headers.get('HX-Request'):
        return htmx_run_started_response()
    return JsonResponse({'error': 'already_running'}, status=409)


def htmx_run_started_response():
    """Return 204 + an HX-Trigger that fires an immediate table refresh."""
    return HttpResponse(status=204, headers={'HX-Trigger': 'refreshRuns'})


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
