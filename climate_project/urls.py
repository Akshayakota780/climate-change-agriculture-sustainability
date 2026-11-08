from django.contrib import admin
from django.urls import path
from dashboard import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.home, name="home"),
    path("api/data", views.api_data, name="api_data"),
    path("api/metadata", views.metadata, name="metadata"),
    path("api/predict", views.predict, name="predict"),
    path("api/refresh", views.refresh, name="refresh"),
    path("api/download", views.download, name="download"),
]
