"""Configuración del módulo de encuestas."""

from django.apps import AppConfig


class AppEncuestasConfig(AppConfig):
    """Registra formularios de seguimiento y sus respuestas."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "app_encuestas"
    verbose_name = "Encuestas"
