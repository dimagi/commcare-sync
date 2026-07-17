from django import forms

from apps.db.models import Database
from apps.schedules.forms import ScheduleFormMixin

from .models import ForwardingConfig, ForwardingDestination


class CreateForwardingDestinationForm(forms.ModelForm):
    """Form for creating ForwardingDestination objects."""

    api_password = forms.CharField(
        widget=forms.PasswordInput(),
        required=False,
        help_text=ForwardingDestination.api_password_encrypted.field.help_text,
    )

    class Meta:
        model = ForwardingDestination
        fields = ('name', 'api_url', 'http_method', 'api_username')

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.cleaned_data['api_password']:
            instance.api_password = self.cleaned_data['api_password']
        if commit:
            instance.save()
        return instance


class EditForwardingDestinationForm(CreateForwardingDestinationForm):
    """Form for editing ForwardingDestination objects."""

    api_password = forms.CharField(
        widget=forms.PasswordInput(),
        required=False,
        help_text='Leave blank to keep the existing password.',
    )


class ForwardingConfigForm(ScheduleFormMixin, forms.ModelForm):
    """Form for creating and editing ForwardingConfig objects."""

    database = forms.ModelChoiceField(
        queryset=Database.objects.order_by('name')
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
