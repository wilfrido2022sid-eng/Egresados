"""Rutas de perfiles y trayectoria de egresados."""

from django.urls import path

from . import views

app_name = "app_egresados"

urlpatterns = [
    path("", views.egresados_list_view, name="list"),
    path("crear/", views.egresado_create_view, name="create"),
    path("importar/", views.egresados_import_view, name="import"),
    path("<int:pk>/", views.egresado_detail_view, name="detail"),
    path("<int:pk>/editar/", views.egresado_admin_update_view, name="admin_update"),
    path("<int:pk>/inactivar/", views.egresado_inactivate_view, name="inactivate"),
    path("mi-perfil/", views.my_profile_view, name="my_profile"),
    path("mi-perfil/editar/", views.my_profile_update_view, name="my_profile_update"),
    path("mi-trayectoria/", views.trajectory_list_view, name="trajectory_list"),
    path("mi-trayectoria/crear/", views.trajectory_create_view, name="trajectory_create"),
    path(
        "mi-trayectoria/<int:pk>/eliminar/",
        views.trajectory_delete_view,
        name="trajectory_delete",
    ),
]
