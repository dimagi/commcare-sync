from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Schedule


class ScheduleForm(forms.ModelForm):
    """Form for creating and editing Schedule objects."""

    class Meta:
        model = Schedule
        fields = (
            'schedule_type',
            'first_run_date',
            'first_run_time',
            'timezone',
            'interval_value',
            'interval_unit',
            'days_of_week',
        )
        widgets = {
            'first_run_date': forms.DateInput(attrs={'type': 'date'}),
            'first_run_time': forms.TimeInput(attrs={'type': 'time'}),
            'days_of_week': forms.CheckboxSelectMultiple(
                choices=[
                    (0, _('Sunday')),
                    (1, _('Monday')),
                    (2, _('Tuesday')),
                    (3, _('Wednesday')),
                    (4, _('Thursday')),
                    (5, _('Friday')),
                    (6, _('Saturday')),
                ]
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add CSS classes for better styling
        for field_name, field in self.fields.items():
            if field_name != 'days_of_week':
                field.widget.attrs['class'] = 'input'
