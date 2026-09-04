from datetime import timedelta

from django.db.models import Q, Sum
from django.utils import timezone

from .models import DetalleSolicitudReposicion, Producto


PERIODOS_ROTACION = {30, 90, 365}


def normalizar_filtros_rotacion(periodo, categoria):
    try:
        periodo = int(periodo)
    except (TypeError, ValueError):
        periodo = 30
    if periodo not in PERIODOS_ROTACION:
        periodo = 30
    categorias = {valor for valor, _ in Producto.CATEGORIA_CHOICES}
    categoria = categoria if categoria in categorias else ''
    return periodo, categoria


def obtener_rotacion_productos(*, periodo=30, categoria=''):
    periodo, categoria = normalizar_filtros_rotacion(periodo, categoria)
    desde = timezone.now() - timedelta(days=periodo)
    productos = Producto.objects.filter(activo=True)
    if categoria:
        productos = productos.filter(categoria=categoria)
    productos = list(productos.annotate(
        unidades_vendidas=Sum(
            'detalles__cantidad_producto',
            filter=Q(
                detalles__id_venta__estado_venta='pagado',
                detalles__id_venta__eliminado=False,
                detalles__id_venta__fecha_compra__gte=desde,
            ),
            default=0,
        )
    ).order_by('nombre'))

    pendientes = {}
    pendientes_qs = DetalleSolicitudReposicion.objects.filter(
        solicitud__estado__in=['pendiente', 'error', 'enviada', 'parcial'],
        producto_id__in=[producto.pk for producto in productos],
    ).annotate(recibidas=Sum('detalles_recepcion__cantidad_recibida', default=0))
    for detalle in pendientes_qs:
        faltante = max(detalle.cantidad_solicitada - detalle.recibidas, 0)
        pendientes[detalle.producto_id] = pendientes.get(detalle.producto_id, 0) + faltante

    max_vendido = max((producto.unidades_vendidas for producto in productos), default=0)
    resultado = []
    for producto in productos:
        vendidas = producto.unidades_vendidas or 0
        por_recibir = pendientes.get(producto.pk, 0)
        if vendidas == 0:
            nivel = 'Sin ventas'
        elif max_vendido and vendidas >= max_vendido * .66:
            nivel = 'Alta'
        elif max_vendido and vendidas >= max_vendido * .33:
            nivel = 'Media'
        else:
            nivel = 'Baja'
        resultado.append({
            'id': producto.pk,
            'nombre': producto.nombre,
            'sku': producto.sku or 'Sin SKU',
            'categoria': producto.categoria,
            'vendidas': vendidas,
            'stock': producto.stock,
            'stock_minimo': producto.stock_minimo,
            'pendientes': por_recibir,
            'rotacion': nivel,
            'sugerida': max(vendidas + producto.stock_minimo - producto.stock - por_recibir, 0),
        })
    return resultado
