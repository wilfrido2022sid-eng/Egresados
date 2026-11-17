"""Pruebas del comando para cuentas de demostración."""

from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.management import call_command, CommandError
from django.test import TestCase

from app_egresados.models import Egresado


class DemoCommandTests(TestCase):
    """Verifica que la demo cree los cuatro roles y datos de prueba."""

    def test_command_creates_demo_roles_accounts_and_fixtures(self):
        """Crea cuentas con contraseñas válidas y perfiles de muestra."""
        output = StringIO()
        call_command("crear_demo", stdout=output)

        self.assertEqual(
            set(Group.objects.values_list("name", flat=True)),
            {"Administrador", "funcionario", "egresado", "visor"},
        )
        self.assertEqual(User.objects.filter(username__startswith="demo_").count(), 4)
        self.assertEqual(Egresado.objects.filter(document_number__startswith="DEMO-").count(), 2)
        self.assertIn("contraseña=", output.getvalue())

        graduate_user = User.objects.get(username="demo_egresado")
        self.assertTrue(graduate_user.check_password(
            output.getvalue().split("usuario=demo_egresado contraseña=")[1].splitlines()[0]
        ))

    def test_command_never_overwrites_existing_demo_users(self):
        """Se detiene sin alterar una cuenta previa con nombre reservado."""
        existing = User.objects.create_user("demo_visor", password="do-not-change")
        with self.assertRaises(CommandError):
            call_command("crear_demo", stdout=StringIO())
        existing.refresh_from_db()
        self.assertTrue(existing.check_password("do-not-change"))
