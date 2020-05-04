from django import forms
from .models import ExportConfig


class ExportConfigForm(forms.ModelForm):

    class Meta:
        model = ExportConfig
        fields = ('name', 'project', 'account', 'database', 'config_file')
