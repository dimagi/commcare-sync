from django.contrib import admin
from reversion.admin import VersionAdmin

from . import models


admin.site.register(models.ForwardingDestination)


@admin.register(models.ForwardingConfig)
class ForwardingConfigAdmin(VersionAdmin):
    list_display = [
        'name',
        'database',
        'destination',
        'created_at',
        'updated_at',
    ]
    list_filter = ['database', 'destination', 'created_at', 'updated_at']


@admin.register(models.ForwardingRun)
class ForwardingRunAdmin(admin.ModelAdmin):
    list_display = [
        'forwarding_config',
        'created_at',
        'started_at',
        'completed_at',
        'status',
    ]
    list_filter = [
        'forwarding_config',
        'created_at',
        'started_at',
        'completed_at',
        'status',
    ]

