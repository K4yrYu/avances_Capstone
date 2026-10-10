from rest_framework import serializers
from .models import DespachoVenta, Venta, Detalle
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
    despachos = serializers.SerializerMethodField()
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
            'cargo_despacho',
            'estado_entrega',
            'webpay_payment_status',
            'ultimos_digitos',
            'id_usuario',
            'detalles',
            'despachos',
        ]

    def get_detalles(self, obj):
        detalles = obj.detalles.all()
        return DetalleSerializer(detalles, many=True).data

    def get_despachos(self, obj):
        return [
            {
                'id': despacho.id,
                'numero': despacho.numero,
                'fecha_programada': despacho.fecha_programada,
                'estado': despacho.estado,
                'estado_display': despacho.get_estado_display(),
                'cargo': despacho.cargo,
                'direccion': despacho.direccion,
            }
            for despacho in obj.despachos.all()
        ]


class DespachoVentaSerializer(serializers.ModelSerializer):
    venta_id = serializers.IntegerField(source='venta.id', read_only=True)
    id_usuario = UsuarioSerializer(source='venta.id_usuario', read_only=True)
    direccion_despacho = serializers.CharField(source='direccion', read_only=True)
    fecha_compra = serializers.DateTimeField(source='venta.fecha_compra', read_only=True)
    fecha_programada = serializers.DateField(read_only=True)
    total_venta = serializers.IntegerField(source='venta.total_venta', read_only=True)
    estado_entrega = serializers.SerializerMethodField()
    detalles = serializers.SerializerMethodField()
    valor_despacho = serializers.SerializerMethodField()
    comprador_email = serializers.EmailField(source='venta.id_usuario.email', read_only=True)
    comprador_telefono = serializers.CharField(source='venta.id_usuario.telefono', read_only=True)

    class Meta:
        model = DespachoVenta
        fields = [
            'id',
            'venta_id',
            'numero',
            'fecha_compra',
            'fecha_programada',
            'total_venta',
            'valor_despacho',
            'cargo',
            'estado',
            'estado_entrega',
            'direccion_despacho',
            'id_usuario',
            'comprador_email',
            'comprador_telefono',
            'detalles',
        ]

    def get_estado_entrega(self, obj):
        return 'completado' if obj.estado == DespachoVenta.Estado.ENTREGADO else 'pendiente'

    def get_detalles(self, obj):
        return [
            {
                'nombre_producto': asignacion.detalle.nombre_producto,
                'cantidad_producto': asignacion.cantidad,
                'subtotal_venta': asignacion.detalle.precio_unitario * asignacion.cantidad,
            }
            for asignacion in obj.detalles_despacho.all()
        ]

    def get_valor_despacho(self, obj):
        return obj.cargo + sum(
            asignacion.detalle.precio_unitario * asignacion.cantidad
            for asignacion in obj.detalles_despacho.all()
        )


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
