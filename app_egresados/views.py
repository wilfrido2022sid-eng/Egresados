"""Vistas para perfiles y trayectoria de egresados."""

import csv
import io
from datetime import date
from zipfile import BadZipFile

from django.contrib import messages
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from app_usuarios.decorators import consent_required, role_required

from .forms import (
    EgresadoAdminForm,
    EgresadoContactForm,
    EgresadoCreateForm,
    TrayectoriaForm,
)
from .models import Egresado, Trayectoria


def _read_import_rows(uploaded_file):
    """Lee CSV o Excel y entrega filas normalizadas para validación."""
    suffix = uploaded_file.name.rsplit(".", 1)[-1].lower()
    if uploaded_file.size > 5 * 1024 * 1024:
        raise ValueError("El archivo no puede superar 5 MB.")
    if suffix == "csv":
        try:
            content = uploaded_file.read().decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise ValueError("El CSV debe estar codificado en UTF-8.") from error
        return list(csv.DictReader(io.StringIO(content, newline="")))
    if suffix in {"xlsx", "xlsm"}:
        workbook = load_workbook(uploaded_file, read_only=True, data_only=True)
        sheet = workbook.active
        values = sheet.iter_rows(values_only=True)
        headers = [str(value or "").strip() for value in next(values, ())]
        rows = [dict(zip(headers, row)) for row in values]
        workbook.close()
        return rows
    raise ValueError("Formato no compatible. Cargue un archivo CSV o Excel (.xlsx).")


def _date_value(value):
    """Convierte una fecha de CSV o Excel en fecha ISO."""
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value).strip())


def _validate_import(rows):
    """Valida el lote completo y devuelve instancias y errores por fila."""
    required = {
        "document_type",
        "document_number",
        "first_name",
        "last_name",
        "program",
        "certified_on",
        "academic_status",
    }
    graduates = []
    errors = []
    seen_documents = set()
    for row_number, raw_row in enumerate(rows, start=2):
        row = {str(key or "").strip().lower(): value for key, value in raw_row.items()}
        missing = sorted(required - row.keys())
        if missing:
            return [], [f"Faltan columnas requeridas: {', '.join(missing)}."]
        try:
            values = {
                name: (str(row.get(name) or "").strip())
                for name in (
                    "document_type",
                    "document_number",
                    "first_name",
                    "last_name",
                    "email",
                    "phone",
                    "address",
                    "municipality",
                    "program",
                    "center",
                    "academic_status",
                    "employment_status",
                )
            }
            values["certified_on"] = _date_value(row["certified_on"])
            graduate = Egresado(**{key: value for key, value in values.items() if value})
            graduate.full_clean()
            if graduate.document_number in seen_documents:
                raise ValueError("El número de documento está duplicado en el archivo.")
            seen_documents.add(graduate.document_number)
            graduates.append(graduate)
        except (ValueError, TypeError) as error:
            errors.append(f"Fila {row_number}: {error}")
        except DjangoValidationError as error:
            detail = "; ".join(
                f"{field}: {', '.join(messages_list)}"
                for field, messages_list in getattr(error, "message_dict", {}).items()
            )
            errors.append(f"Fila {row_number}: {detail or error}")
    if not rows:
        errors.append("El archivo no contiene registros.")
    return graduates, errors


@role_required("Administrador", "funcionario")
def egresados_list_view(request):
    """Presenta los perfiles para su gestión institucional."""
    queryset = Egresado.objects.all()
    query = request.GET.get("q", "").strip()
    status = request.GET.get("estado", "").strip()
    if query:
        queryset = queryset.filter(
            document_number__icontains=query
        ) | queryset.filter(first_name__icontains=query) | queryset.filter(
            last_name__icontains=query
        )
    if status:
        queryset = queryset.filter(status=status)
    page = Paginator(queryset.distinct(), 20).get_page(request.GET.get("page"))
    return render(
        request,
        "app_egresados/list.html",
        {"page": page, "query": query, "status": status, "status_choices": Egresado.Estado.choices},
    )


@role_required("Administrador", "funcionario")
def egresado_create_view(request):
    """Registra un egresado certificado de forma individual."""
    form = EgresadoCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        graduate = form.save(commit=False)
        graduate.last_updated_at = timezone.localdate()
        graduate.save()
        messages.success(request, "El egresado quedó registrado.")
        return redirect("app_egresados:detail", pk=graduate.pk)
    return render(request, "app_egresados/form.html", {"form": form, "title": "Nuevo egresado"})


@role_required("Administrador", "funcionario")
def egresados_import_view(request):
    """Importa un lote CSV o Excel solo si todas sus filas son válidas."""
    if request.method == "POST":
        uploaded_file = request.FILES.get("archivo")
        if not uploaded_file:
            messages.error(request, "Seleccione un archivo CSV o Excel.")
        else:
            try:
                rows = _read_import_rows(uploaded_file)
                graduates, errors = _validate_import(rows)
                if not errors:
                    try:
                        with transaction.atomic():
                            for graduate in graduates:
                                graduate.save()
                    except IntegrityError:
                        messages.error(
                            request,
                            "No se importó el archivo: un documento ya existe en la base de datos.",
                        )
                        return render(request, "app_egresados/import.html")
                    messages.success(request, f"Se importaron {len(graduates)} egresados.")
                    return redirect("app_egresados:list")
                for error in errors[:20]:
                    messages.error(request, error)
                if len(errors) > 20:
                    messages.error(request, f"Hay {len(errors) - 20} errores adicionales.")
            except (ValueError, OSError, BadZipFile, InvalidFileException) as error:
                messages.error(request, str(error))
    return render(request, "app_egresados/import.html")


