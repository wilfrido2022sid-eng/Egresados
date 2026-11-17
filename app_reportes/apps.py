"""Configuración del módulo de reportes y acompañamiento."""

from django.apps import AppConfig


class AppReportesConfig(AppConfig):
    """Registra tableros, alertas y bitácoras de acompañamiento."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "app_reportes"
    verbose_name = "Reportes y acompañamiento"
