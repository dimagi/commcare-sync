from django import forms

from apps.commcare.models import (
    CommCareAccount,
    CommCareProject,
    CommCareServer,
)
from apps.db.models import Database

from .api_client import download_config_file
from .models import ExportConfig, MultiProjectExportConfig


class ConfigFileFetchMixin:
    """
    Mixin for forms that fetch DET config files from CommCare HQ API.
    """

    def clean(self):
        cleaned_data = super().clean()
        det_config_url = cleaned_data.get('det_config_url')

        # Require config selection for new exports, optional for edits
        if not self.instance.pk and not det_config_url:
            raise forms.ValidationError('Please select a config file.')

        if det_config_url:
            # Guard against SSRF: only allow URLs from registered CommCare servers.
            valid_prefixes = list(
                CommCareServer.objects.values_list('url', flat=True)
            )
            if not any(
                det_config_url.startswith(server_url.rstrip('/'))
                for server_url in valid_prefixes
            ):
                raise forms.ValidationError(
                    'Config file URL must be from a registered CommCare server.'
                )

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        det_config_url = self.cleaned_data.get('det_config_url')
        if det_config_url:
            account = self.cleaned_data['account']
            config_file = download_config_file(
                url=det_config_url,
                username=account.username,
                api_key=account.api_key,
            )
            instance.config_file = config_file

        if commit:
            instance.save()
        return instance


class ExportConfigForm(ConfigFileFetchMixin, forms.ModelForm):
    project = forms.ModelChoiceField(
        CommCareProject.objects.order_by('domain')
    )
    account = forms.ModelChoiceField(
        CommCareAccount.objects.order_by('username')
    )
    database = forms.ModelChoiceField(Database.objects.order_by('name'))
    extra_args = forms.CharField(widget=forms.TextInput, required=False)
    det_config_url = forms.CharField(
        widget=forms.HiddenInput(), required=False
    )

    class Meta:
        model = ExportConfig
        fields = (
            'name',
            'project',
            'account',
            'database',
            'is_paused',
            'time_between_runs',
            'batch_size',
            'extra_args',
        )


class MultiProjectExportConfigForm(ConfigFileFetchMixin, forms.ModelForm):
    projects = forms.ModelMultipleChoiceField(
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'checkbox'}),
        queryset=CommCareProject.objects.order_by('domain'),
    )
    det_config_url = forms.CharField(
        widget=forms.HiddenInput(), required=False
    )

    class Meta:
        model = MultiProjectExportConfig
        fields = (
            'name',
            'projects',
            'account',
            'database',
            'is_paused',
            'time_between_runs',
            'batch_size',
            'extra_args',
        )
