"""Administración de encuestas y sus respuestas."""

from django.contrib import admin

from .models import Aviso, Encuesta, Pregunta, Respuesta, RespuestaEncuesta


class PreguntaInline(admin.TabularInline):
    """Muestra preguntas dentro de la encuesta."""

    model = Pregunta
    extra = 0


@admin.register(Encuesta)
class EncuestaAdmin(admin.ModelAdmin):
    """Gestiona encuestas y su histórico."""

    list_display = ("title", "published", "target_program", "created_by", "created_at")
    list_filter = ("published", "target_program", "target_center")
    search_fields = ("title", "description")
    inlines = [PreguntaInline]


@admin.register(RespuestaEncuesta)
class RespuestaEncuestaAdmin(admin.ModelAdmin):
    """Consulta envíos sin exponer controles de eliminación."""

    list_display = ("survey", "graduate", "submitted_at")
    list_filter = ("survey", "submitted_at")
    readonly_fields = ("survey", "graduate", "submitted_at")

    def has_add_permission(self, _request):
        """No permite fabricar envíos desde admin."""
        return False

    def has_delete_permission(self, _request, _obj=None):
        """Conserva las respuestas para el histórico institucional."""
        return False


admin.site.register(Respuesta)


@admin.register(Aviso)
class AvisoAdmin(admin.ModelAdmin):
    """Administra avisos institucionales dirigidos a las cohortes."""

    list_display = ("title", "target_program", "target_center", "published", "created_at")
    list_filter = ("published", "target_program", "target_center")
    search_fields = ("title", "body")
