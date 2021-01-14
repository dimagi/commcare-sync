import mimetypes

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, FileResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from apps.users.models import CustomUser
from .forms import CustomUserChangeForm, UploadAvatarForm


@login_required
def profile(request):
    if request.method == 'POST':
        form = CustomUserChangeForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
    else:
        form = CustomUserChangeForm(instance=request.user)
    return render(request, 'account/profile.html', {
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
