from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _

from .forms import CommCareProjectForm, CommCareAccountForm
from .models import CommCareProject, CommCareAccount


@login_required
def home(request):
    projects = CommCareProject.objects.order_by('domain')
    accounts = CommCareAccount.objects.order_by('username')
    return render(request, 'commcare/commcare_home.html', {
        'active_tab': 'commcare',
        'projects': projects,
        'accounts': accounts,
    })


@login_required
def create_project(request):
    if request.method == 'POST':
        form = CommCareProjectForm(request.POST, request.FILES)
        if form.is_valid():
            project = form.save()
            messages.success(request, f'Project {project.domain} was successfully added.')
            return HttpResponseRedirect(reverse('commcare:home'))
    else:
        form = CommCareProjectForm()

    return render(request, 'commcare/create_project.html', {
        'active_tab': 'create_project',
        'form': form,
    })


@login_required
def edit_project(request, project_id):
    project = get_object_or_404(CommCareProject, id=project_id)
    if request.method == 'POST':
        form = CommCareProjectForm(request.POST, request.FILES, instance=project)
        if form.is_valid():
            project = form.save()
            messages.success(request, f'Project {project} was successfully saved.')
            return HttpResponseRedirect(reverse('commcare:home'))
    else:
        form = CommCareProjectForm(instance=project)

    return render(request, 'commcare/edit_project.html', {
        'active_tab': 'commcare',
        'form': form,
        'project': project,
    })



@login_required
def create_account(request):
    if request.method == 'POST':
        form = CommCareAccountForm(request.POST, request.FILES)
        if form.is_valid():
            account = form.save(commit=False)
            account.owner = request.user
            account.save()
            messages.success(request, f'Account {account.username} was successfully added.')
            return HttpResponseRedirect(reverse('commcare:home'))
    else:
        form = CommCareAccountForm()

    return render(request, 'commcare/create_account.html', {
        'active_tab': 'create_account',
        'form': form,
    })


@login_required
def edit_account(request, account_id):
    account = get_object_or_404(CommCareAccount, id=account_id)
    if not request.user == account.owner:
        messages.warning(request, _("Sorry, you don't have permission to edit that account"))
        return HttpResponseRedirect(reverse('commcare:home'))
    if request.method == 'POST':
        form = CommCareAccountForm(request.POST, request.FILES, instance=account)
        if form.is_valid():
            account = form.save()
            messages.success(request, _('Account {account} was successfully saved.').format(account=account))
            return HttpResponseRedirect(reverse('commcare:home'))
    else:
        form = CommCareAccountForm(instance=account)

    return render(request, 'commcare/edit_account.html', {
        'active_tab': 'commcare',
        'form': form,
        'account': account,
    })



