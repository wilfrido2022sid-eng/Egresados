"""Modelos para bitácoras de acompañamiento."""

from django.conf import settings
from django.db import models

from app_egresados.models import Egresado


class Acompanamiento(models.Model):
    """Nota de seguimiento asociada a un perfil y su autor."""

    class Medio(models.TextChoices):
        LLAMADA = "llamada", "Llamada"
        CORREO = "correo", "Correo electrónico"
        PRESENCIAL = "presencial", "Presencial"
        OTRO = "otro", "Otro"

    graduate = models.ForeignKey(
        Egresado, on_delete=models.PROTECT, related_name="acompanamientos"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="acompanamientos_creados"
    )
    body = models.TextField(verbose_name="Nota de seguimiento")
    contacted_via = models.CharField(
        max_length=30, choices=Medio.choices, default=Medio.LLAMADA, verbose_name="Medio"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "acompañamiento"
        verbose_name_plural = "acompañamientos"

    def __str__(self):
        """Devuelve una referencia breve a la nota."""
        return f"Acompañamiento de {self.created_by} · {self.created_at:%Y-%m-%d}"
