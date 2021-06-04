from django.urls import path
from django.views.generic import TemplateView

from . import views

app_name = 'web'
urlpatterns = [
    path('', views.home, name='home'),
    path('terms', TemplateView.as_view(template_name="web/terms.html"), name='terms'),
]
