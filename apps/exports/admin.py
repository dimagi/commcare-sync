from django.contrib import admin

from . import models


admin.site.register(models.CommCareServer)
admin.site.register(models.CommCareProject)
admin.site.register(models.CommCareAccount)
admin.site.register(models.ExportDatabase)
admin.site.register(models.ExportConfig)

@admin.register(models.ExportRun)
class ExportRunAdmin(admin.ModelAdmin):
    list_display = ['export_config', 'created_at', 'completed_at', 'status']
    list_filter = ['export_config', 'created_at', 'completed_at', 'status']
