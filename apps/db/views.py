from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from .forms import CreateDatabaseForm, EditDatabaseForm
from .models import Database


@login_required
def databases(request):
    databases = Database.objects.order_by('name')
    return render(request, 'db/databases.html', {
        'active_tab': 'databases',
        'databases': databases,
    })


@user_passes_test(lambda u: u.is_superuser, login_url='/admin-required')  # type: ignore[union-attr]
def create_database(request):
    if request.method == 'POST':
        form = CreateDatabaseForm(request.POST, request.FILES)
        if form.is_valid():
            db = form.save(commit=False)
            db.owner = request.user
            db.save()
            messages.success(request, f'Database {db.name} was successfully created.')
            return HttpResponseRedirect(reverse('db:databases'))
    else:
        form = CreateDatabaseForm()

    return render(request, 'db/create_database.html', {
        'active_tab': 'databases',
        'form': form,
    })


@user_passes_test(lambda u: u.is_superuser)  # type: ignore[union-attr]
def edit_database(request, database_id):
    db = get_object_or_404(Database, id=database_id)
    if request.method == 'POST':
        form = EditDatabaseForm(request.POST, instance=db)
        if form.is_valid():
            db = form.save()
            messages.success(request, f'Database "{db.name}" was successfully updated.')
            return HttpResponseRedirect(reverse('db:databases'))
    else:
        form = EditDatabaseForm(instance=db)

    return render(request, 'db/edit_database.html', {
        'active_tab': 'databases',
        'form': form,
    })


@login_required
def delete_database(request, database_id):
    db = get_object_or_404(Database, id=database_id)
    if request.method == 'POST':
        db.delete()
        messages.success(request, f'Database "{db.name}" was successfully deleted.')
        return HttpResponseRedirect(reverse('db:databases'))
    return render(request, 'db/delete_database.html', {
        'active_tab': 'databases',
        'db': db,
    })
