"""Pruebas de creación, publicación y respuesta de encuestas."""

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from app_egresados.models import Egresado

from .models import Aviso, Encuesta, Pregunta, RespuestaEncuesta


class SurveyFlowTests(TestCase):
    """Verifica el ciclo de una encuesta dirigida a egresados."""

    def setUp(self):
        """Crea una cuenta de egresado, perfil y encuesta publicada."""
        group = Group.objects.create(name="egresado")
        self.user = User.objects.create_user("ana", password="StrongTestPass123!")
        self.user.groups.add(group)
        self.graduate = Egresado.objects.create(
            user=self.user,
            document_type="CC",
            document_number="20001",
            first_name="Ana",
            last_name="Prueba",
            program="Energía solar",
            center="Centro Uno",
            certified_on=timezone.localdate(),
            privacy_accepted=True,
        )
        self.survey = Encuesta.objects.create(
            title="Seguimiento",
            target_program="Energía solar",
            created_by=self.user,
            published=True,
        )
        self.question = Pregunta.objects.create(
            survey=self.survey, prompt="¿Trabajas?", question_type="radio", options=["Sí", "No"]
        )

    def test_survey_answer_is_saved_once_and_removed_from_pending(self):
        """Persiste las respuestas y evita un segundo envío."""
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("app_encuestas:answer", args=[self.survey.pk]),
            {f"pregunta_{self.question.pk}": "Sí"},
        )
        self.assertRedirects(
            response, reverse("app_usuarios:dashboard"), fetch_redirect_response=False
        )
        self.assertEqual(RespuestaEncuesta.objects.filter(graduate=self.graduate).count(), 1)
        self.assertNotContains(
            self.client.get(reverse("app_encuestas:pending")), self.survey.title
        )

    def test_answer_rejects_an_option_outside_survey_definition(self):
        """No almacena una respuesta de selección que no fue ofrecida."""
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("app_encuestas:answer", args=[self.survey.pk]),
            {f"pregunta_{self.question.pk}": "Opción ajena"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            RespuestaEncuesta.objects.filter(survey=self.survey, graduate=self.graduate).exists()
        )

    def test_required_checkbox_question_accepts_one_selected_option(self):
        """Permite responder una o más opciones en una pregunta obligatoria."""
        question = Pregunta.objects.create(
            survey=self.survey,
            prompt="¿Qué temas te interesan?",
            question_type="checkbox",
            options=["Solar", "Eólica"],
        )
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("app_encuestas:answer", args=[self.survey.pk]),
            {f"pregunta_{self.question.pk}": "Sí", f"pregunta_{question.pk}": ["Solar"]},
        )
        self.assertRedirects(
            response, reverse("app_usuarios:dashboard"), fetch_redirect_response=False
        )
        self.assertEqual(RespuestaEncuesta.objects.get(graduate=self.graduate).answers.count(), 2)

    def test_unrelated_program_cannot_answer_targeted_survey(self):
        """Oculta la encuesta a egresados fuera de la audiencia configurada."""
        self.graduate.program = "Otra formación"
        self.graduate.save()
        self.client.force_login(self.user)
        response = self.client.get(reverse("app_encuestas:answer", args=[self.survey.pk]))
        self.assertEqual(response.status_code, 404)

    def test_staff_can_design_and_publish_structured_survey(self):
        """Permite crear preguntas y publicar un formulario para su cohorte."""
        group = Group.objects.create(name="funcionario")
        staff_user = User.objects.create_user("funcionario", password="StrongTestPass123!")
        staff_user.groups.add(group)
        self.client.force_login(staff_user)
        payload = {
            "title": "Situación laboral",
            "description": "Seguimiento de cohorte",
            "target_program": "Energía solar",
            "target_center": "Centro Uno",
            "question_specs": (
                "¿Tienes empleo? | radio | obligatorio | Sí, No | No\n"
                "Cuéntanos más | textarea | opcional"
            ),
        }
        response = self.client.post(reverse("app_encuestas:create"), payload)
        self.assertRedirects(response, reverse("app_encuestas:list"))
        survey = Encuesta.objects.get(title="Situación laboral")
        self.assertEqual(survey.questions.count(), 2)
        question = survey.questions.get(prompt="¿Tienes empleo?")
        self.assertEqual(question.negative_answers, ["No"])
        self.client.post(reverse("app_encuestas:publish", args=[survey.pk]))
        survey.refresh_from_db()
        self.assertTrue(survey.published)

    def test_staff_can_publish_audience_targeted_notice(self):
        """Publica avisos para que aparezcan solo en los perfiles asignados."""
        group = Group.objects.create(name="funcionario")
        staff_user = User.objects.create_user("comunicaciones", password="StrongTestPass123!")
        staff_user.groups.add(group)
        self.client.force_login(staff_user)
        response = self.client.get(reverse("app_encuestas:create"))
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            reverse("app_encuestas:notice_create"),
            {
                "title": "Feria solar",
                "body": "Inscripciones abiertas.",
                "target_program": "Energía solar",
                "target_center": "Centro Uno",
            },
        )
        self.assertRedirects(response, reverse("app_encuestas:notices"))
        self.assertTrue(Aviso.objects.get(title="Feria solar").published)

        self.client.force_login(self.user)
        response = self.client.get(reverse("app_egresados:my_profile"))
        self.assertContains(response, "Feria solar")

        other_user = User.objects.create_user("otra", password="StrongTestPass123!")
        other_user.groups.add(self.user.groups.get())
        Egresado.objects.create(
            user=other_user,
            document_type="CC",
            document_number="20002",
            first_name="Otra",
            last_name="Cohorte",
            program="Otra formación",
            certified_on=timezone.localdate(),
            privacy_accepted=True,
        )
        self.client.force_login(other_user)
        response = self.client.get(reverse("app_egresados:my_profile"))
        self.assertNotContains(response, "Feria solar")
