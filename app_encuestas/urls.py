"""Rutas de encuestas."""

from django.urls import path

from . import views

app_name = "app_encuestas"

urlpatterns = [
    path("", views.surveys_list_view, name="list"),
    path("crear/", views.survey_create_view, name="create"),
    path("avisos/", views.notices_list_view, name="notices"),
    path("avisos/crear/", views.notice_create_view, name="notice_create"),
    path("<int:pk>/publicar/", views.survey_publish_view, name="publish"),
    path("pendientes/", views.survey_pending_view, name="pending"),
    path("<int:pk>/responder/", views.survey_answer_view, name="answer"),
]
