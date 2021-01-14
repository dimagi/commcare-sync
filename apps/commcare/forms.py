from django import forms
from .models import CommCareProject, CommCareAccount


class CommCareProjectForm(forms.ModelForm):

    class Meta:
        model = CommCareProject
        fields = ('server', 'domain')


class CommCareAccountForm(forms.ModelForm):
    api_key = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = CommCareAccount
        fields = ('server', 'username', 'api_key')
