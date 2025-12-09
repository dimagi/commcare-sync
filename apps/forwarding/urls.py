from django.urls import path

from . import views

app_name = 'forwarding'

urlpatterns = [
    path(
        'create/',
        views.create_forwarding_config,
        name='create_forwarding_config',
    ),
    path(
        'destinations/',
        views.destinations,
        name='destinations',
    ),
    path(
        'destinations/create/',
        views.create_destination,
        name='create_destination',
    ),
    path(
        'destinations/<int:destination_id>/edit/',
        views.edit_destination,
        name='edit_destination',
    ),
    # Placeholder for forwarding_details - will be implemented later
    path(
        '<int:forwarding_id>/',
        lambda request, forwarding_id: None,
        name='forwarding_details',
    ),
]
