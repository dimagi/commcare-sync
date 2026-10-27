import logging
import mimetypes

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, FileResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.users.models import CustomUser
from apps.users.setup import (
    ADMIN_EMAIL_VAR,
    ADMIN_PASSWORD_VAR,
    create_first_admin,
    may_set_up,
    needs_setup,
    setup_access,
)
from commcare_sync.consts import SetupAccess
from .forms import (
    CustomUserChangeForm,
    FirstRunSetupForm,
    UploadAvatarForm,
)

logger = logging.getLogger(__name__)


def first_run_setup(request):
    if not needs_setup():
        return redirect(settings.LOGIN_URL)
    if not may_set_up(request):
        access = setup_access()
        context = {
            'loopback_allowed': access == SetupAccess.LOOPBACK,
            'token_required': access == SetupAccess.TOKEN,
            'port': request.get_port(),
            'admin_email_var': ADMIN_EMAIL_VAR,
            'admin_password_var': ADMIN_PASSWORD_VAR,
        }
        return render(request, 'users/setup_remote.html', context, status=403)
    form = FirstRunSetupForm(request.POST or None)
    if form.is_valid():
        user = create_first_admin(
            form.cleaned_data['email'], form.cleaned_data['password1']
        )
        if user is None:
            return redirect(settings.LOGIN_URL)
        # Once per install, and worth a line in a log that keeps warnings.
        logger.warning('Created the admin user %s from the setup page', user)
        login(request, user)
        return redirect(settings.LOGIN_REDIRECT_URL)
    return render(request, 'users/setup.html', {'form': form})


@login_required
def profile(request):
    if request.method == 'POST':
        form = CustomUserChangeForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
    else:
        form = CustomUserChangeForm(instance=request.user)
    return render(request, 'users/profile.html', {
        'form': form,
        'active_tab': 'profile'
    })


@login_required
@require_POST
def upload_profile_image(request):
    user = request.user
    form = UploadAvatarForm(request.POST, request.FILES)
    if form.is_valid():
        user.avatar = request.FILES['avatar']
        user.save()
    return HttpResponse('Success!')


@login_required
def avatar(request, user_id):
    user = CustomUser.objects.get(id=user_id)
    if user.avatar:
        # copied / modified from django.views.static.serve
        content_type, encoding = mimetypes.guess_type(user.avatar.path)
        content_type = content_type or 'application/octet-stream'
        return FileResponse(user.avatar.open('rb'), content_type=content_type)
    else:
        # should this be a harder error?
        return HttpResponse('No avatar set')
