from django.urls import path
from . import views


app_name = 'exports'
urlpatterns = [
    path(r'', views.home, name='home'),
    path(r'create/', views.create_export_config, name='create_export_config'),
    path(r'details/<int:export_id>/', views.export_details, name='export_details'),
    path(r'api/run/<int:export_id>/', views.run_export, name='run_export'),
]
