"""Pruebas de reglas de negocio para perfiles de egresados."""

from datetime import timedelta
from io import BytesIO

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from openpyxl import Workbook

from .models import Egresado


class EgresadoRulesTests(TestCase):
    """Verifica validaciones académicas y controles de perfil."""

    def setUp(self):
        """Crea un egresado certificado y una cuenta con grupo."""
        self.group = Group.objects.create(name="egresado")
        self.user = User.objects.create_user("egresado", password="StrongTestPass123!")
        self.user.groups.add(self.group)
        self.graduate = Egresado.objects.create(
            user=self.user,
            document_type="CC",
            document_number="10001",
            first_name="Ana",
            last_name="Prueba",
            program="Energía solar",
            certified_on=timezone.localdate(),
        )

    def test_only_certified_academic_status_can_be_saved(self):
        """Rechaza deserción, retiro voluntario y etapa lectiva."""
        for status in (
            Egresado.EstadoAcademico.DESERCION,
            Egresado.EstadoAcademico.RETIRO,
            Egresado.EstadoAcademico.LECTIVA,
        ):
            with self.subTest(status=status):
                self.graduate.academic_status = status
                with self.assertRaises(ValidationError):
                    self.graduate.save()
        self.graduate.refresh_from_db()
        self.assertEqual(self.graduate.academic_status, Egresado.EstadoAcademico.CERTIFICADO)

    def test_physical_profile_deletion_is_blocked(self):
        """Impide eliminar perfiles tanto por instancia como por queryset."""
        with self.assertRaises(ValidationError):
            self.graduate.delete()
        with self.assertRaises(ValidationError):
            Egresado.objects.filter(pk=self.graduate.pk).delete()

    def test_profile_requires_consent_and_can_only_edit_contact_fields(self):
        """Pide consentimiento y no acepta cambios a los campos inmutables."""
        self.client.force_login(self.user)
        response = self.client.get(reverse("app_egresados:my_profile"))
        self.assertRedirects(response, reverse("app_usuarios:consent"))

        self.client.post(reverse("app_usuarios:consent"), {"accepted": "on"})
        response = self.client.post(
            reverse("app_egresados:my_profile_update"),
            {
                "email": "ana@example.com",
                "phone": "3001234567",
                "address": "Calle 1",
                "municipality": "Bogotá",
                "employment_status": Egresado.SituacionLaboral.EMPLEADO,
                "contract_type": Egresado.TipoContrato.INDEFINIDO,
                "company": "Solar SAS",
                "document_number": "99999",
                "program": "Programa alterado",
            },
        )
        self.assertRedirects(response, reverse("app_egresados:my_profile"))
        self.graduate.refresh_from_db()
        self.assertEqual(self.graduate.document_number, "10001")
        self.assertEqual(self.graduate.program, "Energía solar")
        self.assertEqual(self.graduate.email, "ana@example.com")
        self.assertEqual(self.graduate.last_updated_at, timezone.localdate())
        self.assertNotContains(
            self.client.get(reverse("app_egresados:my_profile_update")),
            "unemployment_since",
        )

    def test_entering_unemployment_records_start_date(self):
        """Inicia el conteo del desempleo al cambiar de estado laboral."""
        self.client.force_login(self.user)
        self.graduate.privacy_accepted = True
        self.graduate.employment_status = Egresado.SituacionLaboral.EMPLEADO
        self.graduate.save()
        self.client.post(
            reverse("app_egresados:my_profile_update"),
            {
                "email": "",
                "phone": "",
                "address": "",
                "municipality": "",
                "employment_status": Egresado.SituacionLaboral.DESEMPLEADO,
                "contract_type": "",
                "company": "",
            },
        )
        self.graduate.refresh_from_db()
        self.assertEqual(self.graduate.unemployment_since, timezone.localdate())

    def test_rejecting_consent_blocks_access(self):
        """Registra el rechazo y cambia el estado a No contactable."""
        self.client.force_login(self.user)
        response = self.client.post(reverse("app_usuarios:consent"), {"accepted": ""})
        self.assertRedirects(response, reverse("app_usuarios:login"))
        self.graduate.refresh_from_db()
        self.assertEqual(self.graduate.status, Egresado.Estado.NO_CONTACTABLE)
        self.assertFalse(self.graduate.privacy_accepted)
        self.assertEqual(self.graduate.consent_logs.count(), 1)

    def test_daily_staleness_command_uses_more_than_180_days(self):
        """Marca desactualizados solo los perfiles con más de 180 días."""
        from django.core.management import call_command

        self.graduate.last_updated_at = timezone.localdate() - timedelta(days=181)
        self.graduate.save()
        call_command("actualizar_egresados", verbosity=0)
        self.graduate.refresh_from_db()
        self.assertEqual(self.graduate.status, Egresado.Estado.DESACTUALIZADO)


