"""
Generic signal handlers for models that inherit from ScheduleMixin.

They keep ``next_run_at`` in sync with the schedule fields. Registered
per-model in each app's signals.py via::

    from apps.schedules.signals import update_next_run
    post_save.connect(update_next_run, sender=MyConfig)
"""

import logging

from django.utils import timezone

from .mixin import SCHEDULE_FIELDS

logger = logging.getLogger(__name__)


def _schedule_changed(instance, update_fields):
    """
    True if this save actually touched a schedule-relevant field.

    ``update_fields`` (only set when the caller passes it to ``save()``) is
    a reliable "definitely unchanged" signal when it excludes every schedule
    field, since those columns then simply aren't written. Otherwise fall
    back to comparing against the snapshot ``ScheduleMixin.__init__`` took
    when the instance was loaded/constructed.
    """
    if update_fields is not None:
        return bool(SCHEDULE_FIELDS & set(update_fields))
    snapshot = getattr(instance, '_schedule_snapshot', None)
    if snapshot is None:
        # No snapshot to compare against (e.g. instance built without going
        # through ScheduleMixin.__init__) — recompute to be safe.
        return True
    if snapshot.keys() != SCHEDULE_FIELDS:
        # The instance was loaded with some schedule fields deferred, so
        # the snapshot can't rule a change out. Recompute to be safe.
        return True
    return any(
        snapshot[field] != getattr(instance, field)
        for field in SCHEDULE_FIELDS
    )


def update_next_run(
    sender, instance, created=False, update_fields=None, **kwargs
):
    """Recompute next_run_at when a scheduled config's schedule changes.

    A save that touches no schedule field must not defer a pending run
    (e.g. renaming a config must not push its next_run_at out), so such
    saves are skipped entirely. A newly created instance always gets its
    next_run_at computed.
    """
    if not created and not _schedule_changed(instance, update_fields):
        return

    if instance.has_schedule and instance.schedule_enabled:
        next_run = instance.compute_next_run(timezone.now())
    else:
        next_run = None
    # Use QuerySet.update() rather than instance.save() to avoid
    # triggering this post_save signal recursively.
    sender.objects.filter(pk=instance.pk).update(next_run_at=next_run)
    instance.next_run_at = next_run
    # Refresh the snapshot so a later save() on this same in-memory instance
    # is compared against the schedule state we just persisted, not the
    # state from whenever the instance was first loaded/constructed.
    instance.take_schedule_snapshot()
    logger.debug('Set next_run_at=%s for %s', next_run, instance)
