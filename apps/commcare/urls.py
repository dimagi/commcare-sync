from django.urls import include, path

from . import views

app_name = 'commcare'
urlpatterns = [
    path('', views.home, name='home'),
    path('projects/create/', views.create_project, name='create_project'),
    path(
        'projects/<int:project_id>/edit/',
        views.edit_project,
        name='edit_project',
    ),
    path('accounts/create/', views.create_account, name='create_account'),
    path(
        'accounts/<int:account_id>/edit/',
        views.edit_account,
        name='edit_account',
    ),
    # OAuth integration for configuration assistance
    path('oauth/', include('apps.commcare.oauth.urls')),
]
