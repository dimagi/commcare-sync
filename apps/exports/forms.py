from django import forms
from .models import ExportConfig, MultiProjectExportConfig


class ExportConfigForm(forms.ModelForm):

    class Meta:
        model = ExportConfig
        fields = ('name', 'project', 'account', 'database', 'config_file')


class MultiProjectExportConfigForm(forms.ModelForm):

    class Meta:
        model = MultiProjectExportConfig
        fields = ('name', 'projects', 'account', 'database', 'config_file')
