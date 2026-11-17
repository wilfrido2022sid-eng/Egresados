"""Comando diario para marcar perfiles sin actualización reciente."""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from app_egresados.models import Egresado


class Command(BaseCommand):
    """Marca como desactualizados los perfiles activos con más de 180 días."""

    help = "Actualiza el estado de egresados sin actividad durante más de 180 días."

    def handle(self, *_args, **_options):
        """Ejecuta la actualización de estado y reporta el resultado."""
        cutoff = timezone.localdate() - timedelta(days=180)
        updated = Egresado.objects.filter(
            status=Egresado.Estado.ACTIVO, last_updated_at__lt=cutoff
        ).update(status=Egresado.Estado.DESACTUALIZADO)
        self.stdout.write(self.style.SUCCESS(f"Perfiles desactualizados: {updated}"))
