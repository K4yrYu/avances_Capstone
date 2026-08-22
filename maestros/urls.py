from django.urls import path

from . import views

app_name = "maestros"

urlpatterns = [
    path("maestros/", views.lista_maestros, name="lista"),
    path("maestros/trabaja-con-nosotros/", views.trabaja_con_nosotros, name="trabaja_con_nosotros"),
    path("maestros/panel/", views.panel_maestro, name="panel"),
    path("maestros/perfil/crear/", views.crear_perfil, name="crear_perfil"),
    path("maestros/perfil/editar/", views.editar_perfil, name="editar_perfil"),
    path("maestros/perfil/enviar-revision/", views.enviar_revision, name="enviar_revision"),
    path("maestros/trabajos/", views.gestion_trabajos, name="trabajos"),
    path("maestros/trabajos/nuevo/", views.crear_trabajo, name="crear_trabajo"),
    path("maestros/trabajos/<int:pk>/editar/", views.editar_trabajo, name="editar_trabajo"),
    path("maestros/trabajos/<int:pk>/eliminar/", views.eliminar_trabajo, name="eliminar_trabajo"),
    path("maestros/imagenes/<int:pk>/eliminar/", views.eliminar_imagen, name="eliminar_imagen"),
    path("administracion/maestros/", views.revision_maestros, name="admin_revision"),
    path("administracion/maestros/especialidades/agregar/", views.crear_especialidad, name="admin_crear_especialidad"),
    path("administracion/maestros/<int:pk>/estado/", views.cambiar_estado_maestro, name="admin_estado"),
    path("maestros/<int:pk>/", views.detalle_maestro, name="detalle"),
]
