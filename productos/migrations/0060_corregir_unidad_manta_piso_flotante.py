from django.db import migrations


def corregir_unidad(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.filter(sku='TEST-PIS-MAN-15').update(unidad_venta='rollo')


def revertir_unidad(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.filter(sku='TEST-PIS-MAN-15').update(unidad_venta='unidad')


class Migration(migrations.Migration):
    dependencies = [('productos', '0059_complementos_piso_flotante')]

    operations = [migrations.RunPython(corregir_unidad, revertir_unidad)]
