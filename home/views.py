from django.shortcuts import render
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth import get_user_model
from django.db.models import Count, Sum

from productos.models import Producto
from carro_compras.models import Venta


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

    resumen = {
        'productos_activos': productos_activos.count(),
        'productos_inactivos': productos.filter(activo=False).count(),
        'stock_bajo': productos_activos.filter(stock__gt=0, stock__lte=5).count(),
        'sin_stock': productos_activos.filter(stock=0).count(),
        'clientes_activos': Usuario.objects.filter(is_active=True, is_staff=False).count(),
        'ventas_pagadas': ventas_pagadas.count(),
        'ingresos': ingresos,
        'ingresos_formateados': f"${ingresos:,.0f}".replace(',', '.'),
        'retiros_pendientes': ventas_pagadas.filter(
            tipo_entrega='retiro', estado_entrega='pendiente'
        ).count(),
        'despachos_pendientes': ventas_pagadas.filter(
            tipo_entrega='despacho', estado_entrega='pendiente'
        ).count(),
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
