"""Crea grupos, cuentas y datos ficticios para revisar los flujos web."""

import secrets
from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from django.utils import timezone

from app_egresados.models import Egresado, Trayectoria
from app_encuestas.models import Aviso, Encuesta, Pregunta
from app_reportes.models import Acompanamiento


DEMO_ACCOUNTS = (
    ("demo_administrador", "Administrador"),
    ("demo_funcionario", "funcionario"),
    ("demo_egresado", "egresado"),
    ("demo_visor", "visor"),
)


class Command(BaseCommand):
    """Provisiona una demo local sin alterar cuentas existentes."""

    help = "Crea grupos y cuatro cuentas de demostración con contraseñas aleatorias."

    def handle(self, *args, **options):
        """Crea datos ficticios y muestra las credenciales una sola vez."""
        existing = list(
            User.objects.filter(username__in=[item[0] for item in DEMO_ACCOUNTS])
            .values_list("username", flat=True)
        )
        if existing:
            names = ", ".join(existing)
            raise CommandError(
                f"Ya existen cuentas de demo ({names}). No se modificó ningún registro."
            )
        if Egresado.objects.filter(
            document_number__in=["DEMO-1001", "DEMO-1002"]
        ).exists():
            raise CommandError(
                "Ya existen documentos demo. No se modificó ningún registro."
            )

        credentials = {
            username: secrets.token_urlsafe(18) for username, _group in DEMO_ACCOUNTS
        }
        try:
            with transaction.atomic():
                groups = {
                    group_name: Group.objects.get_or_create(name=group_name)[0]
                    for _username, group_name in DEMO_ACCOUNTS
                }
                users = {}
                for username, group_name in DEMO_ACCOUNTS:
                    user = User.objects.create_user(
                        username=username,
                        email=f"{username}@example.test",
                        first_name=group_name.title(),
                        password=credentials[username],
                    )
                    user.groups.add(groups[group_name])
                    users[username] = user

                today = timezone.localdate()
                graduate = Egresado.objects.create(
                    user=users["demo_egresado"],
                    document_type="Demo",
                    document_number="DEMO-1001",
                    first_name="Alex",
                    last_name="Egresado Demo",
                    email="demo_egresado@example.test",
                    phone="3000000001",
                    address="Dirección ficticia 123",
                    municipality="Bogotá",
                    program="Tecnólogo en Energía Solar Fotovoltaica",
                    center="Centro de Energías Renovables",
                    certified_on=today - timedelta(days=390),
                    employment_status=Egresado.SituacionLaboral.EMPLEADO,
                    contract_type=Egresado.TipoContrato.INDEFINIDO,
                    company="Energía Demo SAS",
                    privacy_accepted=False,
                )
                alert_profile = Egresado.objects.create(
                    document_type="Demo",
                    document_number="DEMO-1002",
                    first_name="Sam",
                    last_name="Perfil Alerta",
                    email="sam@example.test",
                    phone="3000000002",
                    address="Dirección ficticia 456",
                    municipality="Medellín",
                    program="Tecnólogo en Energía Solar Fotovoltaica",
                    center="Centro de Energías Renovables",
                    certified_on=today - timedelta(days=500),
                    employment_status=Egresado.SituacionLaboral.DESEMPLEADO,
                    unemployment_since=today - timedelta(days=210),
                    vulnerability=True,
                )
                Trayectoria.objects.create(
                    egresado=graduate,
                    created_by=users["demo_egresado"],
                    kind=Trayectoria.Tipo.LABORAL,
                    title="Técnico de mantenimiento fotovoltaico",
                    organization="Energía Demo SAS",
                    description="Mantenimiento preventivo de sistemas solares.",
                    started_on=today - timedelta(days=180),
                )
                survey = Encuesta.objects.create(
                    title="Seguimiento a egresados · cohorte demo",
                    description="Cuéntanos sobre tu experiencia después de certificarte.",
                    target_program=graduate.program,
                    target_center=graduate.center,
                    published=True,
                    created_by=users["demo_funcionario"],
                    published_at=timezone.now(),
                )
                Pregunta.objects.create(
                    survey=survey,
                    prompt="¿Actualmente tienes empleo?",
                    question_type=Pregunta.Tipo.OPCION,
                    options=["Sí", "No"],
                    negative_answers=["No"],
                    position=1,
                )
                Pregunta.objects.create(
                    survey=survey,
                    prompt="¿Qué aspecto de tu formación te ha sido más útil?",
                    question_type=Pregunta.Tipo.PARRAFO,
                    position=2,
                )
                Aviso.objects.create(
                    title="Bienvenida a la cohorte demo",
                    body="Este aviso de ejemplo es ficticio y se muestra en tu perfil.",
                    target_program=graduate.program,
                    target_center=graduate.center,
                    created_by=users["demo_funcionario"],
                )
                Acompanamiento.objects.create(
                    graduate=alert_profile,
                    created_by=users["demo_visor"],
                    contacted_via=Acompanamiento.Medio.LLAMADA,
                    body="Registro ficticio: se intentó contactar al egresado para conocer su situación laboral.",
                )
        except IntegrityError as error:
            raise CommandError(
                "No fue posible crear los datos demo porque existe información incompatible."
            ) from error

        self.stdout.write(self.style.SUCCESS("Cuentas de demostración creadas."))
        self.stdout.write("Contraseñas aleatorias; guárdalas ahora, no se vuelven a mostrar:")
        for username, group_name in DEMO_ACCOUNTS:
            self.stdout.write(
                f"  Rol {group_name}: usuario={username} contraseña={credentials[username]}"
            )
        self.stdout.write("")
        self.stdout.write("Perfiles ficticios DEMO-1001 y DEMO-1002; no usar en producción.")
