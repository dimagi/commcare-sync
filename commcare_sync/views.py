from django.conf import settings

from apps.commcare.models import RunBaseModel
from commcare_sync.consts import VALID_CONFIG_PAGE_SIZES


def get_ui_page_size(request):
    limit = settings.COMMCARE_SYNC_UI_PAGE_SIZE
    if 'limit' in request.GET:
        try:
            limit = int(request.GET['limit'])
        except ValueError:
            pass
    return limit


def get_hide_skipped_from_request(request):
    if 'hide_skipped' in request.GET:
        return request.GET['hide_skipped'] == 'y'
    return False


def get_config_page_size(request):
    if 'page_size' in request.GET:
        try:
            size = int(request.GET['page_size'])
            if size in VALID_CONFIG_PAGE_SIZES:
                return size
        except ValueError:
            pass
    return VALID_CONFIG_PAGE_SIZES[0]


def get_page_from_request(request):
    try:
        return max(int(request.GET.get('page', 1)), 1)
    except ValueError:
        return 1


# Per-run statuses available for filtering. RunBaseModel.Status is the shared base
# enum (queued/started/completed/failed/skipped); ExportRunBase additionally
# defines MULTIPLE — an aggregate for multi-project parent runs — which is
# deliberately not a per-run filter state, so deriving from the base excludes it.
_VALID_RUN_STATUSES = set(RunBaseModel.Status.values)


def get_run_statuses_from_request(request):
    """
    Returns a list of statuses to filter runs by.

    Show only runs whose status is in the list. (If the list is empty,
    show nothing.)
    """
    return [
        s for s in request.GET.getlist('status_filter')
        if s in _VALID_RUN_STATUSES
    ]
