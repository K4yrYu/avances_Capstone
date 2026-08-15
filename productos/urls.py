from django.urls import path
from . import views

urlpatterns = [
    path('productos/<int:id>/', views.detalle_producto, name='detalle_producto'),
    path('productos/', views.lista_productos, name='lista_productos'),
    path('productos/calculadora-pintura/', views.calculadora_pintura, name='calculadora_pintura'),
    path('productos/api/calcular-pintura/', views.api_calcular_pintura, name='api_calcular_pintura'),
    path('productos/crud/', views.lista_productos_crud, name='lista_productos_crud'),
    path('productos/api/', views.api_lista_productos, name='api_lista_productos'),
    path('productos/api/agregar/', views.api_agregar_producto, name='api_agregar_producto'),
    path('productos/formulario/', views.formulario_producto, name='formulario_producto'),
    path('productos/api/editar/<int:id>/', views.api_editar_producto, name='api_editar_producto'),
    path('productos/editar/<int:id>/', views.editar_producto, name='editar_producto'),
    path('productos/ofertas/', views.vista_ofertas, name='vista_ofertas'),
    path('productos/api/ofertas/', views.api_ofertas, name='api_ofertas'),
    path('productos/api/toggle-activo/<int:id>/', views.api_toggle_activo_producto, name='api_toggle_activo_producto'),
    path('productos/api/admin/', views.api_lista_productos_admin, name='api_lista_productos_admin'),
    path('administracion/reposicion/', views.gestion_reposicion, name='gestion_reposicion'),
    path('administracion/proveedores/', views.gestion_proveedores, name='gestion_proveedores'),
    path('administracion/reposicion/proveedor/', views.guardar_proveedor, name='crear_proveedor'),
    path('administracion/reposicion/proveedor/<int:id>/', views.guardar_proveedor, name='editar_proveedor'),
    path('administracion/reposicion/solicitar/', views.crear_solicitud_reposicion, name='crear_solicitud_reposicion'),
    path('administracion/reposicion/<int:id>/reenviar/', views.reenviar_solicitud_reposicion, name='reenviar_solicitud_reposicion'),
    path('administracion/reposicion/<int:id>/recibir/', views.recibir_solicitud_reposicion, name='recibir_solicitud_reposicion'),



]
