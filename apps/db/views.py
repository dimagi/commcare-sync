from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from apps.web.decorators import admin_required

from .forms import CreateDatabaseForm, EditDatabaseForm
from .models import Database


@login_required
def databases(request):
    databases = Database.objects.order_by('name')
    return render(
        request,
        'db/databases.html',
        {
            'active_tab': 'databases',
            'databases': databases,
        },
    )


@admin_required
def create_database(request):
    if request.method == 'POST':
        form = CreateDatabaseForm(request.POST, request.FILES)
        if form.is_valid():
            db = form.save()
            messages.success(
                request, f'Database {db.name} was successfully created.'
            )
            return HttpResponseRedirect(reverse('db:databases'))
    else:
        form = CreateDatabaseForm()

    return render(
        request,
        'db/create_database.html',
        {
            'active_tab': 'databases',
            'form': form,
        },
    )


@admin_required
def edit_database(request, database_id):
    db = get_object_or_404(Database, id=database_id)
    if request.method == 'POST':
        form = EditDatabaseForm(request.POST, instance=db)
        if form.is_valid():
            db = form.save()
            messages.success(
                request, f'Database "{db.name}" was successfully updated.'
            )
            return HttpResponseRedirect(reverse('db:databases'))
    else:
        form = EditDatabaseForm(instance=db)

    return render(
        request,
        'db/edit_database.html',
        {
            'active_tab': 'databases',
            'form': form,
        },
    )


@admin_required
def delete_database(request, database_id):
    db = get_object_or_404(Database, id=database_id)
    if db.is_in_use():
        messages.error(request, f'Cannot delete "{db.name}": It is currently in use.')
        return HttpResponseRedirect(reverse('db:databases'))
    if request.method == 'POST':
        db.delete()
        messages.success(
            request, f'Database "{db.name}" was successfully deleted.'
        )
        return HttpResponseRedirect(reverse('db:databases'))
    return render(
        request,
        'db/delete_database.html',
        {
            'active_tab': 'databases',
            'db': db,
        },
    )
