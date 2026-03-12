from django.conf import settings


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


_VALID_CONFIG_PAGE_SIZES = (10, 20, 50)


def get_config_page_size(request):
    if 'page_size' in request.GET:
        try:
            size = int(request.GET['page_size'])
            if size in _VALID_CONFIG_PAGE_SIZES:
                return size
        except ValueError:
            pass
    return _VALID_CONFIG_PAGE_SIZES[0]


def get_page_from_request(request):
    try:
        return max(int(request.GET.get('page', 1)), 1)
    except ValueError:
        return 1


# Note: 'multiple' (ExportRunBase.MULTIPLE) is intentionally excluded — it is
# an aggregate status for multi-project parent runs, not a per-run filter state.
_VALID_RUN_STATUSES = {'queued', 'started', 'completed', 'failed', 'skipped'}


def get_run_statuses_from_request(request):
    """Return list of statuses to filter runs by, or None if no filter active.

    Returns None  → filter not submitted; show all runs (initial page load).
    Returns list  → filter active; show only runs whose status is in the list
                    (list may be empty, which means show nothing).
    """
    if 'has_status_filter' not in request.GET:
        return None
    return [
        s for s in request.GET.getlist('status_filter')
        if s in _VALID_RUN_STATUSES
    ]
