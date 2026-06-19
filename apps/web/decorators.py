from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseBadRequest


def admin_required(view_func):
    """Restrict a view to users with is_active, is_superuser, and is_staff.

    - Unauthenticated requests are redirected to settings.LOGIN_URL.
    - Authenticated requests that fail the test receive a 403 response.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not request.user.is_admin:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapper


def require_htmx(view_func):
    """Restrict a view to requests issued by HTMX.

    HTMX sets the ``HX-Request: true`` header on every request it makes, so
    its absence indicates a direct (non-HTMX) request — e.g. a bookmark or a
    manually-entered URL — which these partial-rendering endpoints do not
    support. Such requests receive a 400 response.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.headers.get('HX-Request') != 'true':
            return HttpResponseBadRequest('This endpoint must be called via HTMX.')
        return view_func(request, *args, **kwargs)

    return wrapper
