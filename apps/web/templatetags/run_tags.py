from django import template

from apps.commcare.models import RunBaseModel

register = template.Library()


@register.simple_tag
def run_status_choices():
    """The per-run statuses, as ``(value, label)`` pairs, for filtering.

    ``RunBaseModel.Status`` rather than ``ExportRunBase.Status``: MULTIPLE
    is an aggregate for multi-project parent runs, not a per-run state.
    (See ``get_run_statuses_from_request``.)
    """
    return RunBaseModel.Status.choices
