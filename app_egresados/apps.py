"""Configuración del módulo de egresados."""

from django.apps import AppConfig


class AppEgresadosConfig(AppConfig):
    """Registra los perfiles y trayectoria de egresados."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "app_egresados"
    verbose_name = "Egresados"
