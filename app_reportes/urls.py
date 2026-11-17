"""Rutas de reportes, alertas y acompañamiento."""

from django.urls import path

from . import views

app_name = "app_reportes"

urlpatterns = [
    path("", views.dashboard_view, name="dashboard"),
    path("exportar/<str:file_format>/", views.report_export_view, name="export"),
    path("alertas/", views.alerts_list_view, name="alerts"),
    path("alertas/<int:pk>/", views.alert_detail_view, name="alert_detail"),
    path(
        "alertas/<int:pk>/acompanamiento/",
        views.accompaniment_create_view,
        name="accompaniment_create",
    ),
    path(
        "acompanamiento/<int:pk>/editar/",
        views.accompaniment_update_view,
        name="accompaniment_update",
    ),
]
