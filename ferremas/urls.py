from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('home.urls')),  # Ruta para la aplicación de inicio
    path('', include('productos.urls')),  # Incluye las rutas de la app productos
    path('', include('usuarios.urls')),  # Incluye las rutas de la app usuarios
    path('', include('carro_compras.urls')),
    path('', include('asistente.urls')),
    path('', include('maestros.urls')),
    path('', include('movimientos.urls')),
]

handler404 = 'home.views.custom_404'  # Añade esta línea

# Las fotografías del catálogo son contenido público y deben estar
# disponibles aunque DEBUG esté desactivado. El resto de MEDIA permanece
# cerrado fuera del entorno de desarrollo.
urlpatterns += [
    re_path(
        r'^media/productos/(?P<path>.*)$',
        serve,
        {'document_root': settings.MEDIA_ROOT / 'productos'},
        name='media_productos_publicos',
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
