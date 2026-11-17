"""Administración de bitácoras de acompañamiento."""

from django.contrib import admin

from .models import Acompanamiento


@admin.register(Acompanamiento)
class AcompanamientoAdmin(admin.ModelAdmin):
    """Permite consultar notas de acompañamiento."""

    list_display = ("graduate", "contacted_via", "created_by", "created_at")
    list_filter = ("contacted_via", "created_at")
    search_fields = ("graduate__document_number", "graduate__last_name", "body")
    readonly_fields = ("created_by", "created_at", "updated_at")

    def has_delete_permission(self, _request, _obj=None):
        """Mantiene inmutable la bitácora institucional."""
        return False
