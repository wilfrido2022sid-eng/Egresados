"""Decoradores de autenticación y autorización por grupos."""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(*group_names):
    """Restringe una vista a los grupos indicados o a superusuarios."""

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapped_view(request, *args, **kwargs):
            user = request.user
            if user.is_superuser or user.groups.filter(name__in=group_names).exists():
                return view_func(request, *args, **kwargs)
            raise PermissionDenied

        return wrapped_view

    return decorator


def consent_required(view_func):
    """Exige consentimiento vigente a los usuarios del grupo Egresado."""

    @wraps(view_func)
    @login_required
    def wrapped_view(request, *args, **kwargs):
        user = request.user
        if user.groups.filter(name="egresado").exists():
            profile = getattr(user, "egresado", None)
            if profile and profile.status in {"No contactable", "Inactivo"}:
                from django.contrib import messages
                from django.contrib.auth import logout
                from django.shortcuts import redirect

                logout(request)
                messages.error(request, "El acceso de este perfil está deshabilitado.")
                return redirect("app_usuarios:login")
            if profile is None or not profile.privacy_accepted:
                from django.shortcuts import redirect

                return redirect("app_usuarios:consent")
        return view_func(request, *args, **kwargs)

    return wrapped_view
