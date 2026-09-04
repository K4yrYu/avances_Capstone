from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class MovimientoInventario(models.Model):
    class Tipo(models.TextChoices):
        INICIAL = "inicial", "Stock inicial"
        SOLICITUD = "solicitud", "En proceso"
        ENTRADA = "entrada", "Entrada"
        SALIDA = "salida", "Salida"
        AJUSTE = "ajuste", "Ajuste"
        MODIFICACION = "modificacion", "Modificación"
        ELIMINACION = "eliminacion", "Eliminación"
        INCIDENCIA = "incidencia", "Incidencia"

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        PARCIAL = "parcial", "Parcial"
        APLICADO = "aplicado", "Aplicado"
        ANULADO = "anulado", "Anulado"

    class Origen(models.TextChoices):
        STOCK_INICIAL = "stock_inicial", "Stock inicial"
        REPOSICION = "reposicion", "Reposición"
        VENTA = "venta", "Venta"
        AJUSTE_MANUAL = "ajuste_manual", "Ajuste manual"
        EDICION_PRODUCTO = "edicion_producto", "Edición de producto"
        ELIMINACION_PRODUCTO = "eliminacion_producto", "Eliminación de producto"

    producto = models.ForeignKey(
        "productos.Producto",
        on_delete=models.SET_NULL,
        related_name="movimientos_inventario",
        null=True,
        blank=True,
    )
    producto_id_original = models.PositiveBigIntegerField(db_index=True)
    producto_nombre = models.CharField(max_length=200)
    producto_sku = models.CharField(max_length=50, blank=True)
    categoria = models.CharField(max_length=100, blank=True)
    marca = models.CharField(max_length=100, blank=True)
    modelo = models.CharField(max_length=120, blank=True)
    unidad_venta = models.CharField(max_length=20, blank=True)
    precio_unitario = models.PositiveBigIntegerField(default=0)
    proveedor_nombre = models.CharField(max_length=160, blank=True)

    tipo = models.CharField(max_length=20, choices=Tipo.choices, db_index=True)
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.APLICADO,
        db_index=True,
    )
    origen = models.CharField(max_length=30, choices=Origen.choices, db_index=True)
    cantidad_solicitada = models.PositiveIntegerField(default=0)
    cantidad_movida = models.PositiveIntegerField(default=0)
    cantidad_pendiente = models.PositiveIntegerField(default=0)
    entrada = models.PositiveIntegerField(default=0)
    salida = models.PositiveIntegerField(default=0)
    stock_anterior = models.PositiveIntegerField(null=True, blank=True)
    stock_resultante = models.PositiveIntegerField(null=True, blank=True)

    referencia = models.CharField(max_length=120, blank=True)
    observacion = models.TextField(blank=True)
    cambios = models.JSONField(default=dict, blank=True)
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="movimientos_inventario_registrados",
        null=True,
        blank=True,
    )
    clave_idempotencia = models.CharField(max_length=150, unique=True, null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-creado_en", "-id"]
        indexes = [
            models.Index(fields=["producto_id_original", "-creado_en"]),
            models.Index(fields=["origen", "estado", "-creado_en"]),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} | {self.producto_nombre} | {self.creado_en:%d-%m-%Y %H:%M}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Los movimientos históricos no se pueden modificar.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Los movimientos históricos no se pueden eliminar.")


class LoteInventario(models.Model):
    producto = models.ForeignKey(
        "productos.Producto",
        on_delete=models.PROTECT,
        related_name="lotes_inventario",
    )
    lote = models.CharField(max_length=80)
    cantidad_disponible = models.PositiveIntegerField(default=0)
    fecha_ingreso = models.DateField(default=timezone.localdate)
    fecha_vencimiento = models.DateField()
    referencia = models.CharField(max_length=120, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["fecha_vencimiento", "producto__nombre"]
        constraints = [
            models.UniqueConstraint(fields=["producto", "lote"], name="lote_unico_por_producto")
        ]

    def __str__(self):
        return f"{self.producto.nombre} | {self.lote}"
