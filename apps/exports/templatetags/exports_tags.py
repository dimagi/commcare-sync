from django import template
from django.utils.safestring import mark_safe

from apps.exports.models import ExportRunBase


register = template.Library()


@register.filter()
def to_status_icon(export_status):
    text_modifiers = {
        ExportRunBase.COMPLETED: 'has-text-success',
        ExportRunBase.FAILED: 'has-text-danger',
        ExportRunBase.STARTED: 'has-text-primary',
        ExportRunBase.MULTIPLE: 'has-text-warning',
        ExportRunBase.QUEUED: 'has-text-grey',
        ExportRunBase.SKIPPED: 'has-text-grey',
    }
    icons = {
        ExportRunBase.COMPLETED: 'fa-check-circle',
        ExportRunBase.FAILED: 'fa-exclamation-circle',
        ExportRunBase.STARTED: 'fa-play-circle',
        ExportRunBase.MULTIPLE: 'fa-exclamation-triangle',
        ExportRunBase.QUEUED: 'fa-ellipsis-h',
        ExportRunBase.SKIPPED: 'fa-ban',
    }
    return mark_safe(f'<span class="icon {text_modifiers.get(export_status)}"><i title="{export_status}" class="fa {icons.get(export_status)}"></i></span>')  # noqa
