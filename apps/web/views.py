from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse


def home(request):
    if request.user.is_authenticated:
        return HttpResponseRedirect(reverse('exports:home'))
    else:
        return render(request, 'web/landing_page.html')


@login_required
def admin_required(request):
    if request.user.is_superuser:
        return HttpResponseRedirect(request.GET.get('next', reverse('web:home')))
    else:
        return render(request, 'web/admin_required.html', {'dev_mode': settings.DEBUG})
