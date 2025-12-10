from django.urls import path

from . import views

app_name = 'forwarding'

urlpatterns = [
    path(
        '',
        views.forwarders,
        name='forwarders',
    ),
    path(
        'create/',
        views.create_forwarding_config,
        name='create_forwarding_config',
    ),
    path(
        '<int:forwarder_id>/edit/',
        views.edit_forwarding_config,
        name='edit_forwarding_config',
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
    path(
        '<int:forwarder_id>/',
        views.forwarder_details,
        name='forwarder_details',
    ),
]
