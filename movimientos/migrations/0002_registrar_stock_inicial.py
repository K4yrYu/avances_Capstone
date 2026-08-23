from django.db import migrations


def registrar_stock_inicial(apps, schema_editor):
    Producto = apps.get_model("productos", "Producto")
    Movimiento = apps.get_model("movimientos", "MovimientoInventario")
    movimientos = []
    for producto in Producto.objects.all().iterator():
        movimientos.append(Movimiento(
            producto_id=producto.pk,
            producto_id_original=producto.pk,
            producto_nombre=producto.nombre,
            producto_sku=producto.sku or "",
            categoria=producto.categoria or "",
            marca=producto.marca or "",
            modelo=producto.modelo or "",
            unidad_venta=producto.unidad_venta or "",
            precio_unitario=producto.precio,
            tipo="inicial",
            estado="aplicado",
            origen="stock_inicial",
            cantidad_solicitada=producto.stock,
            cantidad_movida=producto.stock,
            entrada=producto.stock,
            stock_anterior=0,
            stock_resultante=producto.stock,
            observacion="Saldo inicial al habilitar el módulo Movimientos.",
            clave_idempotencia=f"stock-inicial:{producto.pk}",
        ))
    Movimiento.objects.bulk_create(movimientos, ignore_conflicts=True)


class Migration(migrations.Migration):
    dependencies = [
        ("movimientos", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(registrar_stock_inicial, migrations.RunPython.noop),
    ]
