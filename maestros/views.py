from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .chile import COMUNA_REGION, COMUNAS_CHOICES, REGIONES_CHOICES
from .forms import EspecialidadForm, PerfilMaestroForm, TrabajoRealizadoForm
from .models import Especialidad, ImagenTrabajoRealizado, PerfilMaestro, TrabajoRealizado


def _puede_ser_maestro(user):
    return user.is_authenticated and user.is_active and user.email_confirmado


def _perfil_del_usuario(request):
    return get_object_or_404(
        PerfilMaestro.objects.prefetch_related("especialidades"),
        usuario=request.user,
    )


def _exigir_admin(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        raise PermissionDenied


def trabaja_con_nosotros(request):
    perfil = None
    if request.user.is_authenticated:
        perfil = PerfilMaestro.objects.filter(usuario=request.user).first()
    return render(request, "maestros/trabaja_con_nosotros.html", {"perfil": perfil})


@login_required
def crear_perfil(request):
    if not _puede_ser_maestro(request.user):
        raise PermissionDenied("Debes tener una cuenta activa y un correo confirmado.")
    if PerfilMaestro.objects.filter(usuario=request.user).exists():
        return redirect("maestros:panel")

    form = PerfilMaestroForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        perfil = form.save(commit=False)
        perfil.usuario = request.user
        perfil.estado = PerfilMaestro.Estado.BORRADOR
        perfil.save()
        form.save_m2m()
        messages.success(request, "Tu perfil profesional fue creado como borrador.")
        return redirect("maestros:panel")
    return render(request, "maestros/perfil_form.html", {"form": form, "es_nuevo": True})


@login_required
def panel_maestro(request):
    perfil = PerfilMaestro.objects.filter(usuario=request.user).prefetch_related("especialidades").first()
    if perfil is None:
        return redirect("maestros:trabaja_con_nosotros")
    trabajos = perfil.trabajos.prefetch_related("especialidades", "imagenes")
    return render(request, "maestros/panel.html", {"perfil": perfil, "trabajos": trabajos})


@login_required
def editar_perfil(request):
    perfil = _perfil_del_usuario(request)
    form = PerfilMaestroForm(request.POST or None, request.FILES or None, instance=perfil)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Tu perfil fue actualizado.")
        return redirect("maestros:panel")
    return render(request, "maestros/perfil_form.html", {"form": form, "perfil": perfil, "es_nuevo": False})


@require_POST
@login_required
def enviar_revision(request):
    perfil = _perfil_del_usuario(request)
    if perfil.estado == PerfilMaestro.Estado.SUSPENDIDO:
        messages.error(request, "Un perfil suspendido debe ser habilitado por administración.")
        return redirect("maestros:panel")
    perfil.estado = PerfilMaestro.Estado.PENDIENTE
    perfil.observacion_admin = ""
    perfil.fecha_aprobacion = None
    perfil.save(update_fields=["estado", "observacion_admin", "fecha_aprobacion", "actualizado_en"])
    messages.success(request, "Tu perfil fue enviado a revisión.")
    return redirect("maestros:panel")


@login_required
def gestion_trabajos(request):
    perfil = _perfil_del_usuario(request)
    trabajos = perfil.trabajos.prefetch_related("especialidades", "imagenes")
    return render(request, "maestros/trabajos.html", {"perfil": perfil, "trabajos": trabajos})


def _guardar_imagenes(trabajo, imagenes):
    ImagenTrabajoRealizado.objects.bulk_create(
        [ImagenTrabajoRealizado(trabajo=trabajo, imagen=imagen) for imagen in imagenes]
    )


@login_required
@transaction.atomic
def crear_trabajo(request):
    perfil = _perfil_del_usuario(request)
    form = TrabajoRealizadoForm(request.POST or None, request.FILES or None, maestro=perfil)
    if request.method == "POST" and form.is_valid():
        trabajo = form.save(commit=False)
        trabajo.maestro = perfil
        trabajo.save()
        form.save_m2m()
        _guardar_imagenes(trabajo, form.cleaned_data["imagenes"])
        messages.success(request, "El trabajo fue agregado a tu portafolio.")
        return redirect("maestros:trabajos")
    return render(request, "maestros/trabajo_form.html", {"form": form, "perfil": perfil})


@login_required
@transaction.atomic
def editar_trabajo(request, pk):
    perfil = _perfil_del_usuario(request)
    trabajo = get_object_or_404(TrabajoRealizado, pk=pk, maestro=perfil)
    form = TrabajoRealizadoForm(
        request.POST or None,
        request.FILES or None,
        instance=trabajo,
        maestro=perfil,
    )
    if request.method == "POST" and form.is_valid():
        trabajo = form.save()
        _guardar_imagenes(trabajo, form.cleaned_data["imagenes"])
        messages.success(request, "El trabajo fue actualizado.")
        return redirect("maestros:trabajos")
    return render(
        request,
        "maestros/trabajo_form.html",
        {"form": form, "perfil": perfil, "trabajo": trabajo},
    )


@require_POST
@login_required
def eliminar_trabajo(request, pk):
    perfil = _perfil_del_usuario(request)
    trabajo = get_object_or_404(TrabajoRealizado, pk=pk, maestro=perfil)
    trabajo.delete()
    messages.success(request, "El trabajo fue eliminado.")
    return redirect("maestros:trabajos")


@require_POST
@login_required
def eliminar_imagen(request, pk):
    imagen = get_object_or_404(
        ImagenTrabajoRealizado,
        pk=pk,
        trabajo__maestro__usuario=request.user,
    )
    trabajo_pk = imagen.trabajo_id
    imagen.delete()
    messages.success(request, "La imagen fue eliminada.")
    return redirect("maestros:editar_trabajo", pk=trabajo_pk)


def lista_maestros(request):
    maestros = (
        PerfilMaestro.objects.filter(estado=PerfilMaestro.Estado.APROBADO)
        .select_related("usuario")
        .prefetch_related("especialidades")
    )
    especialidad = request.GET.get("especialidad", "").strip()
    region = request.GET.get("region", "").strip().upper()
    comuna = request.GET.get("comuna", "").strip()
    if especialidad.isdigit():
        maestros = maestros.filter(especialidades__id=especialidad)
    if region in dict(REGIONES_CHOICES):
        maestros = maestros.filter(region=region)
    if comuna:
        maestros = maestros.filter(zonas_trabajo__icontains=comuna)
    maestros = maestros.distinct()
    return render(
        request,
        "maestros/lista.html",
        {
            "maestros": maestros,
            "especialidades": Especialidad.objects.filter(activa=True),
            "filtro_especialidad": especialidad,
            "regiones": REGIONES_CHOICES,
            "comunas": [
                {"nombre": nombre, "region": COMUNA_REGION[nombre]}
                for nombre, _ in COMUNAS_CHOICES
            ],
            "filtro_region": region,
            "filtro_comuna": comuna,
        },
    )


def detalle_maestro(request, pk):
    perfil = get_object_or_404(
        PerfilMaestro.objects.select_related("usuario").prefetch_related("especialidades"),
        pk=pk,
        estado=PerfilMaestro.Estado.APROBADO,
    )
    trabajos = perfil.trabajos.filter(publicado=True).prefetch_related("especialidades", "imagenes")
    return render(request, "maestros/detalle.html", {"perfil": perfil, "trabajos": trabajos})


@login_required
def revision_maestros(request):
    _exigir_admin(request)
    estado = request.GET.get("estado", "").strip().upper()
    perfiles_base = PerfilMaestro.objects.select_related("usuario").prefetch_related("especialidades")
    conteos = {
        "total": perfiles_base.count(),
        "pendientes": perfiles_base.filter(estado=PerfilMaestro.Estado.PENDIENTE).count(),
        "aprobados": perfiles_base.filter(estado=PerfilMaestro.Estado.APROBADO).count(),
    }
    perfiles = perfiles_base
    if estado in PerfilMaestro.Estado.values:
        perfiles = perfiles.filter(estado=estado)
    return render(
        request,
        "maestros/revision_admin.html",
        {
            "perfiles": perfiles,
            "estados": PerfilMaestro.Estado.choices,
            "filtro_estado": estado,
            "conteos": conteos,
            "especialidad_form": EspecialidadForm(),
            "especialidades": Especialidad.objects.all(),
        },
    )


@require_POST
@login_required
def cambiar_estado_maestro(request, pk):
    _exigir_admin(request)
    perfil = get_object_or_404(PerfilMaestro, pk=pk)
    if perfil.usuario_id == request.user.id:
        raise PermissionDenied("No puedes revisar tu propio perfil profesional.")
    nuevo_estado = request.POST.get("estado", "").upper()
    if nuevo_estado not in {
        PerfilMaestro.Estado.APROBADO,
        PerfilMaestro.Estado.RECHAZADO,
        PerfilMaestro.Estado.SUSPENDIDO,
    }:
        messages.error(request, "La acción seleccionada no es válida.")
        return redirect("maestros:admin_revision")
    perfil.observacion_admin = request.POST.get("observacion_admin", "").strip()
    perfil.save(update_fields=["observacion_admin", "actualizado_en"])
    perfil.cambiar_estado(nuevo_estado)
    messages.success(request, f"El perfil quedó {perfil.get_estado_display().lower()}.")
    return redirect("maestros:admin_revision")


@require_POST
@login_required
def crear_especialidad(request):
    _exigir_admin(request)
    form = EspecialidadForm(request.POST)
    if form.is_valid():
        especialidad = form.save()
        messages.success(request, f"La especialidad {especialidad.nombre} fue agregada.")
    else:
        error = next(iter(form.errors.values()))[0]
        messages.error(request, f"No fue posible agregar la especialidad: {error}")
    return redirect("maestros:admin_revision")
