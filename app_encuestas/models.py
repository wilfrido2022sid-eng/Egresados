"""Modelos para formularios de seguimiento institucional."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from app_egresados.models import Egresado


class Encuesta(models.Model):
    """Encuesta que puede dirigirse a una cohorte o programa."""

    title = models.CharField(max_length=180, verbose_name="Título")
    description = models.TextField(blank=True, verbose_name="Descripción")
    target_program = models.CharField(max_length=160, blank=True, verbose_name="Programa objetivo")
    target_center = models.CharField(max_length=160, blank=True, verbose_name="Centro objetivo")
    published = models.BooleanField(default=False, verbose_name="Publicada")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="encuestas_creadas"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "encuesta"
        verbose_name_plural = "encuestas"

    def __str__(self):
        """Devuelve el título de la encuesta."""
        return self.title

    def publish(self):
        """Publica una encuesta solo si contiene preguntas."""
        questions = list(self.questions.all())
        if not questions:
            raise ValidationError("Agregue al menos una pregunta antes de publicar.")
        for question in questions:
            question.full_clean()
        self.published = True
        self.published_at = timezone.now()
        self.save(update_fields=["published", "published_at"])


class Aviso(models.Model):
    """Comunicado institucional visible a los egresados seleccionados."""

    title = models.CharField(max_length=180, verbose_name="Título")
    body = models.TextField(verbose_name="Mensaje")
    target_program = models.CharField(max_length=160, blank=True, verbose_name="Programa objetivo")
    target_center = models.CharField(max_length=160, blank=True, verbose_name="Centro objetivo")
    published = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="avisos_creados"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "aviso institucional"
        verbose_name_plural = "avisos institucionales"

    def __str__(self):
        """Devuelve el título del aviso."""
        return self.title


class Pregunta(models.Model):
    """Pregunta ordenada que integra una encuesta."""

    class Tipo(models.TextChoices):
        TEXTO = "text", "Texto corto"
        PARRAFO = "textarea", "Párrafo"
        NUMERO = "number", "Número"
        OPCION = "radio", "Opción única"
        MULTIPLE = "checkbox", "Selección múltiple"

    survey = models.ForeignKey(Encuesta, on_delete=models.CASCADE, related_name="questions")
    prompt = models.CharField(max_length=500, verbose_name="Pregunta")
    question_type = models.CharField(max_length=12, choices=Tipo.choices, default=Tipo.TEXTO)
    options = models.JSONField(default=list, blank=True)
    negative_answers = models.JSONField(default=list, blank=True)
    required = models.BooleanField(default=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "pk"]

    def __str__(self):
        """Devuelve el texto de la pregunta."""
        return self.prompt

    def clean(self):
        """Exige opciones para preguntas de selección."""
        if not isinstance(self.options, list) or not isinstance(self.negative_answers, list):
            raise ValidationError("Las opciones de la pregunta deben ser listas.")
        if self.question_type in {self.Tipo.OPCION, self.Tipo.MULTIPLE} and not self.options:
            raise ValidationError({"options": "Esta pregunta necesita opciones."})
        if not set(self.negative_answers).issubset(set(self.options)):
            raise ValidationError(
                {"negative_answers": "Las respuestas negativas deben ser opciones de la pregunta."}
            )

    def save(self, *args, **kwargs):
        """Valida las opciones para que no se publiquen preguntas inválidas."""
        self.full_clean()
        return super().save(*args, **kwargs)


class RespuestaEncuesta(models.Model):
    """Envío único de un egresado para una encuesta publicada."""

    survey = models.ForeignKey(Encuesta, on_delete=models.PROTECT, related_name="responses")
    graduate = models.ForeignKey(
        Egresado, on_delete=models.PROTECT, related_name="survey_responses"
    )
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["survey", "graduate"], name="unique_survey_response_per_graduate"
            )
        ]
        ordering = ["-submitted_at"]


class Respuesta(models.Model):
    """Respuesta individual a una pregunta de una encuesta."""

    submission = models.ForeignKey(
        RespuestaEncuesta, on_delete=models.CASCADE, related_name="answers"
    )
    question = models.ForeignKey(Pregunta, on_delete=models.PROTECT, related_name="answers")
    value = models.JSONField(default=str, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["submission", "question"], name="unique_answer_per_question"
            )
        ]
