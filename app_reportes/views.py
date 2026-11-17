"""Vistas para indicadores, exportaciones y alertas."""

import csv
import io
from datetime import timedelta
from xml.sax.saxutils import escape

from django import forms
from django.contrib import messages
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app_egresados.models import Egresado
from app_encuestas.models import Respuesta
from app_usuarios.decorators import role_required

from .models import Acompanamiento


class AcompanamientoForm(forms.ModelForm):
    """Formulario para registrar o editar una nota de seguimiento."""

    class Meta:
        model = Acompanamiento
        fields = ["contacted_via", "body"]
        widgets = {"body": forms.Textarea(attrs={"rows": 4})}


def _filtered_profiles(request):
    """Devuelve el conjunto de perfiles filtrado por los parámetros del tablero."""
    profiles = Egresado.objects.all()
    program = request.GET.get("programa", "").strip()
    center = request.GET.get("centro", "").strip()
    year = request.GET.get("cohorte", "").strip()
    if program:
        profiles = profiles.filter(program=program)
    if center:
        profiles = profiles.filter(center=center)
    if year.isdigit():
        profiles = profiles.filter(certified_on__year=int(year))
    return profiles, {"programa": program, "centro": center, "cohorte": year}


def _metrics(profiles):
    """Calcula métricas sin exponer los perfiles inactivos."""
    active = profiles.exclude(status=Egresado.Estado.INACTIVO)
    total = active.count()
    employed = active.filter(
        employment_status__in=[
            Egresado.SituacionLaboral.EMPLEADO,
            Egresado.SituacionLaboral.INDEPENDIENTE,
        ]
    ).count()
    entrepreneurs = active.filter(
        employment_status=Egresado.SituacionLaboral.EMPRENDEDOR
    ).count()
    contract_counts = active.filter(contract_type__gt="").values("contract_type").annotate(
        total=Count("pk")
    ).order_by("contract_type")
    return {
        "total": total,
        "employed": employed,
        "employment_rate": round(employed * 100 / total, 1) if total else 0,
        "entrepreneurs": entrepreneurs,
        "entrepreneurship_rate": round(entrepreneurs * 100 / total, 1) if total else 0,
        "contract_counts": list(contract_counts),
        "inactive_history": profiles.filter(status=Egresado.Estado.INACTIVO).count(),
    }


def _negative_survey_profile_ids():
    """Obtiene perfiles con respuestas marcadas como negativas en su encuesta."""
    negative_ids = set()
    answers = Respuesta.objects.select_related("submission", "question").exclude(
        question__negative_answers=[]
    )
    for answer in answers:
        selected = answer.value if isinstance(answer.value, list) else [answer.value]
        negative = {str(value).casefold() for value in answer.question.negative_answers}
        if any(str(value).casefold() in negative for value in selected):
            negative_ids.add(answer.submission.graduate_id)
    return negative_ids


def _alert_profiles():
    """Construye la lista de perfiles que requieren acompañamiento."""
    cutoff = timezone.localdate() - timedelta(days=180)
    negative_ids = _negative_survey_profile_ids()
    profiles = Egresado.objects.exclude(status=Egresado.Estado.INACTIVO).filter(
        Q(status=Egresado.Estado.DESACTUALIZADO)
        | Q(vulnerability=True)
        | Q(
            employment_status=Egresado.SituacionLaboral.DESEMPLEADO,
            unemployment_since__lte=cutoff,
        )
        | Q(pk__in=negative_ids)
    ).distinct()
    return profiles, cutoff, negative_ids


def _spreadsheet_safe(value):
    """Neutraliza valores que una hoja de cálculo podría interpretar como fórmula."""
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


@role_required("Administrador", "funcionario", "visor")
def dashboard_view(request):
    """Muestra indicadores institucionales y filtros de cohorte."""
    profiles, filters = _filtered_profiles(request)
    metrics = _metrics(profiles)
    alert_profiles, _, _ = _alert_profiles()
    alert_count = alert_profiles.filter(pk__in=profiles.values("pk")).count()
    return render(
        request,
        "app_reportes/dashboard.html",
        {
            "metrics": metrics,
            "filters": filters,
            "programs": Egresado.objects.order_by()
            .values_list("program", flat=True)
            .distinct(),
            "centers": Egresado.objects.exclude(center="")
            .order_by()
            .values_list("center", flat=True)
            .distinct(),
            "years": Egresado.objects.dates("certified_on", "year", order="DESC"),
            "alert_count": alert_count,
        },
    )


