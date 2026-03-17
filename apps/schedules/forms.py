from django import forms
from django.utils.translation import gettext_lazy as _


class ScheduleFormMixin:
    """
    Mixin for ModelForms whose model inherits from ScheduleMixin.

    Overrides days_of_week to use TypedMultipleChoiceField with checkboxes,
    and sets appropriate widgets for date/time fields.

    Must be listed before ModelForm in the MRO::

        class MyConfigForm(ScheduleFormMixin, forms.ModelForm):
            ...
    """

    SCHEDULE_FIELDS = (
        'schedule_type',
        'first_run_date',
        'first_run_time',
        'timezone',
        'interval_value',
        'interval_unit',
        'days_of_week',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['days_of_week'] = forms.TypedMultipleChoiceField(
            required=False,
            coerce=int,
            choices=[
                (0, _('Sunday')),
                (1, _('Monday')),
                (2, _('Tuesday')),
                (3, _('Wednesday')),
                (4, _('Thursday')),
                (5, _('Friday')),
                (6, _('Saturday')),
            ],
            widget=forms.CheckboxSelectMultiple(),
        )
        self.fields['first_run_date'].widget = forms.DateInput(
            attrs={'type': 'date'}
        )
        self.fields['first_run_time'].widget = forms.TimeInput(
            attrs={'type': 'time'}
        )
        if self.instance and self.instance.pk:
            self.initial['days_of_week'] = self.instance.days_of_week

    def clean_days_of_week(self):
        """Ensure days_of_week is always a list, not None."""
        days = self.cleaned_data.get('days_of_week')
        return days or []
