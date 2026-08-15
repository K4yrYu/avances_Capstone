from rest_framework import serializers
from .models import Venta, Detalle
from productos.models import Producto
from usuarios.models import Usuario

class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ['id', 'username', 'first_name', 'last_name', 'rut']

class DetalleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Detalle
        fields = [
            'nombre_producto',
            'precio_unitario',
            'imagen_producto',
            'cantidad_producto',
            'subtotal_venta'
        ]

class VentaSerializer(serializers.ModelSerializer):
    detalles = serializers.SerializerMethodField()
    id_usuario = UsuarioSerializer()

    class Meta:
        model = Venta
        fields = [
            'id',
            'fecha_compra',
            'total_venta',
            'estado_venta',
            'tipo_entrega',
            'direccion_despacho',
            'estado_entrega',
            'webpay_payment_status',
            'ultimos_digitos',
            'id_usuario',
            'detalles'
        ]

    def get_detalles(self, obj):
        detalles = obj.detalles.all()
        return DetalleSerializer(detalles, many=True).data


class CantidadProductoSerializer(serializers.Serializer):
    cantidad_producto = serializers.IntegerField(min_value=1)


class DetalleCarritoEntradaSerializer(CantidadProductoSerializer):
    producto = serializers.IntegerField(min_value=1)


class RecomendacionPinturaCarritoSerializer(serializers.Serializer):
    producto = serializers.IntegerField(min_value=1)
    superficie = serializers.IntegerField(min_value=1, max_value=100000)
    ambiente = serializers.ChoiceField(choices=[
        valor for valor, _ in Producto.AMBIENTE_USO_CHOICES if valor != 'no_aplica'
    ])
    tipo_superficie = serializers.ChoiceField(choices=Producto.SUPERFICIE_CHOICES)
    estado_superficie = serializers.ChoiceField(choices=Producto.ESTADO_SUPERFICIE_CHOICES)
    terminacion = serializers.ChoiceField(choices=[
        ('cualquiera', 'Sin preferencia'),
        *[opcion for opcion in Producto.TERMINACION_CHOICES if opcion[0] != 'no_aplica'],
    ])
    capas = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=10)
    desperdicio = serializers.DecimalField(
        required=False,
        allow_null=True,
        max_digits=5,
        decimal_places=2,
        min_value=0,
        max_value=50,
    )
