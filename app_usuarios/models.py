"""Modelos para la trazabilidad de aceptación de la política de datos."""

from django.db import models

from app_egresados.models import Egresado


class Consentimiento(models.Model):
    """Registro de aceptación o rechazo con trazabilidad de la sesión."""

    graduate = models.ForeignKey(
        Egresado, on_delete=models.PROTECT, related_name="consent_logs"
    )
    accepted = models.BooleanField()
    signature = models.CharField(max_length=200)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "registro de consentimiento"
        verbose_name_plural = "registros de consentimiento"
