from django import forms

from apps.commcare.models import CommCareProject, CommCareAccount
from .models import ExportConfig, MultiProjectExportConfig, ExportDatabase


class ExportConfigForm(forms.ModelForm):
    project = forms.ModelChoiceField(CommCareProject.objects.order_by('domain'))
    account = forms.ModelChoiceField(CommCareAccount.objects.order_by('username'))
    database = forms.ModelChoiceField(ExportDatabase.objects.order_by('name'))

    class Meta:
        model = ExportConfig
        fields = ('name', 'project', 'account', 'database', 'config_file')


class MultiProjectExportConfigForm(forms.ModelForm):

    class Meta:
        model = MultiProjectExportConfig
        fields = ('name', 'projects', 'account', 'database', 'config_file')
