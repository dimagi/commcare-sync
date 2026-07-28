import mimetypes

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import HttpResponse, FileResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.users.models import CustomUser
from .forms import CustomUserChangeForm, FirstRunSetupForm, UploadAvatarForm


def first_run_setup(request):
    """Create the first superuser on a fresh install, then log them in.

    Defense in depth beyond ``FirstRunSetupMiddleware``: refuses (redirects
    to login) if a user already exists.

    This does *not* fully close the race between two concurrent setup
    submissions: under READ COMMITTED, both requests' ``exists()``
    re-check can see zero rows and both proceed. What it does guarantee:
    no unhandled crash, and the same-email case (by far the likely
    real-world collision — two submissions of *the* setup form) resolves
    to exactly one user, because the second insert raises
    ``IntegrityError`` on the unique email constraint, which is caught
    here and turned into a redirect to login. Two concurrent submissions
    with *different* emails can both still succeed and create two
    superusers; preventing that fully would need a DB-level constraint
    enforcing "at most one user before setup completes", which doesn't
    exist. That residual window is accepted as out of scope: a
    single-install first-run form isn't typically racing itself.
    """
    if CustomUser.objects.exists():
        return redirect('login')

    if request.method == 'POST':
        form = FirstRunSetupForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    if CustomUser.objects.exists():
                        # Lost the race to another request; don't create
                        # a second admin.
                        return redirect('login')
                    user = CustomUser.objects.create_superuser(
                        email=form.cleaned_data['email'],
                        password=form.cleaned_data['password1'],
                    )
            except IntegrityError:
                # A concurrent request beat us to creating a user with
                # this same email, between our re-check and our insert.
                return redirect('login')
            login(request, user)
            return redirect(settings.LOGIN_REDIRECT_URL)
    else:
        form = FirstRunSetupForm()

    return render(request, 'users/setup.html', {'form': form})


@login_required
def profile(request):
    if request.method == 'POST':
        form = CustomUserChangeForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
    else:
        form = CustomUserChangeForm(instance=request.user)
    return render(
        request, 'users/profile.html', {'form': form, 'active_tab': 'profile'}
    )


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
