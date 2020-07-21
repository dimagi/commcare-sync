from django.contrib import admin

from . import models


admin.site.register(models.ExportDatabase)
admin.site.register(models.MultiProjectExportConfig)

@admin.register(models.ExportConfig)
class ExportConfigAdmin(admin.ModelAdmin):
    list_display = ['name', 'project', 'account', 'database', 'created_by', 'is_paused']
    list_filter = ['project', 'database', 'is_paused']

@admin.register(models.ExportRun)
class ExportRunAdmin(admin.ModelAdmin):
    list_display = ['export_config', 'created_at', 'started_at', 'completed_at', 'status']
    list_filter = ['export_config', 'created_at', 'started_at', 'completed_at', 'status']


@admin.register(models.MultiProjectExportRun)
class MultiProjectExportRunAdmin(admin.ModelAdmin):
    list_display = ['export_config', 'created_at', 'started_at', 'completed_at', 'status']
    list_filter = ['export_config', 'created_at', 'started_at', 'completed_at', 'status']

@admin.register(models.MultiProjectPartialExportRun)
class MultiProjectPartialExportRunAdmin(admin.ModelAdmin):
    list_display = ['export_config', 'project', 'created_at', 'completed_at', 'status']
    list_filter = ['export_config', 'project', 'created_at', 'completed_at', 'status']
