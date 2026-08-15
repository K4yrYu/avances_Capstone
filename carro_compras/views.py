import logging
import re
import secrets
import time
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from transbank.common.integration_type import IntegrationType
from transbank.common.options import WebpayOptions
from transbank.webpay.webpay_plus.transaction import Transaction

from productos.models import Producto
from productos.services import calcular_producto_pintura
from usuarios.models import Usuario
from .models import Detalle, Venta
from .serializers import (
    CantidadProductoSerializer,
    DetalleCarritoEntradaSerializer,
    RecomendacionPinturaCarritoSerializer,
    VentaSerializer,
)

logger = logging.getLogger(__name__)


class PagoInvalidoError(Exception):
    pass


TOKEN_WEBPAY_RE = re.compile(r'^[A-Za-z0-9_-]{16,100}$')


def _validar_respuesta_creacion_webpay(response):
    if not isinstance(response, dict):
        raise PagoInvalidoError('Respuesta de creación inválida')

    token = str(response.get('token', '')).strip()
    redirect_url = str(response.get('url', '')).strip()
    parsed_url = urlsplit(redirect_url)
    hostname = (parsed_url.hostname or '').lower()

    if not TOKEN_WEBPAY_RE.fullmatch(token):
        raise PagoInvalidoError('Token Webpay inválido')
    if parsed_url.scheme != 'https' or not (
        hostname == 'transbank.cl' or hostname.endswith('.transbank.cl')
    ):
        raise PagoInvalidoError('URL Webpay inválida')

    return token, redirect_url


def _recalcular_total(venta):
    venta.total_venta = sum(detalle.subtotal_venta for detalle in venta.detalles.all())
    venta.save(update_fields=['total_venta'])
    return venta.total_venta


def _webpay_transaction():
    environment = str(settings.TRANSBANK['ENVIRONMENT']).upper()
    integration_type = IntegrationType.LIVE if environment == 'LIVE' else IntegrationType.TEST
    options = WebpayOptions(
        commerce_code=settings.TRANSBANK['COMMERCE_CODE'],
        api_key=settings.TRANSBANK['API_KEY'],
        integration_type=integration_type,
    )
    return Transaction(options)


def _limpiar_datos_webpay(venta, payment_status=''):
    venta.webpay_transaction_id = None
    venta.webpay_amount = None
    venta.webpay_buy_order = None
    venta.webpay_session_id = None
    venta.webpay_payment_status = payment_status


def _reembolsar_y_reabrir_carrito(tx, token, amount, venta_id, reason):
    try:
        tx.refund(token, int(amount))
        refunded = True
    except Exception:
        logger.exception('No se pudo reembolsar automáticamente la venta %s', venta_id)
        refunded = False

    with transaction.atomic():
        venta = Venta.objects.select_for_update().get(id=venta_id)
        if refunded:
            venta.estado_venta = 'carrito'
            _limpiar_datos_webpay(venta, payment_status=f'refunded:{reason}')
        else:
            venta.estado_venta = 'pago_error'
            venta.webpay_payment_status = f'refund_failed:{reason}'
        venta.save()
    return refunded


def _es_admin(user):
    return user.is_authenticated and user.is_staff





def vista_carrito(request):
    if request.user.is_authenticated:
        venta = Venta.objects.filter(id_usuario=request.user, estado_venta='carrito').first()

        if venta:
            detalles = Detalle.objects.filter(id_venta=venta).select_related('producto')
            productos_eliminados = []

            for detalle in detalles:
                producto = detalle.producto
                if producto.stock <= 0 or not producto.activo:
                    productos_eliminados.append(detalle)
                    detalle.delete()
                elif detalle.cantidad_producto > producto.stock:
                    detalle.cantidad_producto = producto.stock
                    detalle.subtotal_venta = producto.precio * producto.stock
                    detalle.save()

            detalles = Detalle.objects.filter(id_venta=venta).select_related('producto')
            total_carrito = sum(d.subtotal_venta for d in detalles)
            venta.total_venta = total_carrito
            venta.save(update_fields=['total_venta'])

            return render(request, 'carro_compras/carrito.html', {
                'detalles': detalles,
                'total_carrito': total_carrito,
                'productos_eliminados': productos_eliminados,
                'aviso': request.GET.get('mensaje', '')[:180],
            })
        else:
            # 👇 Mostrar vista sin productos, sin mensaje personalizado
            return render(request, 'carro_compras/carrito.html', {
                'detalles': [],
                'total_carrito': 0,
                'productos_eliminados': []
            })
    else:
        return render(request, 'carro_compras/carrito.html', {
            'mensaje': 'Por favor, inicia sesión para ver tu carrito.'
        })



