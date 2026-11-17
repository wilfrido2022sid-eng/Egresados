"""Vistas para inicio de sesión, acceso y consentimiento de datos."""

from django import forms
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.utils.http import url_has_allowed_host_and_scheme
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from app_egresados.models import Egresado

from .decorators import role_required
from .models import Consentimiento


class ConsentForm(forms.Form):
    """Captura una decisión explícita sobre el tratamiento de datos."""

    accepted = forms.BooleanField(
        required=False,
        label="Acepto la Política de Tratamiento de Datos Personales del SENA.",
    )


def login_view(request):
    """Autentica con el sistema de usuarios de Django."""
    if request.user.is_authenticated:
        return redirect("app_usuarios:dashboard")
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        login(request, user)
        next_url = request.POST.get("next") or request.GET.get("next", "")
        if next_url and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            return redirect(next_url)
        return redirect("app_usuarios:dashboard")
    return render(request, "app_usuarios/login.html", {"form": form})


@login_required
def logout_view(request):
    """Cierra la sesión solo mediante una solicitud POST protegida por CSRF."""
    if request.method == "POST":
        logout(request)
        messages.info(request, "La sesión se cerró correctamente.")
    return redirect("app_usuarios:login")


@login_required
def dashboard_view(request):
    """Dirige al usuario al flujo que corresponde con su grupo y consentimiento."""
    user = request.user
    if user.groups.filter(name="egresado").exists():
        graduate = get_object_or_404(Egresado, user=user)
        if graduate.status in {
            Egresado.Estado.INACTIVO,
            Egresado.Estado.NO_CONTACTABLE,
        }:
            logout(request)
            messages.error(request, "El acceso de este perfil está deshabilitado.")
            return redirect("app_usuarios:login")
        if not graduate.privacy_accepted:
            return redirect("app_usuarios:consent")
        return redirect("app_egresados:my_profile")
    if user.is_superuser or user.groups.filter(
        name__in=["Administrador", "funcionario", "visor"]
    ).exists():
        return redirect("app_reportes:dashboard")
    messages.error(request, "Tu cuenta no tiene un grupo de acceso asignado.")
    logout(request)
    return redirect("app_usuarios:login")


@role_required("egresado")
def consent_view(request):
    """Registra aceptación o rechazo de la política con evidencia de sesión."""
    graduate = get_object_or_404(Egresado, user=request.user)
    if graduate.status in {Egresado.Estado.NO_CONTACTABLE, Egresado.Estado.INACTIVO}:
        logout(request)
        messages.error(request, "El perfil está bloqueado. Contacta al equipo institucional.")
        return redirect("app_usuarios:login")
    form = ConsentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        accepted = form.cleaned_data["accepted"]
        signature = request.user.get_full_name() or request.user.get_username()
        Consentimiento.objects.create(
            graduate=graduate,
            accepted=accepted,
            signature=signature[:200],
            ip_address=request.META.get("REMOTE_ADDR"),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
        )
        graduate.privacy_accepted = accepted
        graduate.privacy_accepted_at = timezone.now() if accepted else None
        graduate.privacy_signature = signature[:200] if accepted else ""
        if not accepted:
            graduate.status = Egresado.Estado.NO_CONTACTABLE
        graduate.save()
        if accepted:
            messages.success(request, "Gracias. Tu acceso al sistema está habilitado.")
            return redirect("app_usuarios:dashboard")
        logout(request)
        messages.info(request, "El acceso fue bloqueado y el perfil quedó No contactable.")
        return redirect("app_usuarios:login")
    return render(request, "app_usuarios/consent.html", {"form": form})


@login_required
def home_view(_request):
    """Muestra el punto de entrada según el perfil y las encuestas pendientes."""
    return redirect("app_usuarios:dashboard")
