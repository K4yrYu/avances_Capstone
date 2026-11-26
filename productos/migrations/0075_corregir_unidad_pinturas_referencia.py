from django.db import migrations


def corregir_unidad(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.filter(
        sku__in=(
            'SFI-REF-PIN-KOL-STD-MAT', 'SFI-REF-PIN-KOL-STD-SB',
            'SFI-REF-PIN-KOL-PHO-SAT', 'SFI-REF-PIN-KOL-EXT-DEEP',
            'SFI-REF-PIN-KOL-ANT-NAR',
        ), unidad_contenido='L',
    ).update(unidad_contenido='l')


class Migration(migrations.Migration):
    dependencies = [('productos', '0074_pinturas_madera_referencia')]
    operations = [migrations.RunPython(corregir_unidad, migrations.RunPython.noop)]
