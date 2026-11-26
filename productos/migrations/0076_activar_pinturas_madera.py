from django.db import migrations


# Precios referenciales aprobados por el administrador; no acreditan el costo
# del proveedor ni reemplazan la revisión comercial posterior.
PRECIOS = {
    'SFI-REF-PIN-KOL-STD-MAT': (33990, 'Referencia de mercado para esmalte KOLOR Standard 1 galón.'),
    'SFI-REF-PIN-KOL-STD-SB': (38990, 'Estimado por comparación con esmalte KOLOR semibrillante 1 galón.'),
    'SFI-REF-PIN-KOL-PHO-SAT': (43235, 'Referencia de mercado para KOLOR Photio 1 galón.'),
    'SFI-REF-PIN-KOL-EXT-DEEP': (38990, 'Estimado por comparación con esmaltes KOLOR de 1 galón.'),
    'SFI-REF-PIN-KOL-ANT-NAR': (42990, 'Estimado por comparación con pinturas KOLOR especiales de 1 galón.'),
}


def activar_pinturas(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Proveedor = apps.get_model('productos', 'Proveedor')
    proveedor = Proveedor.objects.get(nombre='Distribuidora SFI Pinturas', activo=True)
    for sku, (precio, fuente) in PRECIOS.items():
        producto = Producto.objects.get(sku=sku)
        ficha = dict(producto.especificaciones or {})
        ficha.pop('Precio de 1 CLP', None)
        ficha['Estado comercial'] = 'Precio referencial; revisar antes de vender.'
        ficha['Referencia del precio'] = fuente
        producto.precio = precio
        producto.stock = 15
        producto.activo = True
        producto.proveedor_id = proveedor.pk
        producto.especificaciones = ficha
        producto.save(update_fields=['precio', 'stock', 'activo', 'proveedor', 'especificaciones'])


class Migration(migrations.Migration):
    dependencies = [('productos', '0075_corregir_unidad_pinturas_referencia')]
    operations = [migrations.RunPython(activar_pinturas, migrations.RunPython.noop)]
