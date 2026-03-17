# Schedule fields are now provided by apps.schedules.mixin.ScheduleMixin.
# This app has no models of its own.
#
# NOTE: This refactor intentionally has no migration path and is intended for
# non-production environments only. If you have existing Schedule data, you
# must roll back migrations to zero before applying this change, e.g.:
#   python manage.py migrate schedules zero
#   python manage.py migrate forwarding zero
