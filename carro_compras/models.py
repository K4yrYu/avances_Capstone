from django.db import models
from usuarios.models import Usuario
from productos.models import Producto
from django.contrib.auth import get_user_model
from django.db.models import Q

Usuario = get_user_model()

class Venta(models.Model):
    ESTADO_VENTA_CHOICES = [
        ('carrito', 'Carrito'),
        ('pago_pendiente', 'Pago pendiente'),
        ('pagado', 'Pagado'),
        ('pago_error', 'Pago con incidencia'),
    ]

    id_usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    fecha_compra = models.DateTimeField(null=True, blank=True)
    total_venta = models.IntegerField(default=0)
    estado_venta = models.CharField(max_length=20, choices=ESTADO_VENTA_CHOICES, default='carrito')

    # WebPay
    webpay_transaction_id = models.CharField(max_length=100, blank=True, null=True, unique=True)
    webpay_payment_status = models.CharField(max_length=50, blank=True, null=True)
    webpay_amount = models.PositiveBigIntegerField(blank=True, null=True)
    webpay_buy_order = models.CharField(max_length=26, blank=True, null=True, unique=True)
    webpay_session_id = models.CharField(max_length=61, blank=True, null=True, unique=True)
    ultimos_digitos = models.CharField(max_length=4, blank=True, null=True)


    # Tipo de entrega: retiro o despacho
    tipo_entrega = models.CharField(
        max_length=10,
        choices=[('retiro', 'Retiro en tienda'), ('despacho', 'Despacho a domicilio')],
        default='retiro'
    )
    direccion_despacho = models.TextField(blank=True, null=True)

    # Estado de la entrega: pendiente o completado
    estado_entrega = models.CharField(
        max_length=20,
        choices=[('pendiente', 'Por entregar'), ('completado', 'Completado')],
        default='pendiente'
    )

    # Campo de eliminación lógica
    eliminado = models.BooleanField(default=False)

    def __str__(self):
        return f"Venta {self.id} - {self.id_usuario.username}"

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(total_venta__gte=0), name='venta_total_no_negativo'),
        ]
    
    
class Detalle(models.Model):
    cantidad_producto = models.PositiveIntegerField()
    subtotal_venta = models.IntegerField()
    id_venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='detalles')

    # Congelados al momento de la compra
    nombre_producto = models.CharField(max_length=200, default='Producto eliminado')
    precio_unitario = models.IntegerField(default=0)
    imagen_producto = models.CharField(max_length=500, blank=True, null=True)

    def __str__(self):
        return f"{self.id_venta} | {self.nombre_producto} | {self.cantidad_producto} | {self.subtotal_venta}"

    def save(self, *args, **kwargs):
        if not self.pk:
            self.nombre_producto = self.producto.nombre
            self.precio_unitario = self.producto.precio
            self.imagen_producto = self.producto.imagen.url if self.producto.imagen else None
        self.subtotal_venta = self.precio_unitario * self.cantidad_producto
        super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(cantidad_producto__gt=0), name='detalle_cantidad_positiva'),
            models.CheckConstraint(condition=Q(precio_unitario__gt=0), name='detalle_precio_positivo'),
            models.CheckConstraint(condition=Q(subtotal_venta__gte=0), name='detalle_subtotal_no_negativo'),
            models.UniqueConstraint(fields=['id_venta', 'producto'], name='detalle_producto_unico_por_venta'),
        ]
