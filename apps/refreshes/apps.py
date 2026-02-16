from django.apps import AppConfig


class RefreshesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.refreshes'
    verbose_name = 'Materialized View Refreshes'
