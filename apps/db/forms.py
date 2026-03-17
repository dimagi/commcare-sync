from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Database


class CreateDatabaseForm(forms.ModelForm):
    connection_string = forms.CharField()

    class Meta:
        model = Database
        fields = ('name', 'connection_string')

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.cleaned_data['connection_string']:
            # Set connection_string through the property setter to encrypt it
            instance.connection_string = self.cleaned_data['connection_string']
        if commit:
            instance.save()
        return instance


class EditDatabaseForm(CreateDatabaseForm):
    connection_string = forms.CharField(
        required=False,
        help_text=(_(
            'Connection strings are not prepopulated in the form because they '
            'may contain passwords.'
        ))
    )
