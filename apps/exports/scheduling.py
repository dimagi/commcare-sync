import datetime
from django.utils import timezone


def export_is_scheduled_to_run(export_config, last_run):
    # first time running
    if not last_run:
        return True
    # last run still active
    if not last_run.completed_at:
        return False
    else:
        # run if last run completed before the scheduled time between runs
        next_scheduled_run_time = last_run.completed_at + datetime.timedelta(minutes=export_config.time_between_runs)
        return timezone.now() > next_scheduled_run_time
