from ..mixin import ScheduleMixin

# Schedule kwargs that make a config "non-paused": ScheduleMixin.is_paused
# is True unless the config has a schedule and schedule_enabled is True.
SCHEDULED = {
    'schedule_type': ScheduleMixin.ScheduleType.INTERVAL,
    'interval_value': 30,
    'interval_unit': ScheduleMixin.IntervalUnit.MINUTES,
}
