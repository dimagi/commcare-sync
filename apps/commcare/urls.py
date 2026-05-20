from django.urls import path
from . import views


app_name = 'commcare'
urlpatterns = [
    path(r'', views.home, name='home'),
    path(r'projects/', views.projects, name='projects'),
    path(r'projects/create/', views.create_project, name='create_project'),
    path(r'projects/<int:project_id>/delete/', views.delete_project, name='delete_project'),
    path(r'projects/<int:project_id>/edit/', views.edit_project, name='edit_project'),
    path(r'accounts/', views.accounts, name='accounts'),
    path(r'accounts/create/', views.create_account, name='create_account'),
    path(r'accounts/<int:account_id>/edit/', views.edit_account, name='edit_account'),
]
