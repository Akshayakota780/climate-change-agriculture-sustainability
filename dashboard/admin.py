from django.contrib import admin
from .models import DatasetStatus, Observation

admin.site.register(Observation)
admin.site.register(DatasetStatus)
