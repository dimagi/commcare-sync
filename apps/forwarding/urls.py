from django.urls import path

from . import views

app_name = 'forwarding'

urlpatterns = [
    path(
        'create/',
        views.create_forwarding_config,
        name='create_forwarding_config',
    ),
    # Placeholder for forwarding_details - will be implemented later
    path(
        '<int:forwarding_id>/',
        lambda request, forwarding_id: None,
        name='forwarding_details',
    ),
]
