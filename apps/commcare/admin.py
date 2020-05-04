from django.contrib import admin

from . import models


admin.site.register(models.CommCareServer)
admin.site.register(models.CommCareProject)
admin.site.register(models.CommCareAccount)
