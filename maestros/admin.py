from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    DocumentoMaestro,
    Especialidad,
    ImagenTrabajoRealizado,
    LicenciaMaestro,
    PerfilMaestro,
    TrabajoRealizado,
)


@admin.register(Especialidad)
class EspecialidadAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tipo_licencia", "activa")
    list_filter = ("activa", "tipo_licencia")
    search_fields = ("nombre",)


class ImagenTrabajoInline(admin.TabularInline):
    model = ImagenTrabajoRealizado
    extra = 0


@admin.register(TrabajoRealizado)
class TrabajoRealizadoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "maestro", "mostrar_especialidades", "comuna", "publicado")
    list_filter = ("publicado", "especialidades")
    search_fields = ("titulo", "maestro__usuario__username", "comuna")
    filter_horizontal = ("especialidades",)
    inlines = (ImagenTrabajoInline,)

    @admin.display(description="Especialidades")
    def mostrar_especialidades(self, obj):
        return ", ".join(obj.especialidades.values_list("nombre", flat=True))


@admin.action(description="Aprobar perfiles seleccionados")
def aprobar_perfiles(modeladmin, request, queryset):
    aprobados = 0
    omitidos = []
    for perfil in queryset.exclude(usuario=request.user).prefetch_related(
        "especialidades", "documentos", "licencias"
    ):
        if perfil.estado != PerfilMaestro.Estado.PENDIENTE:
            omitidos.append(f"{perfil}: no está pendiente")
            continue
        try:
            perfil.cambiar_estado(PerfilMaestro.Estado.APROBADO)
        except ValidationError as error:
            omitidos.append(f"{perfil.usuario}: {' '.join(error.messages)}")
        else:
            aprobados += 1
    if aprobados:
        modeladmin.message_user(
            request,
            f"Se aprobaron {aprobados} perfil(es).",
            level=messages.SUCCESS,
        )
    if omitidos:
        modeladmin.message_user(
            request,
            "No se aprobaron: " + " | ".join(omitidos),
            level=messages.WARNING,
        )


@admin.action(description="Rechazar perfiles seleccionados")
def rechazar_perfiles(modeladmin, request, queryset):
    queryset.exclude(usuario=request.user).update(
        estado=PerfilMaestro.Estado.RECHAZADO,
        fecha_aprobacion=None,
    )


@admin.action(description="Suspender perfiles seleccionados")
def suspender_perfiles(modeladmin, request, queryset):
    queryset.exclude(usuario=request.user).update(
        estado=PerfilMaestro.Estado.SUSPENDIDO,
        fecha_aprobacion=None,
    )


@admin.register(PerfilMaestro)
class PerfilMaestroAdmin(admin.ModelAdmin):
    list_display = (
        "usuario",
        "estado",
        "estado_documental",
        "comuna",
        "disponible",
        "fecha_aprobacion",
    )
    list_filter = ("estado", "disponible", "especialidades")
    search_fields = ("usuario__username", "usuario__email", "usuario__rut", "comuna")
    filter_horizontal = ("especialidades",)
    readonly_fields = ("estado", "fecha_aprobacion", "creado_en", "actualizado_en")
    actions = (aprobar_perfiles, rechazar_perfiles, suspender_perfiles)

    @admin.display(description="Documentación", boolean=True)
    def estado_documental(self, obj):
        return obj.documentacion_completa()


@admin.register(ImagenTrabajoRealizado)
class ImagenTrabajoRealizadoAdmin(admin.ModelAdmin):
    list_display = ("trabajo", "creada_en")


class ArchivoPrivadoAdminMixin:
    readonly_fields = (
        "enlace_archivo_privado",
        "subido_en",
        "actualizado_en",
        "revisado_en",
        "revisado_por",
    )

    @admin.display(description="Archivo privado")
    def enlace_archivo_privado(self, obj):
        if not obj.pk or not obj.archivo:
            return "Sin archivo"
        nombre_url = (
            "maestros:descargar_documento"
            if isinstance(obj, DocumentoMaestro)
            else "maestros:descargar_licencia"
        )
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">Ver documento</a>',
            reverse(nombre_url, args=[obj.pk]),
        )


@admin.register(DocumentoMaestro)
class DocumentoMaestroAdmin(ArchivoPrivadoAdminMixin, admin.ModelAdmin):
    list_display = ("perfil", "tipo", "estado_revision", "actualizado_en", "revisado_por")
    list_filter = ("tipo", "estado_revision")
    search_fields = ("perfil__usuario__username", "perfil__usuario__rut")
    fields = (
        "perfil",
        "tipo",
        "enlace_archivo_privado",
        "estado_revision",
        "observacion_admin",
        "subido_en",
        "actualizado_en",
        "revisado_en",
        "revisado_por",
    )


@admin.register(LicenciaMaestro)
class LicenciaMaestroAdmin(ArchivoPrivadoAdminMixin, admin.ModelAdmin):
    list_display = (
        "perfil",
        "tipo_licencia",
        "clase",
        "numero_licencia",
        "estado_revision",
        "revisado_por",
    )
    list_filter = ("tipo_licencia", "estado_revision", "clase")
    search_fields = (
        "perfil__usuario__username",
        "perfil__usuario__rut",
        "numero_licencia",
    )
    fields = (
        "perfil",
        "tipo_licencia",
        "clase",
        "numero_licencia",
        "enlace_archivo_privado",
        "estado_revision",
        "observacion_admin",
        "subido_en",
        "actualizado_en",
        "revisado_en",
        "revisado_por",
    )
