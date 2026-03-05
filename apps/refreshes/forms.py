import json

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.db.models import Database
from apps.schedules.forms import ScheduleFormMixin

from .models import RefreshConfig


class RefreshConfigForm(ScheduleFormMixin, forms.ModelForm):

    database = forms.ModelChoiceField(
        queryset=Database.objects.order_by('name'),
        help_text=_('Select a PostgreSQL database connection'),
    )

    materialized_views = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
    )

    class Meta:
        model = RefreshConfig
        fields = (
            'name',
            'database',
            'materialized_views',
            'concurrently',
            *ScheduleFormMixin.SCHEDULE_FIELDS,
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        pg_ids = [
            db.pk for db in ExportDatabase.objects.all()
            if db.dialect == 'postgresql'
        ]
        self.fields['database'].queryset = ExportDatabase.objects.filter(
            pk__in=pg_ids
        ).order_by('name')

        if self.instance and self.instance.pk:
            views_json = json.dumps(self.instance.materialized_views)
            self.fields['materialized_views'].initial = views_json
            self.initial['materialized_views'] = views_json

    def clean_database(self):
        database = self.cleaned_data.get('database')
        if database:
            if not database.connection_string.startswith('postgresql://'):
                raise ValidationError(_(
                    'Only PostgreSQL databases are supported for materialized '
                    'view refreshes.'
                ))
        return database

    def clean_materialized_views(self):
        json_data = self.cleaned_data.get('materialized_views')
        if not json_data:
            raise ValidationError(_(
                'At least one materialized view must be selected.'
            ))

        try:
            views = json.loads(json_data)
        except json.JSONDecodeError:
            raise ValidationError(_('Invalid materialized views data.'))

        if not isinstance(views, list):
            raise ValidationError(_('Invalid materialized views data.'))

        if len(views) == 0:
            raise ValidationError(_(
                'At least one materialized view must be selected.'
            ))

        return views