# Vista para gestionar el carrito (ver y crear)
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def gestionar_carrito(request):
    if request.method == 'GET':
        venta = Venta.objects.filter(id_usuario=request.user, estado_venta='carrito').first()
        if venta:
            return Response(VentaSerializer(venta).data)
        return Response({"detail": "No hay carrito abierto."}, status=status.HTTP_404_NOT_FOUND)

    detalles_data = request.data.get('detalles', [])
    if not isinstance(detalles_data, list) or not detalles_data:
        return Response({"detail": "Debes incluir al menos un producto."}, status=status.HTTP_400_BAD_REQUEST)

    entrada = DetalleCarritoEntradaSerializer(data=detalles_data, many=True)
    entrada.is_valid(raise_exception=True)
    product_ids = [item['producto'] for item in entrada.validated_data]
    if len(product_ids) != len(set(product_ids)):
        return Response({"detail": "No puedes repetir productos en el carrito."}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        Usuario.objects.select_for_update().get(pk=request.user.pk)
        productos = {
            producto.id: producto
            for producto in Producto.objects.select_for_update().filter(id__in=product_ids, activo=True)
        }
        if len(productos) != len(product_ids):
            return Response({"detail": "Uno o más productos no existen o no están activos."}, status=status.HTTP_400_BAD_REQUEST)

        for item in entrada.validated_data:
            producto = productos[item['producto']]
            cantidad = item['cantidad_producto']
            if cantidad > producto.stock:
                return Response({"detail": f"Stock insuficiente para {producto.nombre}."}, status=status.HTTP_400_BAD_REQUEST)

        venta, created = Venta.objects.select_for_update().get_or_create(
            id_usuario=request.user,
            estado_venta='carrito',
            defaults={'fecha_compra': timezone.now(), 'total_venta': 0},
        )
        if not created and venta.detalles.exists():
            return Response({"detail": "Ya tienes un carrito activo."}, status=status.HTTP_409_CONFLICT)

        for item in entrada.validated_data:
            producto = productos[item['producto']]
            cantidad = item['cantidad_producto']
            Detalle.objects.create(id_venta=venta, producto=producto, cantidad_producto=cantidad)

        _recalcular_total(venta)

    return Response({"message": "Carrito creado exitosamente."}, status=status.HTTP_201_CREATED)

# Vista para agregar productos al carrito
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def agregar_producto_carrito(request):
    entrada = DetalleCarritoEntradaSerializer(data=request.data)
    entrada.is_valid(raise_exception=True)

    with transaction.atomic():
        Usuario.objects.select_for_update().get(pk=request.user.pk)
        producto = get_object_or_404(
            Producto.objects.select_for_update(),
            id=entrada.validated_data['producto'],
            activo=True,
        )
        cantidad = entrada.validated_data['cantidad_producto']
        if cantidad > producto.stock:
            return Response({"detail": f"Solo hay {producto.stock} unidades disponibles."}, status=status.HTTP_400_BAD_REQUEST)

        venta, _ = Venta.objects.select_for_update().get_or_create(
            id_usuario=request.user,
            estado_venta='carrito',
            defaults={'fecha_compra': timezone.now(), 'total_venta': 0},
        )
        if venta.detalles.filter(producto=producto).exists():
            return Response({"detail": "Este producto ya está en tu carrito."}, status=status.HTTP_400_BAD_REQUEST)

        Detalle.objects.create(id_venta=venta, producto=producto, cantidad_producto=cantidad)
        _recalcular_total(venta)

    return Response({"message": "Producto agregado al carrito exitosamente."})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def agregar_calculo_pintura_carrito(request):
    """Recalcula la recomendacion en el servidor antes de modificar el carrito."""
    entrada = RecomendacionPinturaCarritoSerializer(data=request.data)
    entrada.is_valid(raise_exception=True)
    datos = entrada.validated_data

    with transaction.atomic():
        Usuario.objects.select_for_update().get(pk=request.user.pk)
        producto = get_object_or_404(
            Producto.objects.select_for_update(),
            pk=datos['producto'],
            activo=True,
        )
        calculo = calcular_producto_pintura(
            producto=producto,
            superficie=datos['superficie'],
            capas=datos.get('capas'),
            desperdicio=datos.get('desperdicio'),
            ambiente=datos['ambiente'],
            tipo_superficie=datos['tipo_superficie'],
            estado_superficie=datos['estado_superficie'],
            terminacion=datos['terminacion'],
        )
        if calculo is None:
            return Response(
                {'detail': 'Este producto no tiene una ficha de pintura valida.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cantidad = calculo['cantidad_envases']
        if cantidad > producto.stock:
            return Response({
                'detail': (
                    f'Stock insuficiente para la recomendacion. '
                    f'Necesitas {cantidad} envases y hay {producto.stock} disponibles.'
                ),
                'cantidad_necesaria': cantidad,
                'stock_disponible': producto.stock,
            }, status=status.HTTP_400_BAD_REQUEST)

        venta, _ = Venta.objects.select_for_update().get_or_create(
            id_usuario=request.user,
            estado_venta='carrito',
            defaults={'fecha_compra': timezone.now(), 'total_venta': 0},
        )
        detalle = venta.detalles.select_for_update().filter(producto=producto).first()
        if detalle:
            detalle.cantidad_producto = cantidad
            detalle.nombre_producto = producto.nombre
            detalle.precio_unitario = producto.precio
            detalle.imagen_producto = producto.imagen.url if producto.imagen else None
            detalle.save(update_fields=[
                'cantidad_producto', 'nombre_producto', 'precio_unitario',
                'imagen_producto', 'subtotal_venta',
            ])
        else:
            Detalle.objects.create(
                id_venta=venta,
                producto=producto,
                cantidad_producto=cantidad,
            )

        total = _recalcular_total(venta)

    return Response({
        'message': f'Se agregaron {cantidad} envases de {producto.nombre} al carrito.',
        'cantidad_producto': cantidad,
        'total_carrito': total,
        'redirect_url': reverse('vista_carrito'),
    })


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def actualizar_cantidad_producto(request, detalle_id):
    entrada = CantidadProductoSerializer(data=request.data)
    entrada.is_valid(raise_exception=True)

    with transaction.atomic():
        detalle = get_object_or_404(
            Detalle.objects.select_for_update().select_related('producto', 'id_venta'),
            id=detalle_id,
            id_venta__id_usuario=request.user,
            id_venta__estado_venta='carrito',
        )
        cantidad_nueva = entrada.validated_data['cantidad_producto']
        if not detalle.producto.activo or cantidad_nueva > detalle.producto.stock:
            return Response({"detail": f"Solo hay {detalle.producto.stock} unidades disponibles."}, status=status.HTTP_400_BAD_REQUEST)

        detalle.cantidad_producto = cantidad_nueva
        detalle.save(update_fields=['cantidad_producto', 'subtotal_venta'])
        venta = detalle.id_venta
        _recalcular_total(venta)

    return Response({"subtotal_venta": detalle.subtotal_venta, "total_carrito": venta.total_venta})



# Vista para disminuir la cantidad de un producto
@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def disminuir_cantidad_producto(request, detalle_id):
    with transaction.atomic():
        detalle = get_object_or_404(
            Detalle.objects.select_for_update().select_related('id_venta'),
            id=detalle_id,
            id_venta__id_usuario=request.user,
            id_venta__estado_venta='carrito',
        )
        venta = detalle.id_venta
        if detalle.cantidad_producto == 1:
            detalle.delete()
            _recalcular_total(venta)
            return Response({"message": "Producto eliminado del carrito.", "total_carrito": venta.total_venta})

        detalle.cantidad_producto -= 1
        detalle.save(update_fields=['cantidad_producto', 'subtotal_venta'])
        _recalcular_total(venta)

    return Response({"subtotal_venta": detalle.subtotal_venta, "total_carrito": venta.total_venta})
#####################


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def iniciar_pago_webpay(request):
    tipo_entrega = str(request.data.get('tipo_entrega', '')).strip().lower()
    direccion_despacho = str(request.data.get('direccion_despacho', '')).strip()
    if tipo_entrega not in {'retiro', 'despacho'}:
        return Response({'error': 'Selecciona un tipo de entrega válido.'}, status=status.HTTP_400_BAD_REQUEST)
    if tipo_entrega == 'despacho' and not (10 <= len(direccion_despacho) <= 500):
        return Response({'error': 'Ingresa una dirección de despacho válida.'}, status=status.HTTP_400_BAD_REQUEST)
    if tipo_entrega == 'retiro':
        direccion_despacho = ''

    with transaction.atomic():
        venta = Venta.objects.select_for_update().filter(
            id_usuario=request.user,
            estado_venta='carrito',
        ).first()
        if not venta:
            return Response({'error': 'No tienes un carrito activo.'}, status=status.HTTP_404_NOT_FOUND)

        detalles = list(venta.detalles.select_related('producto').all())
        if not detalles:
            return Response({'error': 'No puedes pagar un carrito vacío.'}, status=status.HTTP_400_BAD_REQUEST)

        for detalle in detalles:
            if not detalle.producto.activo or detalle.cantidad_producto > detalle.producto.stock:
                return Response(
                    {'error': f'Stock insuficiente para {detalle.nombre_producto}.'},
                    status=status.HTTP_409_CONFLICT,
                )

        total = sum(detalle.subtotal_venta for detalle in detalles)
        if total <= 0:
            return Response({'error': 'El total de la compra no es válido.'}, status=status.HTTP_400_BAD_REQUEST)

        buy_order = f"F{venta.id}-{int(time.time())}"[:26]
        session_id = secrets.token_urlsafe(24)[:61]
        venta.total_venta = total
        venta.tipo_entrega = tipo_entrega
        venta.direccion_despacho = direccion_despacho
        venta.estado_venta = 'pago_pendiente'
        venta.webpay_amount = total
        venta.webpay_buy_order = buy_order
        venta.webpay_session_id = session_id
        venta.webpay_payment_status = 'initializing'
        venta.save()

    tx = _webpay_transaction()
    token = None
    try:
        response = tx.create(
            buy_order=buy_order,
            session_id=session_id,
            amount=total,
            return_url=request.build_absolute_uri('/api/webpay/respuesta/'),
        )
        token, redirect_url = _validar_respuesta_creacion_webpay(response)
    except PagoInvalidoError as exc:
        logger.warning('Webpay devolvió datos de inicio inválidos para la venta %s: %s', venta.id, exc)
    except Exception:
        logger.exception('No se pudo iniciar Webpay para la venta %s', venta.id)

    if token is None:
        with transaction.atomic():
            venta = Venta.objects.select_for_update().get(id=venta.id)
            if venta.estado_venta == 'pago_pendiente' and venta.webpay_buy_order == buy_order:
                venta.estado_venta = 'carrito'
                _limpiar_datos_webpay(venta, payment_status='create_failed')
                venta.save()
        return Response({'error': 'No fue posible iniciar el pago. Intenta nuevamente.'}, status=status.HTTP_502_BAD_GATEWAY)

    with transaction.atomic():
        venta = Venta.objects.select_for_update().get(id=venta.id)
        if venta.estado_venta != 'pago_pendiente' or venta.webpay_buy_order != buy_order:
            return Response({'error': 'La venta cambió mientras se iniciaba el pago.'}, status=status.HTTP_409_CONFLICT)
        venta.webpay_transaction_id = token
        venta.webpay_payment_status = 'pending'
        venta.save(update_fields=['webpay_transaction_id', 'webpay_payment_status'])

    request.session['venta_webpay_pendiente'] = venta.id
    separator = '&' if urlsplit(redirect_url).query else '?'
    payment_url = f"{redirect_url}{separator}{urlencode({'token_ws': token})}"
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return Response({'redirect_url': payment_url})
    return redirect(payment_url)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancelar_pago_webpay(request):
    venta_id = request.session.pop('venta_webpay_pendiente', None)
    if not venta_id:
        return Response({'cancelled': False})

    with transaction.atomic():
        venta = Venta.objects.select_for_update().filter(
            id=venta_id,
            id_usuario=request.user,
            estado_venta='pago_pendiente',
        ).first()
        if not venta:
            return Response({'cancelled': False})

        venta.estado_venta = 'carrito'
        _limpiar_datos_webpay(venta, payment_status='cancelled_by_navigation')
        venta.save()

    return Response({'cancelled': True})
    
@csrf_exempt
@require_http_methods(["GET", "POST"])
def respuesta_pago_webpay(request):
    token = request.POST.get("token_ws") or request.GET.get("token_ws")

    if not token:
        venta_id = request.session.pop('venta_webpay_pendiente', None)
        if venta_id:
            with transaction.atomic():
                venta = Venta.objects.select_for_update().filter(
                    id=venta_id,
                    id_usuario=request.user if request.user.is_authenticated else None,
                    estado_venta='pago_pendiente',
                ).first()
                if venta:
                    venta.estado_venta = 'carrito'
                    _limpiar_datos_webpay(venta, payment_status='cancelled')
                    venta.save()
        return redirect('/carrito/?mensaje=Transacción cancelada.')

    if not TOKEN_WEBPAY_RE.fullmatch(str(token)):
        return HttpResponse('Token de transacción inválido.', status=400)

    venta_previa = Venta.objects.filter(webpay_transaction_id=token).first()
    if not venta_previa:
        return HttpResponse('La transacción no corresponde a una venta válida.', status=400)
    if venta_previa.estado_venta == 'pagado':
        return render(request, 'carro_compras/webpay_respuesta.html', {
            'mensaje': '✅ Pago ya confirmado',
            'venta': venta_previa,
        })

    tx = _webpay_transaction()
    try:
        response = tx.commit(token)
    except Exception:
        logger.exception('Error al confirmar Webpay para la venta %s', venta_previa.id)
        return HttpResponse('No fue posible confirmar el pago. La venta quedó pendiente de revisión.', status=502)

    if not isinstance(response, dict):
        logger.error('Webpay devolvió una respuesta inválida para la venta %s', venta_previa.id)
        return HttpResponse('La respuesta del pago no fue válida. La venta quedó pendiente de revisión.', status=502)

    try:
        response_code = int(response.get('response_code', -1))
    except (TypeError, ValueError):
        response_code = -1

    if response.get('status') != 'AUTHORIZED' or response_code != 0:
        with transaction.atomic():
            venta = Venta.objects.select_for_update().get(id=venta_previa.id)
            if venta.estado_venta == 'pago_pendiente' and venta.webpay_transaction_id == token:
                venta.estado_venta = 'carrito'
                _limpiar_datos_webpay(venta, payment_status='rejected')
                venta.save()
        request.session.pop('venta_webpay_pendiente', None)
        return render(request, 'carro_compras/webpay_respuesta.html', {
            'mensaje': '❌ Pago rechazado',
            'venta': venta_previa,
        })

    try:
        response_amount = Decimal(str(response.get('amount')))
        expected_amount = Decimal(str(venta_previa.webpay_amount))
    except (InvalidOperation, TypeError):
        response_amount = Decimal('-1')
        expected_amount = Decimal(str(venta_previa.webpay_amount or 0))

    response_matches = all([
        response.get('buy_order') == venta_previa.webpay_buy_order,
        response.get('session_id') == venta_previa.webpay_session_id,
        response_amount == expected_amount,
    ])
    if not response_matches:
        _reembolsar_y_reabrir_carrito(tx, token, response.get('amount', 0), venta_previa.id, 'integrity_mismatch')
        return HttpResponse('El pago fue revertido porque los datos de la transacción no coincidían.', status=409)

    try:
        with transaction.atomic():
            venta = Venta.objects.select_for_update().get(id=venta_previa.id)
            if venta.estado_venta == 'pagado':
                return render(request, 'carro_compras/webpay_respuesta.html', {
                    'mensaje': '✅ Pago ya confirmado',
                    'venta': venta,
                })
            if venta.estado_venta != 'pago_pendiente' or venta.webpay_transaction_id != token:
                raise PagoInvalidoError('Estado o token inesperado')

            detalles = list(venta.detalles.select_related('producto').all())
            if not detalles or sum(d.subtotal_venta for d in detalles) != venta.webpay_amount:
                raise PagoInvalidoError('El carrito cambió durante el pago')

            productos = {
                producto.id: producto
                for producto in Producto.objects.select_for_update().filter(
                    id__in=[detalle.producto_id for detalle in detalles]
                ).order_by('id')
            }
            for detalle in detalles:
                producto = productos.get(detalle.producto_id)
                if not producto or not producto.activo or producto.stock < detalle.cantidad_producto:
                    raise PagoInvalidoError('Stock insuficiente al confirmar')

            for detalle in detalles:
                producto = productos[detalle.producto_id]
                producto.stock -= detalle.cantidad_producto
                producto.save(update_fields=['stock'])

            venta.estado_entrega = 'pendiente'
            venta.estado_venta = 'pagado'
            venta.fecha_compra = timezone.now()
            venta.webpay_payment_status = 'completed'
            card_detail = response.get('card_detail')
            if not isinstance(card_detail, dict):
                card_detail = {}
            venta.ultimos_digitos = str(card_detail.get('card_number', ''))[-4:]
            venta.total_venta = int(venta.webpay_amount)
            venta.save()
    except PagoInvalidoError:
        logger.warning('Pago autorizado revertido por validación local en venta %s', venta_previa.id)
        _reembolsar_y_reabrir_carrito(tx, token, response_amount, venta_previa.id, 'local_validation')
        return HttpResponse('El pago fue revertido porque la compra ya no podía completarse.', status=409)
    except Exception:
        logger.exception('Fallo local al finalizar la venta %s; se intentará revertir', venta_previa.id)
        _reembolsar_y_reabrir_carrito(tx, token, response_amount, venta_previa.id, 'local_error')
        return HttpResponse('El pago fue revertido por un error al finalizar la compra.', status=500)

    request.session.pop('venta_webpay_pendiente', None)
    return render(request, 'carro_compras/webpay_respuesta.html', {
        'mensaje': '✅ Pago realizado con éxito',
        'venta': venta,
    })


@login_required
def ver_boleta(request, venta_id):
    venta = get_object_or_404(
        Venta.objects.select_related('id_usuario'),
        id=venta_id,
        estado_venta='pagado',
    )

    # Solo el dueño o un admin puede verla
    if request.user != venta.id_usuario and not request.user.is_staff:
        return HttpResponseForbidden("No tienes permiso para ver esta boleta.")

    detalles = list(Detalle.objects.filter(id_venta=venta).select_related('producto'))
    origen_mis_compras = request.GET.get('origen') == 'mis-compras'
    volver_a_mis_compras = (
        not request.user.is_staff
        or (origen_mis_compras and request.user == venta.id_usuario)
    )
    return render(request, 'carro_compras/boleta.html', {
        'venta': venta,
        'detalles': detalles,
        'cantidad_total': sum(detalle.cantidad_producto for detalle in detalles),
        'volver_a_mis_compras': volver_a_mis_compras,
    })

#############

@user_passes_test(_es_admin, login_url='/usuarios/iniciosesion/')
def vista_retiros(request):
    return render(request, 'carro_compras/retiros.html')

@user_passes_test(_es_admin, login_url='/usuarios/iniciosesion/')
def vista_despachos(request):
    return render(request, 'carro_compras/despachos.html')


@user_passes_test(_es_admin, login_url='/usuarios/iniciosesion/')
def historial_ventas(request):
    return render(request, 'carro_compras/historial_ventas.html')

@login_required
def mi_historial_compras(request):
    ventas = list(Venta.objects.filter(
        id_usuario=request.user,
        estado_venta='pagado',
        eliminado=False,
    ).prefetch_related('detalles__producto').order_by('-fecha_compra'))

    total_unidades = 0
    for venta in ventas:
        venta.detalles_list = list(venta.detalles.all())
        venta.cantidad_unidades = sum(detalle.cantidad_producto for detalle in venta.detalles_list)
        total_unidades += venta.cantidad_unidades

    return render(request, 'carro_compras/mi_historial.html', {
        'ventas': ventas,
        'total_compras': len(ventas),
        'total_gastado': sum(venta.total_venta for venta in ventas),
        'total_unidades': total_unidades,
        'entregas_pendientes': sum(venta.estado_entrega == 'pendiente' for venta in ventas),
    })

@api_view(['GET'])
@permission_classes([IsAdminUser])
def api_historial_ventas(request):
    ventas = Venta.objects.filter(estado_venta='pagado').select_related(
        'id_usuario'
    ).prefetch_related('detalles').order_by('-fecha_compra')
    serializer = VentaSerializer(ventas, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_mis_compras(request):
    ventas = Venta.objects.filter(id_usuario=request.user, estado_venta='pagado').order_by('-fecha_compra')
    serializer = VentaSerializer(ventas, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAdminUser])
def api_retiros(request):
    retiros = Venta.objects.filter(
        tipo_entrega='retiro', estado_venta='pagado'
    ).select_related('id_usuario').prefetch_related('detalles').order_by('-fecha_compra')
    serializer = VentaSerializer(retiros, many=True)
    return Response(serializer.data)

# Confirmar retiro (admin)
@api_view(['POST'])
@permission_classes([IsAdminUser])
def api_confirmar_retiro(request, venta_id):
    rut = str(request.data.get('rut') or '').replace('.', '').replace(' ', '').upper()
    venta = get_object_or_404(
        Venta,
        id=venta_id,
        tipo_entrega='retiro',
        estado_venta='pagado',
        estado_entrega='pendiente',
    )

    rut_cliente = venta.id_usuario.rut.replace('.', '').replace(' ', '').upper()
    if not rut or rut != rut_cliente:
        return Response({'detail': 'El RUT ingresado no corresponde al cliente.'}, status=400)

    venta.estado_entrega = 'completado'
    venta.save()
    return Response({'mensaje': f"Retiro confirmado para la venta #{venta.id}."})

@api_view(['GET'])
@permission_classes([IsAdminUser])
def api_despachos(request):
    despachos = Venta.objects.filter(
        tipo_entrega='despacho', estado_venta='pagado'
    ).select_related('id_usuario').prefetch_related('detalles').order_by('-fecha_compra')
    serializer = VentaSerializer(despachos, many=True)
    return Response(serializer.data)

@api_view(['POST'])
@permission_classes([IsAdminUser])
def api_confirmar_despacho(request, venta_id):
    venta = get_object_or_404(
        Venta,
        id=venta_id,
        tipo_entrega='despacho',
        estado_venta='pagado',
        estado_entrega='pendiente',
    )
    venta.estado_entrega = 'completado'
    venta.save()
    return Response({'mensaje': f"Despacho confirmado para la venta #{venta.id}."})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_boleta(request, id):
    venta = get_object_or_404(Venta, id=id, estado_venta='pagado')

    # Seguridad: solo el dueño o un admin puede verla
    if request.user != venta.id_usuario and not request.user.is_staff:
        return Response({'detail': 'No autorizado'}, status=403)

    serializer = VentaSerializer(venta)
    return Response(serializer.data)
