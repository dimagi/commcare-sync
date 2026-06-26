from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .forms import (
    CommCareProjectForm,
    CreateCommCareAccountForm,
    EditCommCareAccountForm,
)
from .models import CommCareAccount, CommCareProject


@login_required
def projects(request):
    projects = CommCareProject.objects.order_by('domain')
    return render(request, 'commcare/projects.html', {
        'active_tab': 'projects',
        'projects': projects,
    })


@login_required
def delete_project(request, project_id):
    project = get_object_or_404(CommCareProject, id=project_id)
    if project.is_in_use():
        messages.error(request, _(
            "Cannot delete '{}': It is used by one or more export "
            'configurations.'
        ).format(project.domain),)
        return HttpResponseRedirect(reverse('commcare:projects'))
    if request.method == 'POST':
        project.delete()
        messages.success(request, _(
            "Project '{}' was successfully deleted."
        ).format(project.domain))
        return HttpResponseRedirect(reverse('commcare:projects'))
    return render(request, 'commcare/delete_project.html', {
        'active_tab': 'projects',
        'project': project,
    })


@login_required
def create_project(request):
    if request.method == 'POST':
        form = CommCareProjectForm(request.POST, request.FILES)
        if form.is_valid():
            project = form.save()
            messages.success(request, _(
                "Project '{}' was successfully added."
            ).format(project.domain))
            return HttpResponseRedirect(reverse('commcare:projects'))
    else:
        form = CommCareProjectForm()

    return render(request, 'commcare/create_project.html', {
        'active_tab': 'projects',
        'form': form,
    })


@login_required
def edit_project(request, project_id):
    project = get_object_or_404(CommCareProject, id=project_id)
    if request.method == 'POST':
        form = CommCareProjectForm(
            request.POST,
            request.FILES,
            instance=project,
        )
        if form.is_valid():
            project = form.save()
            messages.success(request, _(
                "Project '{}' was successfully saved."
            ).format(project))
            return HttpResponseRedirect(reverse('commcare:projects'))
    else:
        form = CommCareProjectForm(instance=project)

    return render(request, 'commcare/edit_project.html', {
        'active_tab': 'projects',
        'form': form,
        'project': project,
    })


@login_required
def accounts(request):
    accounts = CommCareAccount.objects.order_by('username')
    return render(request, 'commcare/accounts.html', {
        'active_tab': 'accounts',
        'accounts': accounts,
    })


@login_required
def delete_account(request, account_id):
    account = get_object_or_404(CommCareAccount, id=account_id)
    if account.owner != request.user:
        raise PermissionDenied
    if account.is_in_use():
        messages.error(request, _(
            "Cannot delete '{}': It is used by one or more export "
            'configurations.'
        ).format(account.username))
        return HttpResponseRedirect(reverse('commcare:accounts'))
    if request.method == 'POST':
        account.delete()
        messages.success(request, _(
            "Account '{}' was successfully deleted."
        ).format(account.username))
        return HttpResponseRedirect(reverse('commcare:accounts'))
    return render(request, 'commcare/delete_account.html', {
        'active_tab': 'accounts',
        'account': account,
    })


@login_required
def create_account(request):
    if request.method == 'POST':
        form = CreateCommCareAccountForm(request.POST, request.FILES)
        if form.is_valid():
            account = form.save(commit=False)
            account.owner = request.user
            account.save()
            messages.success(request, _(
                "Account '{}' was successfully added."
            ).format(account.username))
            return HttpResponseRedirect(reverse('commcare:accounts'))
    else:
        form = CreateCommCareAccountForm()

    return render(request, 'commcare/create_account.html', {
        'active_tab': 'accounts',
        'form': form,
    })


@login_required
def edit_account(request, account_id):
    account = get_object_or_404(CommCareAccount, id=account_id)
    if not request.user == account.owner:
        messages.warning(request, _(
            "Sorry, you don't have permission to edit that account"
        ))
        return HttpResponseRedirect(reverse('commcare:accounts'))
    if request.method == 'POST':
        form = EditCommCareAccountForm(
            request.POST,
            request.FILES,
            instance=account,
        )
        if form.is_valid():
            account = form.save()
            messages.success(request, _(
                "Account '{}' was successfully saved."
            ).format(account))
            return HttpResponseRedirect(reverse('commcare:accounts'))
    else:
        form = EditCommCareAccountForm(instance=account)

    return render(request, 'commcare/edit_account.html', {
        'active_tab': 'accounts',
        'form': form,
        'account': account,
    })
