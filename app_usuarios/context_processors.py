"""Variables de navegación derivadas de los grupos de acceso."""


def role_flags(request):
    """Expone banderas de rol para mostrar enlaces pertinentes."""
    user = request.user
    names = set(user.groups.values_list("name", flat=True)) if user.is_authenticated else set()
    return {
        "can_manage_graduates": user.is_authenticated
        and (user.is_superuser or "Administrador" in names or "funcionario" in names),
        "can_manage_surveys": user.is_authenticated
        and (user.is_superuser or "Administrador" in names or "funcionario" in names),
        "is_administrator": user.is_authenticated
        and (user.is_superuser or "Administrador" in names),
        "can_view_reports": user.is_authenticated
        and (user.is_superuser or bool(names.intersection({"Administrador", "funcionario", "visor"}))),
        "is_graduate": user.is_authenticated and "egresado" in names,
        "can_create_accompaniment": user.is_authenticated and "visor" in names,
    }
