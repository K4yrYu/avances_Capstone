import logging
import secrets

from django.conf import settings
from django.contrib import messages
from django.core.mail import EmailMultiAlternatives
from django.shortcuts import redirect, render, get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from .forms import ProveedorForm
from .models import (
    DetalleRecepcionReposicion,
    DetalleSolicitudReposicion,
    HistorialPrecio,
    Producto,
    Proveedor,
    RecepcionReposicion,
    SolicitudReposicion,
)
from .serializers import CalculoPinturaEntradaSerializer, ProductoSerializer
from .services import calcular_recomendaciones_pintura
from rest_framework.permissions import AllowAny, BasePermission
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.db.models import OuterRef, Subquery, F, Prefetch, Q, Sum
from carro_compras.models import Venta, Detalle  # Asegúrate de importar esto arriba


logger = logging.getLogger(__name__)


#--------------------GET-----------------------


def _productos_elegibles_reposicion():
    """Productos bajo mínimo o con faltantes en su última recepción."""
    ultimo_detalle = DetalleSolicitudReposicion.objects.filter(
        producto_id=OuterRef('pk'),
    ).order_by('-solicitud__creada_en', '-solicitud_id', '-id')
    productos_con_pedido_en_curso = DetalleSolicitudReposicion.objects.filter(
        solicitud__estado__in=['pendiente', 'error', 'enviada'],
    ).values('producto_id')
    return Producto.objects.filter(activo=True).annotate(
        ultima_solicitud_estado=Subquery(
            ultimo_detalle.values('solicitud__estado')[:1]
        ),
        ultimo_detalle_solicitud_id=Subquery(ultimo_detalle.values('id')[:1]),
    ).filter(
        Q(stock__lte=F('stock_minimo')) | Q(ultima_solicitud_estado='parcial'),
    ).exclude(pk__in=productos_con_pedido_en_curso)


def _asignar_cantidades_alerta(productos):
    ids_detalle = [
        producto.ultimo_detalle_solicitud_id
        for producto in productos
        if producto.ultima_solicitud_estado == 'parcial'
        and producto.ultimo_detalle_solicitud_id
    ]
    detalles = DetalleSolicitudReposicion.objects.filter(
        pk__in=ids_detalle,
    ).prefetch_related('detalles_recepcion')
    detalles_por_id = {detalle.pk: detalle for detalle in detalles}
    for producto in productos:
        cantidad = producto.cantidad_reposicion_sugerida
        if producto.ultima_solicitud_estado == 'parcial':
            detalle = detalles_por_id.get(producto.ultimo_detalle_solicitud_id)
            if detalle:
                recibido = sum(
                    recepcion.cantidad_recibida
                    for recepcion in detalle.detalles_recepcion.all()
                )
                cantidad = max(detalle.cantidad_solicitada - recibido, 1)
        producto.cantidad_alerta_sugerida = cantidad

# Vista HTML
def vista_ofertas(request):
    return render(request, 'productos/ofertas.html')


def lista_productos(request):
    return render(request, 'productos/lista_productos.html')


def _pinturas_calculables():
    return Producto.objects.filter(
        activo=True,
        tipo_calculo='pintura',
        informacion_tecnica_verificada=True,
        contenido__gt=0,
        rendimiento__gt=0,
        capas_recomendadas__isnull=False,
        unidad_contenido='l',
        unidad_rendimiento='m2_l',
    ).exclude(
        ambiente_uso='no_aplica',
    ).exclude(
        superficies_compatibles=[],
    ).exclude(
        tipo_pintura='no_aplica',
    ).exclude(
        terminacion='no_aplica',
    ).exclude(
        propiedades_pintura=[],
    ).exclude(
        preparaciones_recomendadas=[],
    ).exclude(repintado_min_horas__isnull=True)


