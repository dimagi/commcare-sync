from django import forms

from apps.commcare.models import CommCareProject, CommCareAccount
from .models import ExportConfig, MultiProjectExportConfig, ExportDatabase


class ExportConfigForm(forms.ModelForm):
    project = forms.ModelChoiceField(CommCareProject.objects.order_by('domain'))
    account = forms.ModelChoiceField(CommCareAccount.objects.order_by('username'))
    database = forms.ModelChoiceField(ExportDatabase.objects.order_by('name'))
    extra_args = forms.CharField(widget=forms.TextInput, required=False)

    class Meta:
        model = ExportConfig
        fields = ('name', 'project', 'account', 'database', 'is_paused', 'time_between_runs',
                  'config_file', 'batch_size', 'extra_args')


class MultiProjectExportConfigForm(forms.ModelForm):

    class Meta:
        model = MultiProjectExportConfig
        fields = ('name', 'projects', 'account', 'database', 'is_paused', 'time_between_runs',
                  'config_file', 'batch_size', 'extra_args')

    projects = forms.ModelMultipleChoiceField(
        widget=forms.CheckboxSelectMultiple(attrs={"class": "checkbox"}),
        queryset=CommCareProject.objects.order_by('domain'),
    )


class CreateExportDatabaseForm(forms.ModelForm):

    class Meta:
        model = ExportDatabase
        fields = ('name', 'connection_string')


class EditExportDatabaseForm(forms.ModelForm):

    class Meta:
        model = ExportDatabase
        fields = ('name',)
