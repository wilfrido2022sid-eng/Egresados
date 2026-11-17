"""Modelos para perfiles y trayectoria de egresados."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class EgresadoQuerySet(models.QuerySet):
    """Impide saltarse la baja lógica mediante operaciones masivas."""

    def delete(self):
        """Bloquea el borrado físico por queryset."""
        raise ValidationError("Los perfiles no se eliminan físicamente; deben inactivarse.")


class Egresado(models.Model):
    """Perfil institucional asociado opcionalmente a una cuenta de acceso."""

    class Estado(models.TextChoices):
        ACTIVO = "Activo", "Activo"
        NO_CONTACTABLE = "No contactable", "No contactable"
        DESACTUALIZADO = "Desactualizado", "Desactualizado"
        INACTIVO = "Inactivo", "Inactivo"

    class EstadoAcademico(models.TextChoices):
        CERTIFICADO = "Certificado", "Certificado"
        DESERCION = "Deserción", "Deserción"
        RETIRO = "Retiro voluntario", "Retiro voluntario"
        LECTIVA = "Etapa lectiva", "Etapa lectiva"

    class SituacionLaboral(models.TextChoices):
        EMPLEADO = "Empleado", "Empleado"
        INDEPENDIENTE = "Independiente", "Independiente"
        DESEMPLEADO = "Desempleado", "Desempleado"
        EMPRENDEDOR = "Emprendedor", "Emprendedor"
        OTRO = "Otro", "Otro"

    class TipoContrato(models.TextChoices):
        INDEFINIDO = "Indefinido", "Indefinido"
        FIJO = "Término fijo", "Término fijo"
        PRESTACION = "Prestación de servicios", "Prestación de servicios"
        APRENDIZAJE = "Aprendizaje", "Aprendizaje"
        INDEPENDIENTE = "Independiente", "Independiente"
        OTRO = "Otro", "Otro"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="egresado",
        null=True,
        blank=True,
    )
    document_type = models.CharField(max_length=30, verbose_name="Tipo de documento")
    document_number = models.CharField(
        max_length=40, unique=True, verbose_name="Número de documento"
    )
    first_name = models.CharField(max_length=100, verbose_name="Nombres")
    last_name = models.CharField(max_length=100, verbose_name="Apellidos")
    email = models.EmailField(blank=True, verbose_name="Correo electrónico")
    phone = models.CharField(max_length=30, blank=True, verbose_name="Teléfono")
    address = models.CharField(max_length=200, blank=True, verbose_name="Dirección")
    municipality = models.CharField(max_length=100, blank=True, verbose_name="Municipio")
    program = models.CharField(max_length=160, verbose_name="Programa de formación")
    center = models.CharField(max_length=160, blank=True, verbose_name="Centro de formación")
    certified_on = models.DateField(verbose_name="Fecha de certificación")
    academic_status = models.CharField(
        max_length=30,
        choices=EstadoAcademico.choices,
        default=EstadoAcademico.CERTIFICADO,
        verbose_name="Estado académico",
    )
    employment_status = models.CharField(
        max_length=30,
        choices=SituacionLaboral.choices,
        default=SituacionLaboral.DESEMPLEADO,
        verbose_name="Situación laboral",
    )
    contract_type = models.CharField(
        max_length=40, choices=TipoContrato.choices, blank=True, verbose_name="Tipo de contrato"
    )
    company = models.CharField(max_length=160, blank=True, verbose_name="Empresa")
    unemployment_since = models.DateField(null=True, blank=True, verbose_name="Desempleado desde")
    vulnerability = models.BooleanField(default=False, verbose_name="Requiere acompañamiento")
    status = models.CharField(
        max_length=30,
        choices=Estado.choices,
        default=Estado.ACTIVO,
        verbose_name="Estado del perfil",
    )
    inactivity_reason = models.CharField(max_length=100, blank=True)
    privacy_accepted = models.BooleanField(default=False, verbose_name="Aceptó política")
    privacy_accepted_at = models.DateTimeField(null=True, blank=True)
    privacy_signature = models.CharField(max_length=200, blank=True)
    last_updated_at = models.DateField(default=timezone.localdate, verbose_name="Última actualización")
    created_at = models.DateTimeField(auto_now_add=True)
    objects = EgresadoQuerySet.as_manager()

    class Meta:
        ordering = ["last_name", "first_name"]
        verbose_name = "egresado"
        verbose_name_plural = "egresados"

    def __str__(self):
        """Devuelve el nombre y documento del egresado."""
        return f"{self.first_name} {self.last_name} · {self.document_number}"

    def clean(self):
        """Valida las reglas académicas de ingreso al registro."""
        if self.academic_status != self.EstadoAcademico.CERTIFICADO:
            raise ValidationError(
                {"academic_status": "Solo se pueden registrar egresados certificados."}
            )
        if not self.program.strip():
            raise ValidationError({"program": "El programa de formación es obligatorio."})

    def save(self, *args, **kwargs):
        """Evita el borrado físico y valida los requisitos del perfil."""
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *_args, **_kwargs):
        """Impide la eliminación física de perfiles institucionales."""
        raise ValidationError("Los perfiles no se eliminan físicamente; deben inactivarse.")


class Trayectoria(models.Model):
    """Registro de experiencia laboral, académica o de emprendimiento."""

    class Tipo(models.TextChoices):
        LABORAL = "laboral", "Experiencia laboral"
        ACADEMICA = "academica", "Formación académica"
        EMPRENDIMIENTO = "emprendimiento", "Emprendimiento"

    egresado = models.ForeignKey(
        Egresado, on_delete=models.PROTECT, related_name="trayectorias"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="trayectorias_creadas"
    )
    kind = models.CharField(max_length=20, choices=Tipo.choices, verbose_name="Tipo")
    title = models.CharField(max_length=160, verbose_name="Cargo, estudio o emprendimiento")
    organization = models.CharField(max_length=160, blank=True, verbose_name="Organización")
    description = models.TextField(blank=True, verbose_name="Descripción")
    started_on = models.DateField(null=True, blank=True, verbose_name="Fecha de inicio")
    ended_on = models.DateField(null=True, blank=True, verbose_name="Fecha de finalización")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-started_on", "-created_at"]
        verbose_name = "registro de trayectoria"
        verbose_name_plural = "registros de trayectoria"

    def __str__(self):
        """Devuelve el título del registro de trayectoria."""
        return self.title

    def delete(self, *args, **kwargs):
        """Restringe la eliminación al autor original del registro."""
        request_user = kwargs.pop("request_user", None)
        if request_user is None or request_user.pk != self.created_by_id:
            raise ValidationError("Solo el autor del registro puede eliminarlo.")
        return super().delete(*args, **kwargs)
