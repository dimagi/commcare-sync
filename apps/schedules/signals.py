"""
Generic signal handlers for models that inherit from ScheduleMixin.

They keep ``next_run_at`` in sync with the schedule fields. Registered
per-model in each app's signals.py via::

    from apps.schedules.signals import update_next_run
    post_save.connect(update_next_run, sender=MyConfig)
"""

import logging

from django.utils import timezone

logger = logging.getLogger(__name__)


def update_next_run(sender, instance, **kwargs):
    """Recompute next_run_at when a scheduled config is saved."""
    if instance.has_schedule and instance.schedule_enabled:
        next_run = instance.compute_next_run(timezone.now())
    else:
        next_run = None
    # Use QuerySet.update() rather than instance.save() to avoid
    # triggering this post_save signal recursively.
    sender.objects.filter(pk=instance.pk).update(next_run_at=next_run)
    instance.next_run_at = next_run
    logger.debug('Set next_run_at=%s for %s', next_run, instance)
