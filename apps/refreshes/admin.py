from django.contrib import admin
from reversion.admin import VersionAdmin

from . import models


@admin.register(models.RefreshConfig)
class RefreshConfigAdmin(VersionAdmin):
    list_display = [
        'name',
        'database',
        'created_at',
        'updated_at',
    ]
    list_filter = ['database', 'created_at', 'updated_at']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        (
            None,
            {
                'fields': (
                    'name',
                    'database',
                    'materialized_views',
                )
            },
        ),
        (
            'Scheduling',
            {
                'fields': (
                    'schedule_type',
                    'first_run_date',
                    'first_run_time',
                    'timezone',
                    'interval_value',
                    'interval_unit',
                    'days_of_week',
                )
            },
        ),
        (
            'Metadata',
            {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)},
        ),
    )


@admin.register(models.RefreshRun)
class RefreshRunAdmin(admin.ModelAdmin):
    list_display = [
        'refresh_config',
        'created_at',
        'started_at',
        'completed_at',
        'status',
    ]
    list_filter = [
        'refresh_config',
        'status',
        'created_at',
        'started_at',
    ]
    readonly_fields = [
        'refresh_config',
        'refresh_config_version',
        'status',
        'started_at',
        'completed_at',
        'triggered_from_ui',
        'triggering_user',
        'log',
        'view_results',
        'created_at',
        'updated_at',
    ]

    fieldsets = (
        (
            None,
            {
                'fields': (
                    'refresh_config',
                    'refresh_config_version',
                    'status',
                )
            },
        ),
        (
            'Execution',
            {
                'fields': (
                    'started_at',
                    'completed_at',
                    'triggered_from_ui',
                    'triggering_user',
                )
            },
        ),
        ('Results', {'fields': ('log', 'view_results')}),
        (
            'Metadata',
            {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)},
        ),
    )
