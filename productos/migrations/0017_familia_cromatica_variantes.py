from django.db import migrations


FAMILIAS_POR_SKU = {
    'SFI-SIP-LTX-CW004W-1GL': 'azul',
    'SFI-SIP-LTX-CW015W-1GL': 'verde',
    'SFI-SIP-LTX-CW022W-1GL': 'amarillo',
    'SFI-SIP-LTX-CW053W-1GL': 'beige',
    'SFI-SIP-LTX-CW059W-1GL': 'gris',
    'SFI-SIP-LTX-AC116N-1GL': 'rojo',
    'SFI-SIP-ESA-7002W-1GL': 'violeta morado lila',
    'SFI-SIP-ESA-7050W-1GL': 'azul',
    'SFI-SIP-ESA-0720-1GL': 'verde',
    'SFI-SIP-ESA-CW026W-1GL': 'amarillo',
    'SFI-SIP-ESA-CW032W-1GL': 'naranjo naranja',
    'SFI-SIP-ESA-CW058W-1GL': 'gris',
    'SFI-SIP-FEH-AC102N-1GL': 'verde',
    'SFI-SIP-FEH-AC103Y-1GL': 'amarillo',
    'SFI-SIP-FEH-AC113N-1GL': 'cafe marron',
    'SFI-SIP-FEH-AC116N-1GL': 'rojo',
    'SFI-SIP-FEH-7055D-1GL': 'azul',
    'SFI-SIP-FEH-0752-1GL': 'verde',
    'SFI-SIP-EAS-7045D-1GL': 'azul',
    'SFI-SIP-EAS-0726-1GL': 'verde',
    'SFI-SIP-EAS-0800-1GL': 'amarillo',
    'SFI-SIP-EAS-CW070W-1GL': 'gris',
    'SFI-SIP-EAS-CW030W-1GL': 'beige',
    'SFI-SIP-EAS-AC110N-1GL': 'rojo',
}


def agregar_familias(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    for sku, familia in FAMILIAS_POR_SKU.items():
        producto = Producto.objects.filter(sku=sku).first()
        if not producto:
            continue
        especificaciones = dict(producto.especificaciones or {})
        especificaciones['familia_cromatica'] = familia
        producto.especificaciones = especificaciones
        producto.save(update_fields=['especificaciones'])


def quitar_familias(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    for producto in Producto.objects.filter(sku__in=FAMILIAS_POR_SKU):
        especificaciones = dict(producto.especificaciones or {})
        especificaciones.pop('familia_cromatica', None)
        producto.especificaciones = especificaciones
        producto.save(update_fields=['especificaciones'])


class Migration(migrations.Migration):
    dependencies = [('productos', '0016_variantes_pintura_sipa')]
    operations = [
        migrations.RunPython(agregar_familias, quitar_familias),
    ]
