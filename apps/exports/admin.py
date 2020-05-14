from django.contrib import admin

from . import models


admin.site.register(models.ExportDatabase)
admin.site.register(models.ExportConfig)
admin.site.register(models.MultiProjectExportConfig)

@admin.register(models.ExportRun)
class ExportRunAdmin(admin.ModelAdmin):
    list_display = ['export_config', 'created_at', 'completed_at', 'status']
    list_filter = ['export_config', 'created_at', 'completed_at', 'status']
