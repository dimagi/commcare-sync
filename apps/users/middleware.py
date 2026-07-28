from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import redirect
from django.urls import reverse


class FirstRunSetupMiddleware:
    """Force every request to the first-run setup page until an admin exists.

    A freshly installed instance has no users and no way to log in, so
    every request (other than the setup page itself and static/media
    files, which the setup page needs to render) is redirected to
    ``/setup/``. Once an admin has been created, the reverse applies:
    visiting the setup page redirects to the login page instead of
    letting a second admin be created there.

    This runs an ``exists()`` query per request. That's cheap and correct
    at this scale; a module-level cache would go stale the moment setup
    completes; we don't cache.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._is_exempt_path(request.path):
            return self.get_response(request)

        no_users = not get_user_model().objects.exists()
        setup_path = reverse('setup')

        if request.path == setup_path:
            if not no_users:
                return redirect(settings.LOGIN_URL)
        elif no_users:
            return redirect(setup_path)

        return self.get_response(request)

    @staticmethod
    def _is_exempt_path(path):
        return path.startswith((settings.STATIC_URL, settings.MEDIA_URL))
