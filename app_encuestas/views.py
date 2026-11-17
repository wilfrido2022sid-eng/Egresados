"""Vistas para diseñar, publicar y responder encuestas."""

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from app_egresados.models import Egresado
from app_usuarios.decorators import consent_required, role_required

from .models import Aviso, Encuesta, Pregunta, Respuesta, RespuestaEncuesta


class EncuestaCreateForm(forms.Form):
    """Captura los datos de una encuesta y su lista de preguntas."""

    title = forms.CharField(max_length=180, label="Título")
    description = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 3}), label="Descripción"
    )
    target_program = forms.CharField(
        max_length=160, required=False, label="Programa objetivo (opcional)"
    )
    target_center = forms.CharField(
        max_length=160, required=False, label="Centro objetivo (opcional)"
    )
    question_specs = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 8}),
        label="Preguntas",
        help_text=(
            "Una por línea: pregunta | tipo | obligatorio/opcional | opción1, opción2 | "
            "negativa1, negativa2. Las opciones negativas son opcionales. "
            "Tipos: text, textarea, number, radio o checkbox."
        ),
    )

    def clean_question_specs(self):
        """Valida la sintaxis de cada pregunta y sus opciones."""
        value = self.cleaned_data["question_specs"]
        lines = [line.strip() for line in value.splitlines() if line.strip()]
        if not lines:
            raise forms.ValidationError("La encuesta debe tener al menos una pregunta.")
        for line_number, line in enumerate(lines, start=1):
            parts = [part.strip() for part in line.split("|")]
            if len(parts) > 5:
                raise forms.ValidationError(
                    f"Línea {line_number}: cada pregunta admite máximo cinco campos."
                )
            if len(parts) < 2 or parts[1] not in dict(Pregunta.Tipo.choices):
                raise forms.ValidationError(
                    f"Línea {line_number}: use pregunta | text, textarea, number, radio o checkbox."
                )
            if not parts[0]:
                raise forms.ValidationError(f"Línea {line_number}: la pregunta no puede estar vacía.")
            if parts[1] in {"radio", "checkbox"} and (
                len(parts) < 4 or not [item.strip() for item in parts[3].split(",") if item.strip()]
            ):
                raise forms.ValidationError(
                    f"Línea {line_number}: indique opciones separadas por coma."
                )
            if len(parts) > 4:
                options = [item.strip() for item in parts[3].split(",") if item.strip()]
                negative_options = [item.strip() for item in parts[4].split(",") if item.strip()]
                if parts[1] not in {"radio", "checkbox"} or not set(negative_options).issubset(
                    set(options)
                ):
                    raise forms.ValidationError(
                        f"Línea {line_number}: las respuestas negativas deben ser opciones válidas."
                    )
            if len(parts) > 2 and parts[2] not in {"obligatorio", "opcional"}:
                raise forms.ValidationError(
                    f"Línea {line_number}: el tercer campo debe ser obligatorio u opcional."
                )
        return value


class AvisoCreateForm(forms.ModelForm):
    """Formulario para publicar un aviso institucional por audiencia."""

    class Meta:
        model = Aviso
        fields = ["title", "body", "target_program", "target_center"]
        widgets = {"body": forms.Textarea(attrs={"rows": 5})}


@role_required("Administrador", "funcionario")
def surveys_list_view(request):
    """Lista el histórico de encuestas para el equipo institucional."""
    surveys = Encuesta.objects.prefetch_related("questions")
    return render(request, "app_encuestas/list.html", {"surveys": surveys})


@role_required("Administrador", "funcionario")
def survey_create_view(request):
    """Crea una encuesta estructurada con las preguntas indicadas."""
    form = EncuestaCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            survey = Encuesta.objects.create(
                title=form.cleaned_data["title"],
                description=form.cleaned_data["description"],
                target_program=form.cleaned_data["target_program"],
                target_center=form.cleaned_data["target_center"],
                created_by=request.user,
            )
            for position, line in enumerate(
                line.strip()
                for line in form.cleaned_data["question_specs"].splitlines()
                if line.strip()
            ):
                parts = [part.strip() for part in line.split("|")]
                question_type = parts[1]
                options = (
                    [item.strip() for item in parts[3].split(",") if item.strip()]
                    if question_type in {"radio", "checkbox"}
                    else []
                )
                Pregunta.objects.create(
                    survey=survey,
                    prompt=parts[0],
                    question_type=question_type,
                    required=len(parts) < 3 or parts[2] == "obligatorio",
                    options=options,
                    negative_answers=(
                        [item.strip() for item in parts[4].split(",") if item.strip()]
                        if len(parts) > 4
                        else []
                    ),
                    position=position,
                )
        messages.success(request, "La encuesta fue creada como borrador.")
        return redirect("app_encuestas:list")
    return render(
        request, "app_encuestas/form.html", {"form": form, "title": "Diseñar encuesta"}
    )


