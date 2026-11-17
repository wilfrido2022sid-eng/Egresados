"""Pruebas de privacidad de indicadores y exportaciones."""

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from app_egresados.models import Egresado
from app_encuestas.models import Encuesta, Pregunta, Respuesta, RespuestaEncuesta

from .models import Acompanamiento


class ReportPrivacyTests(TestCase):
    """Verifica la agregación anónima y permisos de solo lectura."""

    def setUp(self):
        """Crea usuario visor y registros activos e inactivos."""
        group = Group.objects.create(name="visor")
        self.user = User.objects.create_user("visor", password="StrongTestPass123!")
        self.user.groups.add(group)
        self.client.force_login(self.user)
        self.active = Egresado.objects.create(
            document_type="CC",
            document_number="30001",
            first_name="Visible",
            last_name="Activo",
            program="Solar",
            certified_on=timezone.localdate(),
            employment_status=Egresado.SituacionLaboral.EMPLEADO,
        )
        self.inactive = Egresado.objects.create(
            document_type="CC",
            document_number="30002",
            first_name="Privado",
            last_name="Inactivo",
            program="Solar",
            certified_on=timezone.localdate(),
            status=Egresado.Estado.INACTIVO,
        )

    def test_dashboard_anonymizes_inactive_profiles(self):
        """Presenta solo cantidades del histórico inactivo."""
        response = self.client.get(reverse("app_reportes:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["metrics"]["total"], 1)
        self.assertEqual(response.context["metrics"]["inactive_history"], 1)
        self.assertNotContains(response, self.inactive.first_name)
        self.assertNotContains(response, self.inactive.document_number)

    def test_csv_export_contains_aggregates_not_personal_data(self):
        """Exporta estadísticas agregadas sin nombre ni documento."""
        response = self.client.get(reverse("app_reportes:export", args=["csv"]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertNotContains(response, self.inactive.document_number)
        self.assertNotContains(response, self.active.document_number)

    def test_spreadsheet_exports_neutralize_formula_like_filter_values(self):
        """Evita que filtros manipulados se ejecuten como fórmulas en una hoja."""
        response = self.client.get(
            reverse("app_reportes:export", args=["csv"]),
            {"programa": "=1+1"},
        )
        self.assertContains(response, "'=1+1")
        response = self.client.get(
            reverse("app_reportes:export", args=["xlsx"]),
            {"programa": "=1+1"},
        )
        from io import BytesIO
        from openpyxl import load_workbook

        workbook = load_workbook(BytesIO(response.content), read_only=True, data_only=False)
        self.assertIn(
            "'=1+1",
            [cell.value for row in workbook.active.iter_rows() for cell in row],
        )

    def test_excel_and_pdf_exports_are_available(self):
        """Responde con los tipos MIME esperados para Excel y PDF."""
        excel = self.client.get(reverse("app_reportes:export", args=["xlsx"]))
        pdf = self.client.get(reverse("app_reportes:export", args=["pdf"]))
        self.assertEqual(excel["Content-Type"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        self.assertEqual(pdf["Content-Type"], "application/pdf")

    def test_visor_cannot_create_profiles(self):
        """Impide que un visor use rutas de mantenimiento de perfiles."""
        response = self.client.get(reverse("app_egresados:create"))
        self.assertEqual(response.status_code, 403)

    def test_negative_survey_answers_are_in_alerts(self):
        """Incluye perfiles que eligieron una opción marcada como negativa."""
        survey = Encuesta.objects.create(title="Seguimiento", created_by=self.user)
        question = Pregunta.objects.create(
            survey=survey,
            prompt="¿Tienes empleo?",
            question_type="radio",
            options=["Sí", "No"],
            negative_answers=["No"],
        )
        submission = RespuestaEncuesta.objects.create(
            survey=survey, graduate=self.active
        )
        Respuesta.objects.create(submission=submission, question=question, value="No")
        response = self.client.get(reverse("app_reportes:alerts"))
        self.assertIn(self.active.pk, response.context["negative_ids"])
        self.assertContains(response, "ENCUESTA NEGATIVA")

    def test_visor_can_only_edit_their_own_accompaniment_notes(self):
        """Permite modificar notas propias y oculta las de otras cuentas visor."""
        self.active.vulnerability = True
        self.active.save()
        note = Acompanamiento.objects.create(
            graduate=self.active, created_by=self.user, body="Primer contacto"
        )
        self.assertEqual(
            self.client.get(
                reverse("app_reportes:accompaniment_update", args=[note.pk])
            ).status_code,
            200,
        )
        other_user = User.objects.create_user("otro-visor", password="StrongTestPass123!")
        other_user.groups.add(self.user.groups.get())
        self.client.force_login(other_user)
        response = self.client.get(
            reverse("app_reportes:accompaniment_update", args=[note.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_alert_detail_does_not_expose_unflagged_profiles(self):
        """Solo abre la ficha de egresados que aparecen en la lista de alertas."""
        response = self.client.get(
            reverse("app_reportes:alert_detail", args=[self.active.pk])
        )
        self.assertEqual(response.status_code, 404)
