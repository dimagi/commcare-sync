from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
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


@login_required
def task_status(request, task_id):
    """Poll endpoint for background task state, used by run buttons.

    A task id is only found once the task has finished (django-q2 stores
    completed tasks in the ORM); anything not found is still pending.
    """
    task = fetch(task_id)
    if task is None:
        return JsonResponse(
            {'complete': False, 'success': None, 'result': None}
        )
    return JsonResponse(
        {
            'complete': True,
            'success': task.success,
            # Failed tasks carry a traceback string; only expose dicts.
            'result': task.result if isinstance(task.result, dict) else None,
        }
    )


@login_required
@require_POST
def dismiss_failed_runs_banner(request):
    """Record the dismissal time so the banner stays hidden until a new failure.

    Stored in the session (not the DB): it is per-browser, disposable state,
    not something worth a migration for.
    """
    request.session['failed_runs_dismissed_at'] = timezone.now().isoformat()
    return HttpResponse(status=204)
