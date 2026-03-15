from django.db.models.signals import post_save, pre_delete

from apps.schedules.signals import (
    create_or_update_periodic_task,
    delete_periodic_task,
)

from .models import ExportConfig, MultiProjectExportConfig

post_save.connect(create_or_update_periodic_task, sender=ExportConfig)
pre_delete.connect(delete_periodic_task, sender=ExportConfig)

post_save.connect(
    create_or_update_periodic_task, sender=MultiProjectExportConfig
)
pre_delete.connect(delete_periodic_task, sender=MultiProjectExportConfig)
