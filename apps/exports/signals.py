from django.db.models.signals import post_save

from apps.schedules.signals import update_next_run

from .models import ExportConfig, MultiProjectExportConfig

post_save.connect(update_next_run, sender=ExportConfig)
post_save.connect(update_next_run, sender=MultiProjectExportConfig)
