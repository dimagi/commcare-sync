from django.db.models.signals import post_save, pre_delete

from apps.schedules.signals import (
    create_or_update_periodic_task,
    delete_periodic_task,
)

from .models import RefreshConfig

post_save.connect(create_or_update_periodic_task, sender=RefreshConfig)
pre_delete.connect(delete_periodic_task, sender=RefreshConfig)
