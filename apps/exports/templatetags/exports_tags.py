from django import template
from django.utils.safestring import mark_safe

from apps.exports.models import ExportRunBase


register = template.Library()


@register.filter()
def to_status_icon(export_status):
    text_modifiers = {
        ExportRunBase.COMPLETED: 'text-success',
        ExportRunBase.FAILED: 'text-danger',
        ExportRunBase.STARTED: 'text-primary',
        ExportRunBase.MULTIPLE: 'text-warning',
        ExportRunBase.QUEUED: 'text-muted',
        ExportRunBase.SKIPPED: 'text-muted',
    }
    icons = {
        ExportRunBase.COMPLETED: 'fa-check-circle',
        ExportRunBase.FAILED: 'fa-exclamation-circle',
        ExportRunBase.STARTED: 'fa-play-circle',
        ExportRunBase.MULTIPLE: 'fa-exclamation-triangle',
        ExportRunBase.QUEUED: 'fa-ellipsis-h',
        ExportRunBase.SKIPPED: 'fa-ban',
    }
    return mark_safe(
        '<i'
        f'  title="{export_status}"'
        f'  class="fa {icons.get(export_status)} {text_modifiers.get(export_status)}"'
        '></i>'
    )
