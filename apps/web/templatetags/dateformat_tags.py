from django import template
from django.utils.translation import gettext as _
from django.utils.translation import ngettext

register = template.Library()


@register.filter()
def readable_timedelta(timedelta_obj, short=False):
    """
    Convert a datetime.timedelta object into days, hours, minutes and
    seconds. If ``short`` is ``True``, use abbreviations "d", "h", "m"
    and "s".

    >>> from datetime import timedelta
    >>> readable_timedelta(timedelta(days=1, hours=2, minutes=3, seconds=4))
    '1 day 2 hours 3 minutes 4 seconds'
    >>> readable_timedelta(timedelta(seconds=90))
    '1 minute 30 seconds'
    >>> readable_timedelta(
    ...    timedelta(days=1, hours=2, minutes=3, seconds=4),
    ...    short=True,
    ... )
    '1d 2h 3m 4s'
    >>> readable_timedelta(timedelta(seconds=7204), short=True)
    '2h 4s'
    >>> readable_timedelta(timedelta(milliseconds=250))
    'less than a second'
    >>> readable_timedelta(timedelta(milliseconds=250), short=True)
    '<1s'
    >>> readable_timedelta(None)
    '---'
    """
    # adapted from https://stackoverflow.com/a/46928226/8207
    if not timedelta_obj:
        return '---'
    secs = int(timedelta_obj.total_seconds())
    strings = []
    if secs > 86400:  # 60sec * 60min * 24hrs
        days = secs // 86400
        if days:
            strings.append(
                f'{days}d'
                if short
                else ngettext('{} day', '{} days', days).format(days)
            )
        secs = secs - days * 86400
    if secs > 3600:
        hours = secs // 3600
        if hours:
            strings.append(
                f'{hours}h'
                if short
                else ngettext('{} hour', '{} hours', hours).format(hours)
            )
        secs = secs - hours * 3600
    if secs > 60:
        mins = secs // 60
        if mins:
            strings.append(
                f'{mins}m'
                if short
                else ngettext('{} minute', '{} minutes', mins).format(mins)
            )
        secs = secs - mins * 60
    if secs:
        strings.append(
            f'{secs}s'
            if short
            else ngettext('{} second', '{} seconds', secs).format(secs)
        )
    if not strings:
        # A duration under a second truncates to zero, leaving nothing to
        # report. Say it is brief rather than rendering an empty string.
        return '<1s' if short else _('less than a second')
    return ' '.join(strings)


@register.filter()
def readable_timedelta_short(timedelta_obj):
    return readable_timedelta(timedelta_obj, short=True)
