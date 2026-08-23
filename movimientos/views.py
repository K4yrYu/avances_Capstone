from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import F, Q, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date

from productos.models import DetalleSolicitudReposicion, Producto

from .models import LoteInventario, MovimientoInventario
from .services import registrar_ajuste_stock


def es_administrador(user):
    return user.is_active and user.is_staff


@user_passes_test(es_administrador, login_url="/usuarios/iniciosesion/")
def lista_movimientos(request):
    movimientos = MovimientoInventario.objects.select_related("responsable")
    q = request.GET.get("q", "").strip()
    filtros = {
        "tipo": (request.GET.get("tipo", ""), MovimientoInventario.Tipo.values),
        "estado": (request.GET.get("estado", ""), MovimientoInventario.Estado.values),
        "origen": (request.GET.get("origen", ""), MovimientoInventario.Origen.values),
    }
    if q:
        movimientos = movimientos.filter(Q(producto_nombre__icontains=q) | Q(producto_sku__icontains=q) | Q(referencia__icontains=q))
    for campo, (valor, permitidos) in filtros.items():
        if valor in permitidos:
            movimientos = movimientos.filter(**{campo: valor})
    categoria = request.GET.get("categoria", "")
    if categoria:
        movimientos = movimientos.filter(categoria=categoria)
    desde, hasta = parse_date(request.GET.get("desde", "")), parse_date(request.GET.get("hasta", ""))
    if desde:
        movimientos = movimientos.filter(creado_en__date__gte=desde)
    if hasta:
        movimientos = movimientos.filter(creado_en__date__lte=hasta)

    totales = movimientos.aggregate(entradas=Coalesce(Sum("entrada"), 0), salidas=Coalesce(Sum("salida"), 0))
    pendientes = DetalleSolicitudReposicion.objects.filter(solicitud__estado="enviada").aggregate(total=Coalesce(Sum("cantidad_solicitada"), 0))["total"]
    alertas = Producto.objects.filter(activo=True, stock__lte=F("stock_minimo")).count()
    flujo = (MovimientoInventario.objects.filter(creado_en__date__gte=timezone.localdate() - timedelta(days=13)).annotate(dia=TruncDate("creado_en")).values("dia").annotate(entradas=Coalesce(Sum("entrada"), 0), salidas=Coalesce(Sum("salida"), 0)).order_by("dia"))
    vendidos = MovimientoInventario.objects.filter(origen=MovimientoInventario.Origen.VENTA).values("producto_id_original", "producto_nombre", "producto_sku").annotate(total=Coalesce(Sum("salida"), 0))
    vencen_pronto = LoteInventario.objects.select_related("producto").filter(cantidad_disponible__gt=0, fecha_vencimiento__gte=timezone.localdate(), fecha_vencimiento__lte=timezone.localdate() + timedelta(days=60))[:5]
    pagina = Paginator(movimientos, 25).get_page(request.GET.get("pagina"))
    parametros_filtro = request.GET.copy()
    parametros_filtro.pop("pagina", None)
    return render(request, "movimientos/lista.html", {
        "pagina": pagina, "totales": totales, "pendientes": pendientes, "alertas": alertas,
        "productos": Producto.objects.filter(activo=True).order_by("nombre"),
        "categorias": Producto.objects.order_by().values_list("categoria", flat=True).distinct(),
        "tipos": MovimientoInventario.Tipo.choices, "estados": MovimientoInventario.Estado.choices,
        "origenes": MovimientoInventario.Origen.choices,
        "mas_vendidos": list(vendidos.order_by("-total", "producto_nombre")[:5]),
        "menos_vendidos": list(vendidos.order_by("total", "producto_nombre")[:5]),
        "vencen_pronto": vencen_pronto,
        "grafico_fechas": [fila["dia"].strftime("%d/%m") for fila in flujo],
        "grafico_entradas": [fila["entradas"] for fila in flujo],
        "grafico_salidas": [fila["salidas"] for fila in flujo],
        "parametros_filtro": parametros_filtro.urlencode(),
    })


@user_passes_test(es_administrador, login_url="/usuarios/iniciosesion/")
def registrar_ajuste(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    try:
        producto_id = int(request.POST.get("producto", ""))
        nuevo_stock = int(request.POST.get("nuevo_stock", ""))
        observacion = request.POST.get("observacion", "").strip()
        if len(observacion) < 10:
            raise ValidationError("La observación debe tener al menos 10 caracteres.")
        movimiento = registrar_ajuste_stock(producto_id=producto_id, nuevo_stock=nuevo_stock, observacion=observacion, responsable=request.user)
    except (TypeError, ValueError, Producto.DoesNotExist):
        messages.error(request, "Selecciona un producto y escribe un stock válido.")
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        messages.success(request, f"Ajuste registrado. Nuevo stock: {movimiento.stock_resultante}.")
    return redirect("movimientos:lista")