class EgresadoAccessTests(TestCase):
    """Verifica que los roles sin permiso no gestionen registros."""

    def test_visor_cannot_open_management_list(self):
        """Niega la lista operativa a un usuario visor."""
        group = Group.objects.create(name="visor")
        user = User.objects.create_user("visor", password="StrongTestPass123!")
        user.groups.add(group)
        self.client.force_login(user)
        response = self.client.get(reverse("app_egresados:list"))
        self.assertEqual(response.status_code, 403)

    def test_staff_list_renders_and_certified_csv_import_succeeds(self):
        """Renderiza el listado e importa un registro CSV certificado."""
        group = Group.objects.create(name="funcionario")
        user = User.objects.create_user("funcionario", password="StrongTestPass123!")
        user.groups.add(group)
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("app_egresados:list")).status_code, 200)

        payload = (
            "document_type,document_number,first_name,last_name,program,"
            "certified_on,academic_status\n"
            "CC,40001,Elena,Importada,Energía solar,2024-06-10,Certificado\n"
        )
        upload = SimpleUploadedFile("cohorte.csv", payload.encode("utf-8"), "text/csv")
        response = self.client.post(reverse("app_egresados:import"), {"archivo": upload})
        self.assertRedirects(response, reverse("app_egresados:list"))
        self.assertTrue(Egresado.objects.filter(document_number="40001").exists())

    def test_import_rejects_non_certified_records_without_partial_writes(self):
        """Rechaza el lote cuando un registro incumple el estado académico."""
        group = Group.objects.create(name="funcionario")
        user = User.objects.create_user("funcionario", password="StrongTestPass123!")
        user.groups.add(group)
        self.client.force_login(user)
        payload = (
            "document_type,document_number,first_name,last_name,program,"
            "certified_on,academic_status\n"
            "CC,40002,Elena,Rechazada,Energía solar,2024-06-10,Etapa lectiva\n"
        )
        upload = SimpleUploadedFile("cohorte.csv", payload.encode("utf-8"), "text/csv")
        response = self.client.post(reverse("app_egresados:import"), {"archivo": upload})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Egresado.objects.filter(document_number="40002").exists())
        self.assertContains(response, "Certificado")

    def test_excel_import_accepts_workbook_rows(self):
        """Lee un archivo Excel válido y lo importa."""
        group = Group.objects.create(name="funcionario")
        user = User.objects.create_user("funcionario-xlsx", password="StrongTestPass123!")
        user.groups.add(group)
        self.client.force_login(user)
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(
            [
                "document_type",
                "document_number",
                "first_name",
                "last_name",
                "program",
                "certified_on",
                "academic_status",
            ]
        )
        sheet.append(["CC", "40003", "Luis", "Excel", "Energía solar", "2024-06-10", "Certificado"])
        output = BytesIO()
        workbook.save(output)
        upload = SimpleUploadedFile(
            "cohorte.xlsx",
            output.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response = self.client.post(reverse("app_egresados:import"), {"archivo": upload})
        self.assertRedirects(response, reverse("app_egresados:list"))
        self.assertTrue(Egresado.objects.filter(document_number="40003").exists())
