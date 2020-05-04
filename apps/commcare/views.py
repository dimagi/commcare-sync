from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.urls import reverse

from .forms import CommCareProjectForm
from .models import CommCareProject


@login_required
def home(request):
    projects = CommCareProject.objects.order_by('domain')
    return render(request, 'commcare/commcare_home.html', {
        'active_tab': 'commcare_home',
        'projects': projects,
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
    export = get_object_or_404(CommCareProject, id=project_id)
    if request.method == 'POST':
        form = CommCareProjectForm(request.POST, request.FILES, instance=export)
        if form.is_valid():
            export = form.save()
            messages.success(request, f'Export {export.name} was successfully saved.')
            return HttpResponseRedirect(reverse('exports:export_details', args=[export.id]))
    else:
        form = CommCareProjectForm(instance=export)

    return render(request, 'exports/edit_export.html', {
        'active_tab': 'exports',
        'form': form,
        'export': export,
    })
