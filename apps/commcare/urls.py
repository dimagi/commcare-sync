from django.urls import path
from . import views


app_name = 'commcare'
urlpatterns = [
    path(r'', views.home, name='home'),
    path(r'projects/create/', views.create_project, name='create_project'),

    path(r'view/<int:export_id>/edit/', views.edit_project, name='edit_project'),
]
