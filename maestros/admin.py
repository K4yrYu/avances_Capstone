from django.contrib import admin
from django.utils import timezone

from .models import Especialidad, ImagenTrabajoRealizado, PerfilMaestro, TrabajoRealizado


@admin.register(Especialidad)
class EspecialidadAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activa")
    list_filter = ("activa",)
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
    queryset.exclude(usuario=request.user).update(
        estado=PerfilMaestro.Estado.APROBADO,
        fecha_aprobacion=timezone.now(),
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
    list_display = ("usuario", "estado", "comuna", "disponible", "fecha_aprobacion")
    list_filter = ("estado", "disponible", "especialidades")
    search_fields = ("usuario__username", "usuario__email", "usuario__rut", "comuna")
    filter_horizontal = ("especialidades",)
    readonly_fields = ("fecha_aprobacion", "creado_en", "actualizado_en")
    actions = (aprobar_perfiles, rechazar_perfiles, suspender_perfiles)


@admin.register(ImagenTrabajoRealizado)
class ImagenTrabajoRealizadoAdmin(admin.ModelAdmin):
    list_display = ("trabajo", "creada_en")
