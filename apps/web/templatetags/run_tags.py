from django import template

from apps.commcare.models import RunBaseModel

register = template.Library()


@register.simple_tag
def run_status_choices():
    """
    The statuses of individual runs, as ``(value, label)`` pairs, for
    filtering.

    Uses ``RunBaseModel.Status`` rather than ``ExportRunBase.Status``
    because ``MULTIPLE`` is an aggregate for multi-project parent runs,
    not a state of an individual run. (See
    ``commcare_sync.views.get_run_statuses_from_request``.)
    """
    return RunBaseModel.Status.choices
