from django.apps import AppConfig


class ForwardingConfig(AppConfig):
    name = 'apps.forwarding'
    verbose_name = 'Data Forwarding'

    def ready(self):
        import apps.forwarding.signals  # noqa: F401
