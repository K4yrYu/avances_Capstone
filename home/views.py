from django.shortcuts import render
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count

from productos.models import Producto


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
    return render(request, 'home/panel_admin.html')

def contacto(request):
    return render(request, 'home/contacto.html')

def custom_404(request, exception):
    return render(request, '404.html', status=404)
