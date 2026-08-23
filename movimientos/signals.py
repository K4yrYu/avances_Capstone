from django.db.models.signals import post_save, pre_delete, pre_save
from django.dispatch import receiver

from productos.models import Producto

from .contexto import obtener_responsable_actual
from .models import MovimientoInventario
from .services import datos_historicos_producto


CAMPOS_AUDITADOS = (
    "nombre", "sku", "categoria", "marca", "modelo", "precio", "stock",
    "stock_minimo", "unidad_venta", "activo", "proveedor_id",
)


@receiver(pre_save, sender=Producto)
def conservar_estado_anterior(sender, instance, **kwargs):
    if instance.pk:
        instance._estado_anterior_movimientos = sender.objects.filter(pk=instance.pk).values(
            *CAMPOS_AUDITADOS
        ).first()


@receiver(post_save, sender=Producto)
def registrar_creacion_o_modificacion(sender, instance, created, **kwargs):
    responsable = obtener_responsable_actual()
    if created:
        MovimientoInventario.objects.create(
            **datos_historicos_producto(instance),
            tipo=MovimientoInventario.Tipo.INICIAL,
            estado=MovimientoInventario.Estado.APLICADO,
            origen=MovimientoInventario.Origen.STOCK_INICIAL,
            cantidad_solicitada=instance.stock,
            cantidad_movida=instance.stock,
            entrada=instance.stock,
            stock_anterior=0,
            stock_resultante=instance.stock,
            observacion="Registro inicial del producto.",
            responsable=responsable,
        )
        return

    anterior = getattr(instance, "_estado_anterior_movimientos", None)
    if not anterior:
        return
    cambios = {}
    for campo in CAMPOS_AUDITADOS:
        actual = getattr(instance, campo)
        if anterior[campo] != actual:
            cambios[campo] = {"anterior": anterior[campo], "nuevo": actual}
    if not cambios:
        return

    stock_anterior = anterior["stock"]
    diferencia_stock = instance.stock - stock_anterior
    MovimientoInventario.objects.create(
        **datos_historicos_producto(instance),
        tipo=(MovimientoInventario.Tipo.AJUSTE if diferencia_stock else MovimientoInventario.Tipo.MODIFICACION),
        estado=MovimientoInventario.Estado.APLICADO,
        origen=(MovimientoInventario.Origen.AJUSTE_MANUAL if diferencia_stock else MovimientoInventario.Origen.EDICION_PRODUCTO),
        cantidad_solicitada=abs(diferencia_stock),
        cantidad_movida=abs(diferencia_stock),
        entrada=max(diferencia_stock, 0),
        salida=max(-diferencia_stock, 0),
        stock_anterior=stock_anterior,
        stock_resultante=instance.stock,
        observacion="Producto actualizado desde el catálogo.",
        cambios=cambios,
        responsable=responsable,
    )


@receiver(pre_delete, sender=Producto)
def registrar_eliminacion_producto(sender, instance, **kwargs):
    MovimientoInventario.objects.create(
        **datos_historicos_producto(instance),
        tipo=MovimientoInventario.Tipo.ELIMINACION,
        estado=MovimientoInventario.Estado.APLICADO,
        origen=MovimientoInventario.Origen.ELIMINACION_PRODUCTO,
        stock_anterior=instance.stock,
        stock_resultante=instance.stock,
        observacion="Producto eliminado del catálogo; se conserva su información histórica.",
        responsable=obtener_responsable_actual(),
    )
