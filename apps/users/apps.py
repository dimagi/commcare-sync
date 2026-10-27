from django.apps import AppConfig


class UserConfig(AppConfig):
    name = 'apps.users'
    label = 'users'

    def ready(self):
        from . import checks  # noqa: F401  (registers the system checks)
