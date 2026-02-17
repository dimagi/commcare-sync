from django import template

register = template.Library()


@register.filter()
def readable_timedelta(timedeltaobj):
    """
    Convert a datetime.timedelta object into Days, Hours, Minutes, Seconds.

    >>> from datetime import timedelta
    >>> readable_timedelta(timedelta(days=1, hours=2, minutes=3, seconds=4))
    '1 days 2 hours 3 minutes 4 seconds'
    >>> readable_timedelta(timedelta(seconds=90))
    ' 1 minutes 30 seconds'
    >>> readable_timedelta(None)
    '---'
    """
    # stolen from https://stackoverflow.com/a/46928226/8207
    if not timedeltaobj:
        return '---'
    secs = timedeltaobj.total_seconds()
    timetot = ""
    if secs > 86400:  # 60sec * 60min * 24hrs
        days = secs // 86400
        timetot += "{} days".format(int(days))
        secs = secs - days * 86400

    if secs > 3600:
        hrs = secs // 3600
        timetot += " {} hours".format(int(hrs))
        secs = secs - hrs * 3600

    if secs > 60:
        mins = secs // 60
        timetot += " {} minutes".format(int(mins))
        secs = secs - mins * 60

    if secs > 0:
        timetot += " {} seconds".format(int(secs))
    return timetot
