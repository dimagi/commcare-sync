from django import forms
from .models import CommCareProject


class CommCareProjectForm(forms.ModelForm):

    class Meta:
        model = CommCareProject
        fields = ('server', 'domain')
