from django.apps import AppConfig


class ExportsConfig(AppConfig):
    name = 'apps.exports'
    label = 'exports'

    def ready(self):
        import apps.exports.signals  # noqa: F401
