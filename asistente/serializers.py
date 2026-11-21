from rest_framework import serializers

from productos.models import Producto


class MensajeHistorialSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=['user', 'assistant'])
    # Una propuesta completa puede superar 4.000 caracteres. El límite global
    # del historial evita aceptar cargas desmedidas sin rechazar seguimientos
    # legítimos iniciados desde una respuesta extensa.
    content = serializers.CharField(min_length=1, max_length=30000, trim_whitespace=True)


class ProductoContextoSerializer(serializers.Serializer):
    id = serializers.IntegerField(min_value=1)
    carrito_cantidad = serializers.IntegerField(min_value=1, max_value=10000, required=False)
    cantidad_requerida = serializers.FloatField(min_value=0, max_value=100000, required=False)
    rol = serializers.CharField(max_length=100, required=False, allow_blank=True)
    detalle_material = serializers.CharField(max_length=500, required=False, allow_blank=True)
    presentacion_sugerida = serializers.CharField(max_length=300, required=False, allow_blank=True)
    bloquear_carrito = serializers.BooleanField(required=False)
    es_opcional = serializers.BooleanField(required=False)
    es_alternativa = serializers.BooleanField(required=False)
    cantidad_pendiente = serializers.BooleanField(required=False)
    incluido_en_total = serializers.BooleanField(required=False)


class ConsultaAsistenteSerializer(serializers.Serializer):
    mensaje = serializers.CharField(min_length=2, max_length=700, trim_whitespace=True)
    modo_consulta = serializers.ChoiceField(
        choices=['auto', 'producto', 'herramienta', 'proyecto_reparacion', 'problema_cotidiano'],
        required=False,
        default='auto',
    )
    historial = MensajeHistorialSerializer(many=True, required=False, default=list)
    productos_contexto = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        default=list,
        max_length=60,
    )
    estimacion_contexto = ProductoContextoSerializer(
        many=True,
        required=False,
        default=list,
    )

    def validate_historial(self, value):
        if len(value) > 20:
            raise serializers.ValidationError('Solo se permiten los últimos 20 mensajes.')
        if sum(len(item.get('content') or '') for item in value) > 120000:
            raise serializers.ValidationError('El historial de la consulta es demasiado extenso.')
        return value

    def validate_productos_contexto(self, value):
        return list(dict.fromkeys(value))

    def validate_estimacion_contexto(self, value):
        unicos = {}
        for item in value[:60]:
            unicos.setdefault(item['id'], item)
        return list(unicos.values())


class ConfiguracionFotoPinturaSerializer(ConsultaAsistenteSerializer):
    contexto = serializers.ChoiceField(
        choices=['interior', 'exterior', 'piscina', 'no_determinado'],
    )
    producto_id = serializers.IntegerField(min_value=1, required=False)

    def validate_producto_id(self, value):
        if not Producto.objects.filter(
            pk=value,
            activo=True,
            categoria='Pinturas',
            color_hex__gt='',
        ).exists():
            raise serializers.ValidationError('La pintura seleccionada no está disponible.')
        return value

class AnalisisFotoPinturaSerializer(serializers.Serializer):
    imagen = serializers.ImageField(allow_empty_file=False, write_only=True)
    color_hex = serializers.RegexField(
        r'^#[0-9A-Fa-f]{6}$',
        error_messages={'invalid': 'Selecciona un color válido.'},
    )
    producto_id = serializers.IntegerField(min_value=1, required=False)

    def validate_imagen(self, value):
        if value.size > 4 * 1024 * 1024:
            raise serializers.ValidationError('La fotografía no puede superar 4 MB.')
        if value.content_type not in {'image/jpeg', 'image/png', 'image/webp'}:
            raise serializers.ValidationError('Usa una imagen JPG, PNG o WebP.')
        ancho, alto = value.image.size
        if ancho * alto > 12_000_000:
            raise serializers.ValidationError('La fotografía no puede superar 12 megapíxeles.')
        value.seek(0)
        return value

    def validate_producto_id(self, value):
        if not Producto.objects.filter(
            pk=value,
            activo=True,
            categoria='Pinturas',
            color_hex__gt='',
        ).exists():
            raise serializers.ValidationError('La pintura seleccionada no está disponible.')
        return value
