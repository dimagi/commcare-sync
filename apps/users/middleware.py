from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

from apps.users.setup import needs_setup


class FirstRunSetupMiddleware:
    """
    A fresh install has no users and no way to sign in, so every request
    but static and media files goes to the setup page until a user
    exists. After that the setup page redirects to login, so it cannot
    create a second admin.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.setup_path = reverse('setup')

    def __call__(self, request):
        if request.path.startswith((settings.STATIC_URL, settings.MEDIA_URL)):
            return self.get_response(request)
        # One cheap query per request; a remembered answer would have
        # to be invalidated by every process that can delete users.
        if needs_setup():
            if request.path != self.setup_path:
                return redirect(self.setup_path)
        elif request.path == self.setup_path:
            return redirect(settings.LOGIN_URL)
        return self.get_response(request)
