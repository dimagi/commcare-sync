from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse


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
