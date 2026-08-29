from django.urls import path

from . import api_views, views

app_name = "maestros"

urlpatterns = [
    path("api/maestros/mi-perfil/", api_views.MiPerfilAPIView.as_view(), name="api_mi_perfil"),
    path(
        "api/maestros/mi-perfil/enviar-revision/",
        api_views.EnviarRevisionAPIView.as_view(),
        name="api_enviar_revision",
    ),
    path(
        "api/maestros/documentos/",
        api_views.DocumentosPropiosAPIView.as_view(),
        name="api_documentos",
    ),
    path(
        "api/maestros/licencias/",
        api_views.LicenciasPropiasAPIView.as_view(),
        name="api_licencias",
    ),
    path("api/maestros/trabajos/", api_views.TrabajosAPIView.as_view(), name="api_trabajos"),
    path(
        "api/maestros/trabajos/<int:pk>/",
        api_views.TrabajoDetalleAPIView.as_view(),
        name="api_trabajo_detalle",
    ),
    path(
        "api/maestros/trabajos/<int:pk>/imagenes/",
        api_views.ImagenesTrabajoAPIView.as_view(),
        name="api_trabajo_imagenes",
    ),
    path(
        "api/maestros/imagenes/<int:pk>/",
        api_views.ImagenDetalleAPIView.as_view(),
        name="api_imagen_detalle",
    ),
    path(
        "api/maestros/admin/<int:pk>/estado/",
        api_views.EstadoMaestroAdminAPIView.as_view(),
        name="api_admin_estado",
    ),
    path(
        "api/maestros/admin/documentos/<int:pk>/estado/",
        api_views.RevisionDocumentoAdminAPIView.as_view(),
        name="api_admin_documento_estado",
    ),
    path(
        "api/maestros/admin/licencias/<int:pk>/estado/",
        api_views.RevisionLicenciaAdminAPIView.as_view(),
        name="api_admin_licencia_estado",
    ),
    path(
        "api/maestros/publicos/",
        api_views.MaestrosPublicosAPIView.as_view(),
        name="api_publicos",
    ),
    path(
        "api/maestros/publicos/<int:pk>/",
        api_views.MaestroPublicoDetalleAPIView.as_view(),
        name="api_publico_detalle",
    ),
    path("maestros/", views.lista_maestros, name="lista"),
    path("maestros/trabaja-con-nosotros/", views.trabaja_con_nosotros, name="trabaja_con_nosotros"),
    path("maestros/panel/", views.panel_maestro, name="panel"),
    path("maestros/perfil/crear/", views.crear_perfil, name="crear_perfil"),
    path("maestros/perfil/editar/", views.editar_perfil, name="editar_perfil"),
    path("maestros/perfil/enviar-revision/", views.enviar_revision, name="enviar_revision"),
    path(
        "maestros/documentos/<str:tipo>/subir/",
        views.subir_documento,
        name="subir_documento",
    ),
    path(
        "maestros/documentos/<int:pk>/ver/",
        views.descargar_documento,
        name="descargar_documento",
    ),
    path(
        "maestros/licencias/<str:tipo>/subir/",
        views.subir_licencia,
        name="subir_licencia",
    ),
    path(
        "maestros/licencias/<int:pk>/ver/",
        views.descargar_licencia,
        name="descargar_licencia",
    ),
    path("maestros/perfil/apelar/", views.solicitar_apelacion, name="solicitar_apelacion"),
    path("maestros/trabajos/", views.gestion_trabajos, name="trabajos"),
    path("maestros/trabajos/nuevo/", views.crear_trabajo, name="crear_trabajo"),
    path("maestros/trabajos/<int:pk>/editar/", views.editar_trabajo, name="editar_trabajo"),
    path("maestros/trabajos/<int:pk>/eliminar/", views.eliminar_trabajo, name="eliminar_trabajo"),
    path("maestros/imagenes/<int:pk>/eliminar/", views.eliminar_imagen, name="eliminar_imagen"),
    path("administracion/maestros/", views.revision_maestros, name="admin_revision"),
    path("administracion/maestros/especialidades/agregar/", views.crear_especialidad, name="admin_crear_especialidad"),
    path("administracion/maestros/<int:pk>/estado/", views.cambiar_estado_maestro, name="admin_estado"),
    path(
        "administracion/maestros/documentos/<int:pk>/estado/",
        views.revisar_documento,
        name="admin_documento_estado",
    ),
    path(
        "administracion/maestros/licencias/<int:pk>/estado/",
        views.revisar_licencia,
        name="admin_licencia_estado",
    ),
    path("maestros/<int:pk>/", views.detalle_maestro, name="detalle"),
]
