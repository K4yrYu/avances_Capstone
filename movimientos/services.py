from django.core.exceptions import ValidationError
from django.db import transaction

from productos.models import Producto

from .models import MovimientoInventario


def datos_historicos_producto(producto):
    return {
        "producto": producto,
        "producto_id_original": producto.pk,
        "producto_nombre": producto.nombre,
        "producto_sku": producto.sku or "",
        "categoria": producto.categoria or "",
        "marca": producto.marca or "",
        "modelo": producto.modelo or "",
        "unidad_venta": producto.unidad_venta or "",
        "precio_unitario": producto.precio,
    }


@transaction.atomic
def registrar_movimiento_stock(
    *, producto_id, tipo, cantidad, origen, referencia="", observacion="",
    responsable=None, cantidad_solicitada=None, cantidad_pendiente=0,
    clave_idempotencia=None, precio_unitario=None,
):
    if cantidad <= 0:
        raise ValidationError("La cantidad del movimiento debe ser mayor que cero.")

    if clave_idempotencia:
        existente = MovimientoInventario.objects.filter(
            clave_idempotencia=clave_idempotencia
        ).first()
        if existente:
            return existente

    producto = Producto.objects.select_for_update().get(pk=producto_id)
    stock_anterior = producto.stock
    entrada = cantidad if tipo == MovimientoInventario.Tipo.ENTRADA else 0
    salida = cantidad if tipo == MovimientoInventario.Tipo.SALIDA else 0
    stock_resultante = stock_anterior + entrada - salida
    if stock_resultante < 0:
        raise ValidationError(f"Stock insuficiente para {producto.nombre}.")

    Producto.objects.filter(pk=producto.pk).update(stock=stock_resultante)
    datos = datos_historicos_producto(producto)
    if precio_unitario is not None:
        datos["precio_unitario"] = precio_unitario
    return MovimientoInventario.objects.create(
        **datos,
        tipo=tipo,
        estado=MovimientoInventario.Estado.APLICADO,
        origen=origen,
        cantidad_solicitada=cantidad_solicitada if cantidad_solicitada is not None else cantidad,
        cantidad_movida=cantidad,
        cantidad_pendiente=cantidad_pendiente,
        entrada=entrada,
        salida=salida,
        stock_anterior=stock_anterior,
        stock_resultante=stock_resultante,
        referencia=referencia,
        observacion=observacion,
        responsable=responsable,
        clave_idempotencia=clave_idempotencia,
    )


@transaction.atomic
def registrar_ajuste_stock(*, producto_id, nuevo_stock, observacion, responsable=None):
    producto = Producto.objects.select_for_update().get(pk=producto_id)
    stock_anterior = producto.stock
    if nuevo_stock < 0:
        raise ValidationError("El stock no puede ser negativo.")
    if nuevo_stock == stock_anterior:
        raise ValidationError("El nuevo stock debe ser diferente al stock actual.")

    Producto.objects.filter(pk=producto.pk).update(stock=nuevo_stock)
    diferencia = nuevo_stock - stock_anterior
    return MovimientoInventario.objects.create(
        **datos_historicos_producto(producto),
        tipo=MovimientoInventario.Tipo.AJUSTE,
        estado=MovimientoInventario.Estado.APLICADO,
        origen=MovimientoInventario.Origen.AJUSTE_MANUAL,
        cantidad_solicitada=abs(diferencia),
        cantidad_movida=abs(diferencia),
        entrada=max(diferencia, 0),
        salida=max(-diferencia, 0),
        stock_anterior=stock_anterior,
        stock_resultante=nuevo_stock,
        observacion=observacion,
        responsable=responsable,
    )
