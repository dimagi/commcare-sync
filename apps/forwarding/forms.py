from django import forms

from apps.db.models import Database as ExportDatabase
from apps.schedules.forms import ScheduleFormMixin

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


class ForwardingConfigForm(ScheduleFormMixin, forms.ModelForm):
    """Form for creating and editing ForwardingConfig objects."""

    database = forms.ModelChoiceField(
        queryset=ExportDatabase.objects.order_by('name')
    )
    destination = forms.ModelChoiceField(
        queryset=ForwardingDestination.objects.order_by('name')
    )

    class Meta:
        model = ForwardingConfig
        fields = (
            'name',
            'database',
            'destination',
            'query',
            'query_params',
            *ScheduleFormMixin.SCHEDULE_FIELDS,
        )
        widgets = {
            'query': forms.Textarea(attrs={'rows': 2}),
            'query_params': forms.Textarea(attrs={'rows': 3}),
        }
