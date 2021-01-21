from django.contrib import admin
from reversion.admin import VersionAdmin

from . import models


admin.site.register(models.ExportDatabase)


@admin.register(models.ExportConfig)
class ExportConfigAdmin(VersionAdmin):
    list_display = ['name', 'project', 'account', 'database', 'created_by', 'is_paused', 'created_at',
                    'updated_at']
    list_filter = ['project', 'database', 'is_paused', 'created_at', 'updated_at']


@admin.register(models.ExportRun)
class ExportRunAdmin(admin.ModelAdmin):
    list_display = ['base_export_config', 'created_at', 'started_at', 'completed_at', 'status']
    list_filter = ['base_export_config', 'created_at', 'started_at', 'completed_at', 'status']


@admin.register(models.MultiProjectExportConfig)
class MultiProjectExportConfigAdmin(VersionAdmin):
    list_display = ['name', 'account', 'database', 'created_by', 'is_paused', 'created_at', 'updated_at']
    list_filter = ['database', 'is_paused', 'created_at', 'updated_at']


@admin.register(models.MultiProjectExportRun)
class MultiProjectExportRunAdmin(admin.ModelAdmin):
    list_display = ['base_export_config', 'created_at', 'started_at', 'completed_at', 'status']
    list_filter = ['base_export_config', 'created_at', 'started_at', 'completed_at', 'status']


@admin.register(models.MultiProjectPartialExportRun)
class MultiProjectPartialExportRunAdmin(admin.ModelAdmin):
    list_display = ['parent_run', 'project', 'created_at', 'completed_at', 'status']
    list_filter = ['parent_run__base_export_config', 'created_at', 'completed_at', 'status']
