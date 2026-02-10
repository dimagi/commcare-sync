from django import forms

from apps.schedules.forms import ScheduleForm
from apps.exports.models import ExportDatabase

from .models import ForwardingConfig, ForwardingDestination


class CreateForwardingDestinationForm(forms.ModelForm):
    """Form for creating ForwardingDestination objects."""

    class Meta:
        model = ForwardingDestination
        fields = ('name', 'api_url', 'api_username', 'api_password')
        widgets = {
            'api_password': forms.PasswordInput(),
        }


class EditForwardingDestinationForm(forms.ModelForm):
    """Form for editing ForwardingDestination objects."""

    class Meta:
        model = ForwardingDestination
        fields = ('name', 'api_url', 'api_username')


class ForwardingConfigForm(forms.ModelForm):
    """Form for creating and editing ForwardingConfig objects."""

    database = forms.ModelChoiceField(
        queryset=ExportDatabase.objects.order_by('name')
    )
    destination = forms.ModelChoiceField(
        queryset=ForwardingDestination.objects.order_by('name')
    )

    class Meta:
        model = ForwardingConfig
        fields = ('name', 'database', 'destination', 'query', 'query_params')
        widgets = {
            'query': forms.Textarea(attrs={'rows': 2}),
            'query_params': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        # Pop schedule_data if provided (used for creating schedule)
        self.schedule_data = kwargs.pop('schedule_data', None)
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Create and associate schedule if schedule_data is provided
        if self.schedule_data and commit:
            schedule_form = ScheduleForm(self.schedule_data)
            if schedule_form.is_valid():
                schedule = schedule_form.save()
                instance.schedule = schedule

        if commit:
            instance.save()

        return instance
