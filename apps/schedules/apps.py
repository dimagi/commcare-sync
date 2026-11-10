from django.apps import AppConfig


class SchedulesConfig(AppConfig):
    name = 'apps.schedules'
    label = 'schedules'

    def ready(self):
        from . import checks  # noqa: F401  (registers the system checks)
