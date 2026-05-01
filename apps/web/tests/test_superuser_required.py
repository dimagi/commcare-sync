import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory
from unmagic import use

from apps.web.decorators import admin_required

User = get_user_model()


@admin_required
def _protected_view(request):
    return HttpResponse('OK', status=200)


@use('db')
class TestAdminRequired:
    def setup_method(self):
        self.factory = RequestFactory()

    def _get(self):
        return self.factory.get('/some-protected-path/')

    def test_unauthenticated_redirects_to_login(self):
        """Unauthenticated users are redirected to the login page with next= set."""
        request = self._get()
        request.user = AnonymousUser()
        response = _protected_view(request)
        assert response.status_code == 302
        assert response['Location'].startswith(settings.LOGIN_URL)
        assert '/some-protected-path/' in response['Location']

    def test_authenticated_regular_user_gets_403(self):
        """Authenticated users without superuser+staff get 403, not a redirect."""
        user = User.objects.create_user(username='regular', password='testpass')
        request = self._get()
        request.user = user
        with pytest.raises(PermissionDenied):
            _protected_view(request)

    def test_superuser_without_staff_gets_403(self):
        """is_superuser alone is not sufficient; is_staff is also required."""
        user = User.objects.create_user(
            username='super_only', password='testpass', is_superuser=True
        )
        request = self._get()
        request.user = user
        with pytest.raises(PermissionDenied):
            _protected_view(request)

    def test_active_superuser_and_staff_can_access(self):
        """Active superuser+staff users reach the view normally."""
        user = User.objects.create_user(
            username='admin', password='testpass', is_superuser=True, is_staff=True
        )
        request = self._get()
        request.user = user
        response = _protected_view(request)
        assert response.status_code == 200
