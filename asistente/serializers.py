from rest_framework import serializers

from productos.models import Producto


class MensajeHistorialSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=['user', 'assistant'])
    content = serializers.CharField(min_length=1, max_length=700, trim_whitespace=True)


class ConsultaAsistenteSerializer(serializers.Serializer):
    mensaje = serializers.CharField(min_length=2, max_length=700, trim_whitespace=True)
    historial = MensajeHistorialSerializer(many=True, required=False, default=list)
    productos_contexto = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        default=list,
        max_length=8,
    )

    def validate_historial(self, value):
        if len(value) > 6:
            raise serializers.ValidationError('Solo se permiten los últimos 6 mensajes.')
        return value

    def validate_productos_contexto(self, value):
        return list(dict.fromkeys(value))


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