@role_required("Administrador", "funcionario")
def egresado_detail_view(request, pk):
    """Muestra la ficha de un egresado a los roles autorizados."""
    graduate = get_object_or_404(Egresado, pk=pk)
    return render(request, "app_egresados/detail.html", {"graduate": graduate})


@role_required("Administrador")
def egresado_admin_update_view(request, pk):
    """Permite al administrador actualizar datos maestros del egresado."""
    graduate = get_object_or_404(Egresado, pk=pk)
    form = EgresadoAdminForm(request.POST or None, instance=graduate)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "El registro maestro fue actualizado.")
        return redirect("app_egresados:detail", pk=graduate.pk)
    return render(
        request,
        "app_egresados/form.html",
        {"form": form, "title": "Editar registro maestro"},
    )


@role_required("Administrador")
def egresado_inactivate_view(request, pk):
    """Inactiva el perfil conservando sus datos para métricas históricas."""
    graduate = get_object_or_404(Egresado, pk=pk)
    if request.method == "POST":
        reason = request.POST.get("reason", "").strip()
        if not reason:
            messages.error(request, "Indique el motivo de inactivación.")
        else:
            graduate.status = Egresado.Estado.INACTIVO
            graduate.inactivity_reason = reason[:100]
            graduate.save(update_fields=["status", "inactivity_reason"])
            messages.success(request, "El perfil fue inactivado sin borrar sus datos.")
            return redirect("app_egresados:list")
    return render(
        request, "app_egresados/inactivate.html", {"graduate": graduate}
    )


@consent_required
@role_required("egresado")
def my_profile_view(request):
    """Muestra el perfil propio de la cuenta autenticada."""
    graduate = get_object_or_404(Egresado, user=request.user)
    from app_encuestas.models import Aviso, Encuesta

    pending_count = Encuesta.objects.filter(published=True).exclude(
        responses__graduate=graduate
    ).filter(target_program__in=["", graduate.program]).filter(
        target_center__in=["", graduate.center]
    ).count()
    notices = Aviso.objects.filter(published=True).filter(
        Q(target_program="") | Q(target_program=graduate.program)
    ).filter(Q(target_center="") | Q(target_center=graduate.center))
    return render(
        request,
        "app_egresados/my_profile.html",
        {"graduate": graduate, "pending_count": pending_count, "notices": notices},
    )


@consent_required
@role_required("egresado")
def my_profile_update_view(request):
    """Actualiza los campos permitidos por el egresado y fecha de vigencia."""
    graduate = get_object_or_404(Egresado, user=request.user)
    form = EgresadoContactForm(request.POST or None, instance=graduate)
    if request.method == "POST" and form.is_valid():
        previous_employment_status = graduate.employment_status
        profile = form.save(commit=False)
        profile.last_updated_at = timezone.localdate()
        if profile.employment_status == Egresado.SituacionLaboral.DESEMPLEADO:
            if (
                previous_employment_status != Egresado.SituacionLaboral.DESEMPLEADO
                or profile.unemployment_since is None
            ):
                profile.unemployment_since = timezone.localdate()
        else:
            profile.unemployment_since = None
        if profile.status == Egresado.Estado.DESACTUALIZADO:
            profile.status = Egresado.Estado.ACTIVO
        profile.save()
        messages.success(request, "Tu información fue actualizada.")
        return redirect("app_egresados:my_profile")
    return render(
        request,
        "app_egresados/form.html",
        {"form": form, "title": "Actualizar mis datos"},
    )


@consent_required
@role_required("egresado")
def trajectory_list_view(request):
    """Lista la trayectoria de la persona autenticada."""
    graduate = get_object_or_404(Egresado, user=request.user)
    entries = graduate.trayectorias.all()
    return render(
        request,
        "app_egresados/trajectory_list.html",
        {"graduate": graduate, "entries": entries},
    )


@consent_required
@role_required("egresado")
def trajectory_create_view(request):
    """Crea un registro de trayectoria asociado al perfil propio."""
    graduate = get_object_or_404(Egresado, user=request.user)
    form = TrayectoriaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        entry = form.save(commit=False)
        entry.egresado = graduate
        entry.created_by = request.user
        entry.save()
        messages.success(request, "El registro de trayectoria fue agregado.")
        return redirect("app_egresados:trajectory_list")
    return render(request, "app_egresados/form.html", {"form": form, "title": "Nueva trayectoria"})


@consent_required
@role_required("egresado")
def trajectory_delete_view(request, pk):
    """Elimina únicamente un registro creado por el usuario autenticado."""
    entry = get_object_or_404(
        Trayectoria, pk=pk, egresado__user=request.user, created_by=request.user
    )
    if request.method == "POST":
        entry.delete(request_user=request.user)
        messages.success(request, "El registro de trayectoria fue eliminado.")
    return redirect("app_egresados:trajectory_list")
