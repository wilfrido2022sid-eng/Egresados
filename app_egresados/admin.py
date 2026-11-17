"""Administración de perfiles con protección contra borrado físico."""

from django.contrib import admin

from .models import Egresado, Trayectoria


@admin.register(Egresado)
class EgresadoAdmin(admin.ModelAdmin):
    """Ofrece consulta y corrección de datos solo a administradores."""

    list_display = (
        "document_number",
        "first_name",
        "last_name",
        "program",
        "status",
        "last_updated_at",
    )
    list_filter = ("status", "program", "center", "academic_status")
    search_fields = ("document_number", "first_name", "last_name", "email")
    readonly_fields = ("created_at", "privacy_accepted_at")
    actions = None

    def has_delete_permission(self, _request, _obj=None):
        """Deshabilita por completo la eliminación física desde admin."""
        return False


@admin.register(Trayectoria)
class TrayectoriaAdmin(admin.ModelAdmin):
    """Permite consultar los registros hijos desde el panel de administración."""

    list_display = ("title", "kind", "egresado", "created_by", "created_at")
    list_filter = ("kind",)
    search_fields = ("title", "egresado__document_number", "egresado__last_name")
    readonly_fields = ("created_at",)

    def has_delete_permission(self, _request, _obj=None):
        """Evita eliminar trayectorias por el panel administrativo."""
        return False
