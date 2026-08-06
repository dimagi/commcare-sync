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
    readonly_fields = ['created_at', 'updated_at', 'next_run_at']

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
                    'schedule_enabled',
                    'schedule_type',
                    'first_run_date',
                    'first_run_time',
                    'timezone',
                    'interval_value',
                    'interval_unit',
                    'days_of_week',
                    'next_run_at',
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
        'config',
        'created_at',
        'started_at',
        'completed_at',
        'status',
    ]
    list_filter = [
        'config',
        'status',
        'created_at',
        'started_at',
    ]
    readonly_fields = [
        'config',
        'config_version',
        'status',
        'started_at',
        'completed_at',
        'triggered_from_ui',
        'triggered_by',
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
                    'config',
                    'config_version',
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
                    'triggered_by',
                )
            },
        ),
        ('Results', {'fields': ('log', 'view_results')}),
        (
            'Metadata',
            {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)},
        ),
    )
