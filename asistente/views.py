from django.conf import settings
from django.shortcuts import render
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from productos.models import Producto

from .serializers import AnalisisFotoPinturaSerializer, ConsultaAsistenteSerializer
from .services import AsistenteNoDisponible, procesar_consulta
from .services.analisis_foto import analizar_foto_pintura
from .services.recomendacion_colores import color_publico, pinturas_compatibles
from .throttles import AsistenteRateThrottle


def asistente_sfi(request):
    return render(request, 'asistente/asistente.html', {
        'ia_configurada': bool(settings.GEMINI_API_KEY),
    })


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AsistenteRateThrottle])
def api_consultar_asistente(request):
    entrada = ConsultaAsistenteSerializer(data=request.data)
    entrada.is_valid(raise_exception=True)
    try:
        resultado = procesar_consulta(
            entrada.validated_data['mensaje'],
            entrada.validated_data['historial'],
        )
    except AsistenteNoDisponible as exc:
        return Response(
            {'detail': str(exc), 'configuracion_pendiente': not bool(settings.GEMINI_API_KEY)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return Response(resultado)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([AsistenteRateThrottle])
def api_analizar_foto_pintura(request):
    entrada = AnalisisFotoPinturaSerializer(data=request.data)
    entrada.is_valid(raise_exception=True)
    producto = None
    if entrada.validated_data.get('producto_id'):
        producto = Producto.objects.get(pk=entrada.validated_data['producto_id'])
    try:
        analisis = analizar_foto_pintura(
            entrada.validated_data['imagen'],
            entrada.validated_data['color_hex'],
            producto,
        )
    except AsistenteNoDisponible as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    contexto = analisis.get('contexto_pintura', 'no_determinado')
    recomendaciones = (
        [color_publico(item) for item in pinturas_compatibles(contexto, limite=4)]
        if contexto in {'interior', 'exterior', 'piscina'} else []
    )
    return Response({
        'analisis': analisis,
        'contexto_pintura': contexto,
        'colores_recomendados': recomendaciones,
        'pintura': {
            'id': producto.id,
            'nombre': producto.nombre,
            'color': producto.color,
            'color_hex': producto.color_hex,
            'precio': producto.precio,
            'url': f'/productos/{producto.id}/',
        } if producto else None,
        'imagen_guardada': False,
    })
