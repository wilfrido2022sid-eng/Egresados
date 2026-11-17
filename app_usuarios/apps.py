"""Configuración de la aplicación de acceso y usuarios."""

from django.apps import AppConfig


class AppUsuariosConfig(AppConfig):
    """Registra las funciones de autenticación y consentimiento."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "app_usuarios"
    verbose_name = "Usuarios y acceso"
