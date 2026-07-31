from django.db.models.signals import post_save

from apps.schedules.signals import update_next_run

from .models import RefreshConfig

post_save.connect(update_next_run, sender=RefreshConfig)