@role_required("Administrador", "funcionario")
def survey_publish_view(request, pk):
    """Publica una encuesta para los perfiles que coincidan con su audiencia."""
    survey = get_object_or_404(Encuesta, pk=pk)
    if request.method == "POST":
        try:
            survey.publish()
        except ValidationError as error:
            messages.error(request, "; ".join(error.messages))
        else:
            messages.success(request, "La encuesta ya está disponible para su audiencia.")
    return redirect("app_encuestas:list")


@role_required("Administrador", "funcionario")
def notices_list_view(request):
    """Muestra el histórico de avisos institucionales."""
    notices = Aviso.objects.select_related("created_by")
    return render(request, "app_encuestas/notices.html", {"notices": notices})


@role_required("Administrador", "funcionario")
def notice_create_view(request):
    """Publica un aviso institucional para todos o parte de los egresados."""
    form = AvisoCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        notice = form.save(commit=False)
        notice.created_by = request.user
        notice.save()
        messages.success(request, "El aviso institucional fue publicado.")
        return redirect("app_encuestas:notices")
    return render(
        request, "app_encuestas/form.html", {"form": form, "title": "Publicar aviso"}
    )


@consent_required
@role_required("egresado")
def survey_answer_view(request, pk):
    """Guarda una única respuesta del egresado a una encuesta asignada."""
    graduate = get_object_or_404(Egresado, user=request.user)
    survey = get_object_or_404(Encuesta, pk=pk, published=True)
    if survey.target_program and survey.target_program != graduate.program:
        raise Http404
    if survey.target_center and survey.target_center != graduate.center:
        raise Http404
    if RespuestaEncuesta.objects.filter(survey=survey, graduate=graduate).exists():
        messages.info(request, "Ya enviaste tus respuestas a esta encuesta.")
        return redirect("app_usuarios:dashboard")
    questions = list(survey.questions.all())
    if request.method == "POST":
        values = {}
        errors = []
        for question in questions:
            key = f"pregunta_{question.pk}"
            value = request.POST.getlist(key) if question.question_type == "checkbox" else request.POST.get(key, "").strip()
            if question.required and not value:
                errors.append(f"Completa la pregunta: {question.prompt}")
                continue
            if question.question_type in {"radio", "checkbox"}:
                selected = value if isinstance(value, list) else ([value] if value else [])
                if any(option not in question.options for option in selected):
                    errors.append(f"Selecciona una opción válida: {question.prompt}")
                    continue
            if question.question_type == "number" and value:
                try:
                    float(value)
                except ValueError:
                    errors.append(f"Ingresa un número válido: {question.prompt}")
                    continue
            values[question.pk] = value
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            try:
                with transaction.atomic():
                    submission = RespuestaEncuesta.objects.create(
                        survey=survey, graduate=graduate
                    )
                    Respuesta.objects.bulk_create(
                        [
                            Respuesta(
                                submission=submission,
                                question=question,
                                value=values[question.pk],
                            )
                            for question in questions
                        ]
                    )
            except IntegrityError:
                messages.info(request, "La encuesta ya había sido enviada desde otra sesión.")
                return redirect("app_usuarios:dashboard")
            messages.success(request, "La encuesta fue enviada. Gracias por participar.")
            return redirect("app_usuarios:dashboard")
    return render(
        request,
        "app_encuestas/answer.html",
        {"survey": survey, "questions": questions},
    )


@consent_required
@role_required("egresado")
def survey_pending_view(request):
    """Lista encuestas publicadas aún no respondidas por el perfil."""
    graduate = get_object_or_404(Egresado, user=request.user)
    surveys = Encuesta.objects.filter(published=True).exclude(
        responses__graduate=graduate
    )
    if graduate.program:
        surveys = surveys.filter(target_program__in=["", graduate.program])
    if graduate.center:
        surveys = surveys.filter(target_center__in=["", graduate.center])
    else:
        surveys = surveys.filter(target_center="")
    return render(request, "app_encuestas/pending.html", {"surveys": surveys})
