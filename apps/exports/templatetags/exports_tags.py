from django import template
from django.utils.safestring import mark_safe

from apps.exports.models import ExportRunBase


register = template.Library()


@register.filter()
def to_status_icon(export_status):
    """
    Convert export status to an HTML icon with appropriate styling.

    >>> 'fa-circle-check' in to_status_icon('completed')
    True
    >>> 'text-success' in to_status_icon('completed')
    True
    """
    tone = ExportRunBase.STATUS_TONES.get(export_status, 'secondary')
    icons = {
        ExportRunBase.Status.COMPLETED: 'fa-circle-check',
        ExportRunBase.Status.FAILED: 'fa-circle-exclamation',
        ExportRunBase.Status.STARTED: 'fa-circle-play',
        ExportRunBase.Status.MULTIPLE: 'fa-triangle-exclamation',
        ExportRunBase.Status.QUEUED: 'fa-ellipsis',
        ExportRunBase.Status.SKIPPED: 'fa-ban',
        ExportRunBase.Status.TIMEOUT: 'fa-clock',
    }
    return mark_safe(
        '<i'
        f'  title="{export_status}"'
        f'  class="fa-solid {icons.get(export_status)} text-{tone}"'
        '></i>'
    )