@role_required("Administrador", "funcionario", "visor")
def report_export_view(request, file_format):
    """Exporta los indicadores filtrados como CSV, Excel o PDF."""
    if file_format not in {"csv", "xlsx", "pdf"}:
        return HttpResponse("Formato de exportación no compatible.", status=400)
    profiles, filters = _filtered_profiles(request)
    metrics = _metrics(profiles)
    rows = [
        ("Indicador", "Valor"),
        ("Egresados activos", metrics["total"]),
        ("Empleados e independientes", metrics["employed"]),
        ("Tasa de empleabilidad (%)", metrics["employment_rate"]),
        ("Emprendedores", metrics["entrepreneurs"]),
        ("Índice de emprendimiento (%)", metrics["entrepreneurship_rate"]),
        ("Perfiles inactivos (histórico anónimo)", metrics["inactive_history"]),
    ]
    rows.extend(
        (f"Contrato: {item['contract_type']}", item["total"])
        for item in metrics["contract_counts"]
    )
    filename = f"reporte-egresados-{timezone.localdate():%Y%m%d}"
    if file_format == "csv":
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}.csv"'
        response.write("\ufeff")
        writer = csv.writer(response)
        writer.writerows(rows)
        writer.writerow([])
        writer.writerow(["Programa", _spreadsheet_safe(filters["programa"] or "Todos")])
        writer.writerow(["Centro", _spreadsheet_safe(filters["centro"] or "Todos")])
        writer.writerow(["Cohorte", _spreadsheet_safe(filters["cohorte"] or "Todas")])
        return response
    if file_format == "xlsx":
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Indicadores"
        for row in rows:
            sheet.append(row)
        sheet.append([])
        sheet.append(["Programa", _spreadsheet_safe(filters["programa"] or "Todos")])
        sheet.append(["Centro", _spreadsheet_safe(filters["centro"] or "Todos")])
        sheet.append(["Cohorte", _spreadsheet_safe(filters["cohorte"] or "Todas")])
        output = io.BytesIO()
        workbook.save(output)
        response = HttpResponse(
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}.xlsx"'
        return response
    output = io.BytesIO()
    document = SimpleDocTemplate(output, pagesize=A4, title="Reporte de egresados")
    styles = getSampleStyleSheet()
    story = [
        Paragraph("REPORTE INSTITUCIONAL DE EGRESADOS", styles["Title"]),
        Spacer(1, 16),
        Paragraph(
            f"Programa: {escape(filters['programa'] or 'Todos')} · "
            f"Centro: {escape(filters['centro'] or 'Todos')} · "
            f"Cohorte: {escape(filters['cohorte'] or 'Todas')}",
            styles["BodyText"],
        ),
        Spacer(1, 16),
        Table(rows, repeatRows=1),
    ]
    story[-1].setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1A1A1A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#1A1A1A")),
                ("PADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    document.build(story)
    response = HttpResponse(output.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}.pdf"'
    return response


@role_required("Administrador", "funcionario", "visor")
def alerts_list_view(request):
    """Presenta egresados con riesgo de desempleo, vulnerabilidad o desactualización."""
    alerts, cutoff, negative_ids = _alert_profiles()
    return render(
        request,
        "app_reportes/alerts.html",
        {"alerts": alerts, "cutoff": cutoff, "negative_ids": negative_ids},
    )


@role_required("Administrador", "funcionario", "visor")
def alert_detail_view(request, pk):
    """Muestra datos de contacto y bitácora del egresado en alerta."""
    alerts, _, _ = _alert_profiles()
    graduate = get_object_or_404(alerts, pk=pk)
    return render(
        request,
        "app_reportes/alert_detail.html",
        {
            "graduate": graduate,
            "notes": graduate.acompanamientos.select_related("created_by"),
        },
    )


@role_required("visor")
def accompaniment_create_view(request, pk):
    """Permite al visor añadir una nota de acompañamiento."""
    alerts, _, _ = _alert_profiles()
    graduate = get_object_or_404(alerts, pk=pk)
    form = AcompanamientoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        note = form.save(commit=False)
        note.graduate = graduate
        note.created_by = request.user
        note.save()
        messages.success(request, "El acompañamiento fue registrado.")
        return redirect("app_reportes:alert_detail", pk=graduate.pk)
    return render(
        request,
        "app_reportes/note_form.html",
        {"form": form, "graduate": graduate, "title": "Registrar acompañamiento"},
    )


@role_required("visor")
def accompaniment_update_view(request, pk):
    """Restringe la edición de una nota a su autor."""
    note = get_object_or_404(Acompanamiento, pk=pk, created_by=request.user)
    form = AcompanamientoForm(request.POST or None, instance=note)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "La nota de acompañamiento fue actualizada.")
        return redirect("app_reportes:alert_detail", pk=note.graduate_id)
    return render(
        request,
        "app_reportes/note_form.html",
        {"form": form, "graduate": note.graduate, "title": "Editar acompañamiento"},
    )
