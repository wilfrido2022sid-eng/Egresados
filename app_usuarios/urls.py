"""Rutas de acceso y consentimiento."""

from django.urls import path

from . import views

app_name = "app_usuarios"

urlpatterns = [
    path("ingresar/", views.login_view, name="login"),
    path("salir/", views.logout_view, name="logout"),
    path("privacidad/", views.consent_view, name="consent"),
    path("inicio/", views.dashboard_view, name="dashboard"),
    path("", views.home_view, name="home"),
]
