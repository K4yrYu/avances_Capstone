from datetime import timedelta

from django.shortcuts import render
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth import get_user_model
from django.db.models import Count, F, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from productos.models import DetalleSolicitudReposicion, Producto, SolicitudReposicion
from carro_compras.models import Venta
from maestros.models import PerfilMaestro
from movimientos.models import MovimientoInventario


def index(request):
    productos_activos = Producto.objects.filter(activo=True)
    productos_destacados = productos_activos.order_by('-id')[:4]
    totales_categoria = {
        item['categoria']: item['total']
        for item in productos_activos.values('categoria').annotate(total=Count('id'))
    }
    categorias_destacadas = [
        {
            'nombre': 'Herramientas',
            'descripcion': 'Equipos manuales y eléctricos para trabajar con precisión.',
            'icono': 'fa-screwdriver-wrench',
            'total': totales_categoria.get('Herramientas', 0),
        },
        {
            'nombre': 'Construcción',
            'descripcion': 'Materiales esenciales para obras, montajes y terminaciones.',
            'icono': 'fa-helmet-safety',
            'total': totales_categoria.get('Construcción', 0),
        },
        {
            'nombre': 'Pinturas',
            'descripcion': 'Color, protección y terminaciones para interior y exterior.',
            'icono': 'fa-paint-roller',
            'total': totales_categoria.get('Pinturas', 0),
        },
    ]
    return render(request, 'home/index.html', {
        'productos_destacados': productos_destacados,
        'categorias_destacadas': categorias_destacadas,
        'total_productos': productos_activos.count(),
        'total_categorias': len([total for total in totales_categoria.values() if total]),
    })

@user_passes_test(lambda u: u.is_staff, login_url='/usuarios/iniciosesion/')
def panel_administracion(request):
    Usuario = get_user_model()
    productos = Producto.objects.all()
    productos_activos = productos.filter(activo=True)
    ventas_pagadas = Venta.objects.filter(estado_venta='pagado', eliminado=False)
    ingresos = ventas_pagadas.aggregate(total=Sum('total_venta'))['total'] or 0
    fichas_calculo = sum(producto.apto_para_calculo for producto in productos_activos)
    inicio_movimientos = timezone.now() - timedelta(days=30)
    movimientos_periodo = MovimientoInventario.objects.filter(
        creado_en__gte=inicio_movimientos,
        estado=MovimientoInventario.Estado.APLICADO,
    )
    entradas_periodo = movimientos_periodo.filter(
        tipo=MovimientoInventario.Tipo.ENTRADA,
    ).aggregate(total=Coalesce(Sum('entrada'), 0))['total']
    salidas_ventas_periodo = movimientos_periodo.filter(
        tipo=MovimientoInventario.Tipo.SALIDA,
        origen=MovimientoInventario.Origen.VENTA,
    ).aggregate(total=Coalesce(Sum('salida'), 0))['total']
    ajustes_periodo = movimientos_periodo.filter(
        origen=MovimientoInventario.Origen.AJUSTE_MANUAL,
    ).count()
    detalles_reposicion_pendientes = DetalleSolicitudReposicion.objects.filter(
        solicitud__estado__in=['enviada', 'parcial'],
    ).annotate(recibidas=Coalesce(Sum('detalles_recepcion__cantidad_recibida'), 0))
    unidades_reposicion_pendientes = sum(
        max(detalle.cantidad_solicitada - detalle.recibidas, 0)
        for detalle in detalles_reposicion_pendientes
    )

    resumen = {
        'productos_activos': productos_activos.count(),
        'fichas_calculo': fichas_calculo,
        'productos_inactivos': productos.filter(activo=False).count(),
        'stock_bajo': productos_activos.filter(stock__gt=0, stock__lte=F('stock_minimo')).count(),
        'sin_stock': productos_activos.filter(stock=0).count(),
        'solicitudes_reposicion': SolicitudReposicion.objects.filter(
            estado__in=['pendiente', 'enviada', 'parcial', 'error']
        ).count(),
        'clientes_activos': Usuario.objects.filter(is_active=True, is_staff=False).count(),
        'maestros_activos': PerfilMaestro.objects.filter(
            estado=PerfilMaestro.Estado.APROBADO
        ).count(),
        'maestros_pendientes': PerfilMaestro.objects.filter(
            estado=PerfilMaestro.Estado.PENDIENTE
        ).count(),
        'ventas_pagadas': ventas_pagadas.count(),
        'ingresos': ingresos,
        'ingresos_formateados': f"${ingresos:,.0f}".replace(',', '.'),
        'retiros_pendientes': ventas_pagadas.filter(
            tipo_entrega='retiro', estado_entrega='pendiente'
        ).count(),
        'despachos_pendientes': ventas_pagadas.filter(
            tipo_entrega='despacho', estado_entrega='pendiente'
        ).count(),
        'movimientos_entradas_30d': entradas_periodo,
        'movimientos_salidas_ventas_30d': salidas_ventas_periodo,
        'movimientos_ajustes_30d': ajustes_periodo,
        'movimientos_reposicion_pendiente': unidades_reposicion_pendientes,
    }
    ventas_recientes = ventas_pagadas.select_related('id_usuario').order_by('-fecha_compra')[:5]

    return render(request, 'home/panel_admin.html', {
        'resumen': resumen,
        'ventas_recientes': ventas_recientes,
    })

def contacto(request):
    return render(request, 'home/contacto.html')

def custom_404(request, exception):
    return render(request, '404.html', status=404)
