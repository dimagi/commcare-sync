"""
URL patterns for CommCare OAuth integration.
"""

from django.urls import path

from apps.commcare.oauth import views

urlpatterns = [
    path('initiate/', views.oauth_initiate, name='oauth_initiate'),
    path('callback/', views.oauth_callback, name='oauth_callback'),
    path('disconnect/', views.oauth_disconnect, name='oauth_disconnect'),
]
