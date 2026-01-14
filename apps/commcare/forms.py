from django import forms
from .models import CommCareProject, CommCareAccount


class CommCareProjectForm(forms.ModelForm):

    class Meta:
        model = CommCareProject
        fields = ('server', 'domain')


class CreateCommCareAccountForm(forms.ModelForm):
    api_key = forms.CharField(
        widget=forms.PasswordInput,
        help_text=CommCareAccount.api_key_encrypted.field.help_text,
    )

    class Meta:
        model = CommCareAccount
        fields = ('server', 'username')

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.cleaned_data['api_key']:
            # Set api_key through the property setter (which encrypts it)
            instance.api_key = self.cleaned_data['api_key']
        if commit:
            instance.save()
        return instance


class EditCommCareAccountForm(CreateCommCareAccountForm):
    api_key = forms.CharField(
        widget=forms.PasswordInput,
        help_text=CommCareAccount.api_key_encrypted.field.help_text,
        required=False,
    )
