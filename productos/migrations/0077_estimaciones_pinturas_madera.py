from decimal import Decimal

from django.db import migrations


SKUS = (
    'SFI-REF-PIN-KOL-STD-MAT',
    'SFI-REF-PIN-KOL-STD-SB',
    'SFI-REF-PIN-KOL-PHO-SAT',
    'SFI-REF-PIN-KOL-EXT-DEEP',
    'SFI-REF-PIN-KOL-ANT-NAR',
)


def registrar_estimaciones(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    for producto in Producto.objects.filter(sku__in=SKUS):
        ficha = dict(producto.especificaciones or {})
        ficha['Estimación de rendimiento'] = (
            'Referencia orientativa: 10 m² por litro y por mano; '
            'puede variar según superficie y aplicación. Confirmar con fabricante.'
        )
        ficha['Estimación de aplicación'] = (
            'Considerar 2 manos como referencia; confirmar tiempos y preparación '
            'en la ficha del producto.'
        )
        if producto.sku == 'SFI-REF-PIN-KOL-EXT-DEEP':
            ficha['Base tintable'] = 'Confirmar color y tintado antes de aplicar.'
        producto.especificaciones = ficha
        campos = ['especificaciones']
        if producto.rendimiento is None and not producto.unidad_rendimiento:
            producto.rendimiento = Decimal('10.000')
            producto.unidad_rendimiento = 'm2_l'
            campos.extend(['rendimiento', 'unidad_rendimiento'])
        if producto.capas_recomendadas is None:
            producto.capas_recomendadas = 2
            campos.append('capas_recomendadas')
        producto.save(update_fields=campos)


class Migration(migrations.Migration):
    dependencies = [('productos', '0076_activar_pinturas_madera')]
    operations = [migrations.RunPython(registrar_estimaciones, migrations.RunPython.noop)]
