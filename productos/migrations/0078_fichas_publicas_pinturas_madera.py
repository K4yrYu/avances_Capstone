from django.db import migrations


SKUS = (
    'SFI-REF-PIN-KOL-STD-MAT',
    'SFI-REF-PIN-KOL-STD-SB',
    'SFI-REF-PIN-KOL-PHO-SAT',
    'SFI-REF-PIN-KOL-EXT-DEEP',
    'SFI-REF-PIN-KOL-ANT-NAR',
)


def completar_fichas(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    for producto in Producto.objects.filter(sku__in=SKUS):
        ficha = dict(producto.especificaciones or {})
        ficha.setdefault('Base', 'Agua')
        ficha.setdefault('Preparación', 'Superficie limpia y seca; seguir las indicaciones del fabricante.')
        if producto.sku == 'SFI-REF-PIN-KOL-EXT-DEEP':
            ficha.setdefault('Presentación del color', 'Base tintable; confirmar color y tintado antes de aplicar.')
        producto.especificaciones = ficha
        producto.save(update_fields=['especificaciones'])


class Migration(migrations.Migration):
    dependencies = [('productos', '0077_estimaciones_pinturas_madera')]
    operations = [migrations.RunPython(completar_fichas, migrations.RunPython.noop)]
