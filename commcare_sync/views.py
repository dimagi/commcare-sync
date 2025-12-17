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