def calculadora_pintura(request):
    pinturas_validas = _pinturas_calculables()
    colores = pinturas_validas.exclude(color='').values_list(
        'color', flat=True
    ).distinct().order_by('color')
    return render(request, 'productos/calculadora_pintura.html', {
        'colores': colores,
        'ambientes_calculadora': [
            opcion for opcion in Producto.AMBIENTE_USO_CHOICES if opcion[0] != 'no_aplica'
        ],
        'superficies_calculadora': Producto.SUPERFICIE_CHOICES,
        'estados_superficie': Producto.ESTADO_SUPERFICIE_CHOICES,
        'terminaciones_calculadora': [
            ('cualquiera', 'Sin preferencia'),
            *[
                opcion for opcion in Producto.TERMINACION_CHOICES
                if opcion[0] != 'no_aplica'
            ],
        ],
        'total_pinturas_calculables': pinturas_validas.count(),
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def api_calcular_pintura(request):
    entrada = CalculoPinturaEntradaSerializer(data=request.data)
    entrada.is_valid(raise_exception=True)
    datos = entrada.validated_data
    recomendaciones = calcular_recomendaciones_pintura(
        superficie=datos['superficie'],
        capas=datos.get('capas'),
        desperdicio=datos.get('desperdicio'),
        color=datos.get('color', ''),
        ambiente=datos['ambiente'],
        tipo_superficie=datos['tipo_superficie'],
        estado_superficie=datos['estado_superficie'],
        terminacion=datos['terminacion'],
    )
    return Response({
        'consulta': {
            'superficie_m2': datos['superficie'],
            'capas_personalizadas': datos.get('capas'),
            'desperdicio_personalizado': datos.get('desperdicio'),
            'color': datos.get('color', ''),
            'ambiente': datos['ambiente'],
            'ambiente_display': dict(Producto.AMBIENTE_USO_CHOICES)[datos['ambiente']],
            'tipo_superficie': datos['tipo_superficie'],
            'tipo_superficie_display': dict(Producto.SUPERFICIE_CHOICES)[datos['tipo_superficie']],
            'estado_superficie': datos['estado_superficie'],
            'estado_superficie_display': dict(Producto.ESTADO_SUPERFICIE_CHOICES)[datos['estado_superficie']],
            'terminacion': datos['terminacion'],
            'terminacion_display': dict([
                ('cualquiera', 'Sin preferencia'),
                *[
                    opcion for opcion in Producto.TERMINACION_CHOICES
                    if opcion[0] != 'no_aplica'
                ],
            ])[datos['terminacion']],
        },
        'total_resultados': len(recomendaciones),
        'recomendaciones': recomendaciones,
    })

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

@user_passes_test(es_admin, login_url='/usuarios/iniciosesion/')
def formulario_producto(request):
    try:
        proveedor_id = int(request.GET.get('proveedor', ''))
    except (TypeError, ValueError):
        proveedor_id = None
    proveedor_preseleccionado = Proveedor.objects.filter(
        pk=proveedor_id, activo=True
    ).first() if proveedor_id else None
    return render(request, 'productos/formulario_producto.html', {
        'categorias': Producto.CATEGORIA_CHOICES,
        'unidades_venta': Producto.UNIDAD_VENTA_CHOICES,
        'unidades_contenido': Producto.UNIDAD_CONTENIDO_CHOICES,
        'tipos_calculo': Producto.TIPO_CALCULO_CHOICES,
        'unidades_rendimiento': Producto.UNIDAD_RENDIMIENTO_CHOICES,
        'ambientes_uso': Producto.AMBIENTE_USO_CHOICES,
        'superficies_compatibles': Producto.SUPERFICIE_CHOICES,
        'tipos_pintura': Producto.TIPO_PINTURA_CHOICES,
        'terminaciones_pintura': Producto.TERMINACION_CHOICES,
        'propiedades_pintura': Producto.PROPIEDAD_PINTURA_CHOICES,
        'preparaciones_pintura': Producto.PREPARACION_CHOICES,
        'proveedores': Proveedor.objects.filter(activo=True),
        'proveedor_preseleccionado': proveedor_preseleccionado,
        'modo_edicion': False,
    })

@api_view(['POST'])
@permission_classes([EsAdmin])
def api_agregar_producto(request):
    from movimientos.contexto import contexto_responsable

    serializer = ProductoSerializer(data=request.data)
    if serializer.is_valid():
        with contexto_responsable(request.user):
            serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



def detalle_producto(request, id):
    productos = Producto.objects.all()
    if not request.user.is_staff:
        productos = productos.filter(activo=True)
    producto = get_object_or_404(productos, id=id)

    producto_en_carrito = False
    if request.user.is_authenticated:
        carrito = Venta.objects.filter(id_usuario=request.user, estado_venta='carrito').first()
        if carrito:
            producto_en_carrito = Detalle.objects.filter(id_venta=carrito, producto=producto).exists()

    return render(request, 'productos/detalle.html', {
        'producto': producto,
        'producto_en_carrito': producto_en_carrito,
    })
#--------------------------------


@require_http_methods(["PATCH"])
@login_required(login_url='/usuarios/iniciosesion/')
def api_toggle_activo_producto(request, id):
    if not request.user.is_staff:
        return JsonResponse({'error': 'No tienes permisos para modificar productos.'}, status=403)

    try:
        from movimientos.contexto import contexto_responsable

        producto = Producto.objects.get(id=id)
        producto.activo = not producto.activo
        with contexto_responsable(request.user):
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
    from movimientos.contexto import contexto_responsable

    producto = get_object_or_404(Producto, id=id)
    serializer = ProductoSerializer(producto, data=request.data, partial=True)
    if serializer.is_valid():
        precio_anterior = producto.precio
        with transaction.atomic():
            with contexto_responsable(request.user):
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
    especificaciones_texto = '\n'.join(
        f'{clave}: {valor}' for clave, valor in producto.especificaciones.items()
    )
    return render(request, 'productos/formulario_producto.html', {
        'producto': producto,
        'categorias': Producto.CATEGORIA_CHOICES,
        'unidades_venta': Producto.UNIDAD_VENTA_CHOICES,
        'unidades_contenido': Producto.UNIDAD_CONTENIDO_CHOICES,
        'tipos_calculo': Producto.TIPO_CALCULO_CHOICES,
        'unidades_rendimiento': Producto.UNIDAD_RENDIMIENTO_CHOICES,
        'ambientes_uso': Producto.AMBIENTE_USO_CHOICES,
        'superficies_compatibles': Producto.SUPERFICIE_CHOICES,
        'tipos_pintura': Producto.TIPO_PINTURA_CHOICES,
        'terminaciones_pintura': Producto.TERMINACION_CHOICES,
        'propiedades_pintura': Producto.PROPIEDAD_PINTURA_CHOICES,
        'preparaciones_pintura': Producto.PREPARACION_CHOICES,
        'proveedores': Proveedor.objects.filter(activo=True),
        'especificaciones_texto': especificaciones_texto,
        'modo_edicion': True,
    })
@api_view(['GET'])
@permission_classes([AllowAny])
def api_ofertas(request):
    ultimos = HistorialPrecio.objects.filter(
        producto=OuterRef('pk')
    ).order_by('-fecha', '-id')

    productos_con_descuento = Producto.objects.filter(activo=True).annotate(
        precio_anterior=Subquery(ultimos.values('precio_anterior')[:1]),
        precio_nuevo=Subquery(ultimos.values('precio_nuevo')[:1]),
        fecha_oferta=Subquery(ultimos.values('fecha')[:1]),
    ).filter(
        precio_anterior__gt=F('precio'),
        precio_nuevo=F('precio'),
    ).order_by('-fecha_oferta', 'nombre')

    resultado = []
    for p in productos_con_descuento:
        datos_producto = ProductoSerializer(p, context={'request': request}).data
        datos_producto.update({
            'precio_anterior': getattr(p, 'precio_anterior', None),
        })
        resultado.append(datos_producto)

    return Response(resultado)

@api_view(['GET'])
@permission_classes([EsAdmin])
def api_lista_productos_admin(request):
    productos = Producto.objects.select_related('proveedor').all()
    serializer = ProductoSerializer(productos, many=True)
    return Response(serializer.data)


def _enviar_correo_reposicion(solicitud):
    items = list(solicitud.items.select_related('producto').all())
    contexto = {'solicitud': solicitud, 'items': items}
    texto = render_to_string('productos/emails/solicitud_reposicion.txt', contexto)
    html = render_to_string('productos/emails/solicitud_reposicion.html', contexto)
    correo = EmailMultiAlternatives(
        subject=solicitud.asunto,
        body=texto,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[solicitud.email_destino],
    )
    correo.attach_alternative(html, 'text/html')
    try:
        enviados = correo.send(fail_silently=False)
        if enviados != 1:
            raise RuntimeError('El servidor de correo no confirmó el envío.')
    except Exception as exc:
        logger.exception('No fue posible enviar la solicitud de reposición %s', solicitud.pk)
        solicitud.estado = 'error'
        solicitud.error_envio = str(exc)[:1500]
        solicitud.save(update_fields=['estado', 'error_envio'])
        return False

    solicitud.estado = 'enviada'
    solicitud.error_envio = ''
    solicitud.enviada_en = timezone.now()
    solicitud.save(update_fields=['estado', 'error_envio', 'enviada_en'])
    return True


def _enviar_correo_incidencias_reposicion(recepcion):
    detalles = list(
        recepcion.detalles.exclude(
            resultado=DetalleRecepcionReposicion.Resultado.COMPLETO,
        ).select_related('detalle_solicitud__producto')
    )
    if not detalles:
        return True
    contexto = {
        'recepcion': recepcion,
        'solicitud': recepcion.solicitud,
        'detalles': detalles,
    }
    texto = render_to_string('productos/emails/incidencias_reposicion.txt', contexto)
    html = render_to_string('productos/emails/incidencias_reposicion.html', contexto)
    correo = EmailMultiAlternatives(
        subject=f'Incidencias de recepción SFI {recepcion.solicitud.numero}',
        body=texto,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recepcion.solicitud.email_destino],
    )
    correo.attach_alternative(html, 'text/html')
    try:
        enviados = correo.send(fail_silently=False)
        if enviados != 1:
            raise RuntimeError('El servidor de correo no confirmó el envío.')
    except Exception:
        logger.exception(
            'No fue posible notificar las incidencias de la recepción %s',
            recepcion.pk,
        )
        return False
    return True


@user_passes_test(es_admin, login_url='/usuarios/iniciosesion/')
def gestion_reposicion(request):
    productos_alerta = list(
        _productos_elegibles_reposicion().select_related('proveedor').order_by(
            'proveedor__nombre', 'nombre'
        )
    )
    _asignar_cantidades_alerta(productos_alerta)
    solicitudes = SolicitudReposicion.objects.select_related(
        'proveedor', 'creada_por'
    ).prefetch_related(
        'items__producto',
        'recepciones__detalles__detalle_solicitud',
    )
    solicitudes_activas = solicitudes.filter(
        estado__in=['pendiente', 'error', 'enviada'],
    )[:30]
    for solicitud in solicitudes_activas:
        solicitud.token_recepcion = secrets.token_urlsafe(32)
    recepciones_historial = RecepcionReposicion.objects.select_related(
        'solicitud__proveedor', 'recibida_por',
    ).prefetch_related(
        'detalles__detalle_solicitud__producto',
    )[:30]
    proveedores = Proveedor.objects.filter(activo=True).prefetch_related('productos')
    return render(request, 'productos/reposicion.html', {
        'productos_alerta': productos_alerta,
        'solicitudes_activas': solicitudes_activas,
        'recepciones_historial': recepciones_historial,
        'proveedores': proveedores,
        'proveedor_form': ProveedorForm(),
        'total_alertas': len(productos_alerta),
        'sin_stock': sum(producto.stock == 0 for producto in productos_alerta),
        'sin_proveedor': sum(producto.proveedor_id is None for producto in productos_alerta),
        'solicitudes_abiertas': SolicitudReposicion.objects.filter(
            estado__in=['pendiente', 'enviada', 'error']
        ).count(),
    })


def _registrar_pedido_en_movimientos(solicitud):
    from movimientos.models import MovimientoInventario
    from movimientos.services import registrar_evento_reposicion

    for item in solicitud.items.select_related('producto'):
        registrar_evento_reposicion(
            producto_id=item.producto_id,
            tipo=MovimientoInventario.Tipo.SOLICITUD,
            cantidad_solicitada=item.cantidad_solicitada,
            cantidad_pendiente=item.cantidad_solicitada,
            referencia=solicitud.numero,
            proveedor_nombre=solicitud.proveedor.nombre,
            observacion=solicitud.observaciones or 'Pedido enviado al proveedor.',
            responsable=solicitud.creada_por,
            clave_idempotencia=f'reposicion:{solicitud.pk}:item:{item.pk}:solicitud',
        )


@user_passes_test(es_admin, login_url='/usuarios/iniciosesion/')
def gestion_proveedores(request):
    proveedores = Proveedor.objects.prefetch_related(
        Prefetch('productos', queryset=Producto.objects.order_by('categoria', 'nombre'))
    ).order_by('-activo', 'nombre')
    return render(request, 'productos/proveedores.html', {
        'proveedores': proveedores,
        'total_proveedores': proveedores.count(),
        'proveedores_activos': proveedores.filter(activo=True).count(),
        'productos_asignados': Producto.objects.filter(proveedor__isnull=False).count(),
        'productos_sin_proveedor': Producto.objects.filter(proveedor__isnull=True).count(),
    })


@require_http_methods(['POST'])
@user_passes_test(es_admin, login_url='/usuarios/iniciosesion/')
def guardar_proveedor(request, id=None):
    proveedor = get_object_or_404(Proveedor, pk=id) if id else None
    formulario = ProveedorForm(request.POST, instance=proveedor)
    if formulario.is_valid():
        proveedor = formulario.save()
        accion = 'actualizado' if id else 'creado'
        if 'application/json' in request.headers.get('Accept', ''):
            return JsonResponse({
                'id': proveedor.id,
                'nombre': proveedor.nombre,
                'email': proveedor.email,
                'mensaje': f'Proveedor {accion} correctamente.',
            }, status=200 if id else 201)
        messages.success(request, f'Proveedor {accion}: {proveedor.nombre}.')
    else:
        error = next(iter(formulario.errors.values()))[0]
        if 'application/json' in request.headers.get('Accept', ''):
            return JsonResponse({
                'error': str(error),
                'errores': formulario.errors.get_json_data(),
            }, status=400)
        messages.error(request, f'No fue posible guardar el proveedor: {error}')
    destino = 'gestion_proveedores' if request.POST.get('origen') == 'proveedores' else 'gestion_reposicion'
    return redirect(destino)


@require_http_methods(['POST'])
@user_passes_test(es_admin, login_url='/usuarios/iniciosesion/')
def crear_solicitud_reposicion(request):
    try:
        proveedor_id = int(request.POST.get('proveedor_id', ''))
    except (TypeError, ValueError):
        messages.error(request, 'Selecciona un proveedor valido.')
        return redirect('gestion_reposicion')
    proveedor = get_object_or_404(Proveedor, pk=proveedor_id, activo=True)
    ids = request.POST.getlist('productos')
    if not ids:
        messages.error(request, 'Selecciona al menos un producto para solicitar.')
        return redirect('gestion_reposicion')

    productos = list(_productos_elegibles_reposicion().filter(
        pk__in=ids,
        proveedor=proveedor,
    ).order_by('nombre'))
    if len(productos) != len(set(ids)):
        messages.error(request, 'La selección contiene productos que ya no requieren reposición o que ya tienen un pedido en curso.')
        return redirect('gestion_reposicion')

    cantidades = {}
    for producto in productos:
        try:
            cantidad = int(request.POST.get(f'cantidad_{producto.pk}', '0'))
        except (TypeError, ValueError):
            cantidad = 0
        if cantidad < 1 or cantidad > 1_000_000:
            messages.error(request, f'La cantidad para {producto.nombre} no es válida.')
            return redirect('gestion_reposicion')
        cantidades[producto.pk] = cantidad

    observaciones = request.POST.get('observaciones', '').strip()[:2000]
    with transaction.atomic():
        solicitud = SolicitudReposicion.objects.create(
            proveedor=proveedor,
            creada_por=request.user,
            email_destino=proveedor.email,
            asunto='Solicitud de reposición SFI',
            observaciones=observaciones,
        )
        solicitud.asunto = f'Solicitud de reposición SFI {solicitud.numero}'
        solicitud.save(update_fields=['asunto'])
        DetalleSolicitudReposicion.objects.bulk_create([
            DetalleSolicitudReposicion(
                solicitud=solicitud,
                producto=producto,
                cantidad_solicitada=cantidades[producto.pk],
                stock_al_solicitar=producto.stock,
            )
            for producto in productos
        ])

    if _enviar_correo_reposicion(solicitud):
        _registrar_pedido_en_movimientos(solicitud)
        messages.success(request, f'{solicitud.numero} enviada correctamente a {proveedor.email}.')
    else:
        messages.error(request, f'{solicitud.numero} fue guardada, pero el correo no pudo enviarse. Puedes reintentarlo.')
    return redirect('gestion_reposicion')


@require_http_methods(['POST'])
@user_passes_test(es_admin, login_url='/usuarios/iniciosesion/')
def reenviar_solicitud_reposicion(request, id):
    solicitud = get_object_or_404(SolicitudReposicion, pk=id)
    if solicitud.estado not in {'pendiente', 'error'}:
        messages.error(request, 'Esta solicitud no se encuentra disponible para reenvío.')
    elif _enviar_correo_reposicion(solicitud):
        _registrar_pedido_en_movimientos(solicitud)
        messages.success(request, f'{solicitud.numero} reenviada correctamente.')
    else:
        messages.error(request, 'El correo volvió a fallar. Revisa la configuración SMTP o el email del proveedor.')
    return redirect('gestion_reposicion')


@require_http_methods(['POST'])
@user_passes_test(es_admin, login_url='/usuarios/iniciosesion/')
def recibir_solicitud_reposicion(request, id):
    from movimientos.models import MovimientoInventario
    from movimientos.services import registrar_evento_reposicion, registrar_movimiento_stock

    with transaction.atomic():
        solicitud = get_object_or_404(
            SolicitudReposicion.objects.select_for_update(),
            pk=id,
        )
        token_recepcion = request.POST.get('token_recepcion', '').strip()
        if not 20 <= len(token_recepcion) <= 100:
            messages.error(request, 'La confirmación de recepción no es válida. Recarga la página e inténtalo nuevamente.')
            return redirect('gestion_reposicion')
        if RecepcionReposicion.objects.filter(clave_idempotencia=token_recepcion).exists():
            messages.info(request, 'Esta recepción ya fue registrada. No se duplicaron sus movimientos.')
            return redirect('gestion_reposicion')
        if solicitud.estado != 'enviada':
            messages.error(request, 'Esta solicitud no tiene unidades pendientes de recepción.')
            return redirect('gestion_reposicion')

        items = list(solicitud.items.select_for_update().select_related('producto'))
        datos = []
        for item in items:
            recibido_previo = item.detalles_recepcion.aggregate(
                total=Sum('cantidad_recibida')
            )['total'] or 0
            pendiente = max(item.cantidad_solicitada - recibido_previo, 0)
            if not pendiente:
                continue
            resultado = request.POST.get(f'resultado_{item.pk}', '').strip()
            motivo = request.POST.get(f'motivo_{item.pk}', '').strip()[:2000]
            try:
                cantidad = int(request.POST.get(f'cantidad_{item.pk}', '0'))
            except (TypeError, ValueError):
                cantidad = -1
            resultados_validos = DetalleRecepcionReposicion.Resultado.values
            if resultado not in resultados_validos:
                messages.error(request, f'Selecciona el resultado de {item.producto.nombre}.')
                return redirect('gestion_reposicion')
            if cantidad < 0 or cantidad > pendiente:
                messages.error(request, f'La cantidad recibida de {item.producto.nombre} no es válida.')
                return redirect('gestion_reposicion')
            if resultado == DetalleRecepcionReposicion.Resultado.COMPLETO and cantidad != pendiente:
                messages.error(request, f'Para marcar {item.producto.nombre} como completo deben recibirse {pendiente} unidades.')
                return redirect('gestion_reposicion')
            if resultado == DetalleRecepcionReposicion.Resultado.PARCIAL and not 0 < cantidad < pendiente:
                messages.error(request, f'Indica una cantidad parcial válida para {item.producto.nombre}.')
                return redirect('gestion_reposicion')
            if resultado not in {
                DetalleRecepcionReposicion.Resultado.COMPLETO,
                DetalleRecepcionReposicion.Resultado.PARCIAL,
            } and cantidad != 0:
                messages.error(request, f'Las unidades con incidencia de {item.producto.nombre} no pueden ingresar al stock.')
                return redirect('gestion_reposicion')
            if resultado not in {
                DetalleRecepcionReposicion.Resultado.COMPLETO,
                DetalleRecepcionReposicion.Resultado.NO_LLEGO,
            } and len(motivo) < 10:
                messages.error(request, f'Explica en al menos 10 caracteres el problema con {item.producto.nombre}.')
                return redirect('gestion_reposicion')
            datos.append((item, pendiente, cantidad, resultado, motivo))

        if not datos:
            messages.error(request, 'La solicitud ya no tiene productos pendientes.')
            return redirect('gestion_reposicion')

        hay_incidencias = any(resultado != DetalleRecepcionReposicion.Resultado.COMPLETO for _, _, _, resultado, _ in datos)
        recepcion = RecepcionReposicion.objects.create(
            solicitud=solicitud,
            recibida_por=request.user,
            estado=(RecepcionReposicion.Estado.INCIDENCIA if hay_incidencias else RecepcionReposicion.Estado.COMPLETA),
            clave_idempotencia=token_recepcion,
        )
        for item, pendiente, cantidad, resultado, motivo in datos:
            DetalleRecepcionReposicion.objects.create(
                recepcion=recepcion,
                detalle_solicitud=item,
                cantidad_recibida=cantidad,
                resultado=resultado,
                motivo=motivo,
            )
            pendiente_resultante = pendiente - cantidad
            if cantidad:
                registrar_movimiento_stock(
                    producto_id=item.producto_id,
                    tipo=MovimientoInventario.Tipo.ENTRADA,
                    cantidad=cantidad,
                    origen=MovimientoInventario.Origen.REPOSICION,
                    referencia=solicitud.numero,
                    proveedor_nombre=solicitud.proveedor.nombre,
                    observacion=motivo or 'Producto recibido correctamente.',
                    responsable=request.user,
                    cantidad_solicitada=item.cantidad_solicitada,
                    cantidad_pendiente=pendiente_resultante,
                    estado=(MovimientoInventario.Estado.PARCIAL if pendiente_resultante else MovimientoInventario.Estado.APLICADO),
                    clave_idempotencia=f'reposicion:{solicitud.pk}:recepcion:{recepcion.pk}:item:{item.pk}:entrada',
                )
            if resultado != DetalleRecepcionReposicion.Resultado.COMPLETO:
                resultado_texto = dict(
                    DetalleRecepcionReposicion.Resultado.choices
                )[resultado]
                detalle_incidencia = (
                    f'{resultado_texto}: {motivo}' if motivo else resultado_texto
                )
                registrar_evento_reposicion(
                    producto_id=item.producto_id,
                    tipo=MovimientoInventario.Tipo.INCIDENCIA,
                    cantidad_solicitada=item.cantidad_solicitada,
                    cantidad_pendiente=pendiente_resultante,
                    referencia=f'{solicitud.numero} · {detalle_incidencia}',
                    proveedor_nombre=solicitud.proveedor.nombre,
                    observacion=detalle_incidencia,
                    responsable=request.user,
                    estado=MovimientoInventario.Estado.PENDIENTE,
                    clave_idempotencia=f'reposicion:{solicitud.pk}:recepcion:{recepcion.pk}:item:{item.pk}:incidencia',
                )

        quedan_pendientes = any(
            item.cantidad_solicitada > (item.detalles_recepcion.aggregate(total=Sum('cantidad_recibida'))['total'] or 0)
            for item in items
        )
        solicitud.estado = 'parcial' if quedan_pendientes else 'recibida'
        solicitud.recibida_en = None if quedan_pendientes else timezone.now()
        solicitud.save(update_fields=['estado', 'recibida_en'])
        recepcion.estado = (
            RecepcionReposicion.Estado.PARCIAL if quedan_pendientes
            else RecepcionReposicion.Estado.COMPLETA
        )
        recepcion.save(update_fields=['estado'])
    correo_incidencias_enviado = True
    if hay_incidencias:
        correo_incidencias_enviado = _enviar_correo_incidencias_reposicion(recepcion)

    if solicitud.estado == 'recibida':
        messages.success(request, f'{solicitud.numero} recibida completamente. El stock fue actualizado.')
    else:
        messages.error(
            request,
            f'{solicitud.numero} fue cerrada con incidencias. Los productos pendientes volvieron a la lista de compra.',
        )
    if hay_incidencias:
        if correo_incidencias_enviado:
            messages.info(
                request,
                f'Las incidencias fueron notificadas a {solicitud.email_destino}.',
            )
        else:
            messages.error(
                request,
                'La recepción quedó registrada, pero no fue posible enviar la notificación al proveedor.',
            )
    return redirect('gestion_reposicion')
