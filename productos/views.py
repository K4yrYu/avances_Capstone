from django.shortcuts import render, get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from .models import Producto, HistorialPrecio
from .serializers import ProductoSerializer
from rest_framework.permissions import AllowAny, BasePermission
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.db.models import OuterRef, Subquery, F
from carro_compras.models import Venta, Detalle  # Asegúrate de importar esto arriba


#--------------------GET-----------------------

# Vista HTML
def vista_ofertas(request):
    return render(request, 'productos/ofertas.html')


def lista_productos(request):
    return render(request, 'productos/lista_productos.html')

# Vista API (muestra los productos en formato JSON)
@api_view(['GET'])
@permission_classes([AllowAny])
def api_lista_productos(request):
    productos = Producto.objects.filter(activo=True)  # Solo los activos
    serializer = ProductoSerializer(productos, many=True)  # Serializa los productos
    return Response(serializer.data)  # Devuelve los productos en formato JSON

#--------------------POST----------------------
class EsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_staff

def es_admin(user):
    return user.is_authenticated and user.is_staff

@user_passes_test(es_admin)
def formulario_producto(request):
    return render(request, 'productos/formulario_producto.html')

@api_view(['POST'])
@permission_classes([EsAdmin])
def api_agregar_producto(request):
    serializer = ProductoSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



def detalle_producto(request, id):
    productos = Producto.objects.all()
    if not request.user.is_staff:
        productos = productos.filter(activo=True)
    producto = get_object_or_404(productos, id=id)

    productos_en_carrito = []
    if request.user.is_authenticated:
        carrito = Venta.objects.filter(id_usuario=request.user, estado_venta='carrito').first()
        if carrito:
            productos_en_carrito = Detalle.objects.filter(id_venta=carrito).values_list('producto_id', flat=True)

    return render(request, 'productos/detalle.html', {
        'producto': producto,
        'productos_en_carrito': productos_en_carrito
    })
#--------------------------------


@require_http_methods(["PATCH"])
@login_required(login_url='/usuarios/iniciosesion/')
def api_toggle_activo_producto(request, id):
    if not request.user.is_staff:
        return JsonResponse({'error': 'No tienes permisos para modificar productos.'}, status=403)

    try:
        producto = Producto.objects.get(id=id)
        producto.activo = not producto.activo
        producto.save()
        return JsonResponse({'mensaje': 'Estado del producto actualizado correctamente', 'activo': producto.activo}, status=200)
    except Producto.DoesNotExist:
        return JsonResponse({'error': 'Producto no encontrado'}, status=404)


    
    # Usar el decorador para proteger la vista
@user_passes_test(es_admin, login_url='/')  # Redirige a la página principal si no es admin
def lista_productos_crud(request):
    return render(request, 'productos/crud_productos.html')

@api_view(['PUT'])
@permission_classes([EsAdmin])
def api_editar_producto(request, id):
    producto = get_object_or_404(Producto, id=id)
    serializer = ProductoSerializer(producto, data=request.data, partial=True)
    if serializer.is_valid():
        precio_anterior = producto.precio
        with transaction.atomic():
            producto = serializer.save()
            if producto.precio != precio_anterior:
                HistorialPrecio.objects.create(
                    producto=producto,
                    precio_anterior=precio_anterior,
                    precio_nuevo=producto.precio,
                )
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)




# Vista protegida: solo accesible por administradores
@user_passes_test(es_admin, login_url='/usuarios/iniciosesion/')
def editar_producto(request, id):
    producto = get_object_or_404(Producto, id=id)
    return render(request, 'productos/editar_producto.html', {
        'producto': producto
    })
@api_view(['GET'])
@permission_classes([AllowAny])
def api_ofertas(request):
    from django.db.models import OuterRef, Subquery, F
    from .models import Producto, HistorialPrecio

    ultimos = HistorialPrecio.objects.filter(
        producto=OuterRef('pk')
    ).order_by('-fecha')

    productos_con_descuento = Producto.objects.filter(activo=True).annotate(
        precio_anterior=Subquery(ultimos.values('precio_anterior')[:1]),
        precio_nuevo=Subquery(ultimos.values('precio_nuevo')[:1])
    ).filter(precio_anterior__gt=F('precio_nuevo'))

    resultado = []
    for p in productos_con_descuento:
        resultado.append({
            'id': p.id,
            'nombre': p.nombre,
            'descripcion': p.descripcion,
            'precio': p.precio,
            'imagen': p.imagen,
            'precio_anterior': getattr(p, 'precio_anterior', None),
            'stock': p.stock  # ✅ se agrega aquí
        })

    return Response(resultado)

@api_view(['GET'])
@permission_classes([EsAdmin])
def api_lista_productos_admin(request):
    productos = Producto.objects.all()
    serializer = ProductoSerializer(productos, many=True)
    return Response(serializer.data)
