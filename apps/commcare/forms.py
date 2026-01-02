from django import forms
from .models import CommCareProject, CommCareAccount


class CommCareProjectForm(forms.ModelForm):

    class Meta:
        model = CommCareProject
        fields = ('server', 'domain')


class CommCareAccountForm(forms.ModelForm):
    api_key = forms.CharField(
        widget=forms.PasswordInput,
        help_text=CommCareAccount.api_key_encrypted.field.help_text,
    )

    class Meta:
        model = CommCareAccount
        fields = ('server', 'username')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate initial value for api_key from the instance's property
        if self.instance and self.instance.pk:
            self.fields['api_key'].initial = self.instance.api_key

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Set api_key through the property setter (which encrypts it)
        instance.api_key = self.cleaned_data['api_key']
        if commit:
            instance.save()
        return instance
