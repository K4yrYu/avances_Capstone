from django.db import migrations


CLASIFICACION = {
    'COR-IVEANCP14KV': ('Piso', ['Baño', 'Cocina'], True, 'Residencial'),
    'COR-ICEMPCP14KI': ('Piso', ['Baño', 'Cocina'], True, 'Medio'),
    'COR-MAIRENA-BEIGE-45': ('Piso', ['Baño', 'Cocina', 'Terraza'], True, 'Alto'),
    'COR-MAIRENA-OXIDO-45': ('Piso', ['Baño', 'Cocina'], True, 'Medio'),
    'COR-SOLANA-BEIGE-45': ('Piso', ['Baño', 'Cocina'], True, 'Alto'),
    'COR-VENETO-GRIS-45': ('Piso', ['Baño', 'Cocina'], True, 'Medio'),
    'COR-CNAWHAG15QV': ('Muro', ['Baño', 'Cocina'], False, 'No aplica'),
    'COR-HARMONY-BEIGE-27X45': ('Muro', ['Baño', 'Cocina'], False, 'No aplica'),
    'COR-HARMONY-GRIS-27X45': ('Muro', ['Baño', 'Cocina'], False, 'No aplica'),
    'COR-ICEMGCP16BE': ('Muro', ['Baño', 'Cocina'], False, 'No aplica'),
    'COR-ICEMGCO16DI': ('Muro', ['Baño', 'Cocina'], False, 'No aplica'),
    'COR-IINDICP16BN': ('Muro', ['Baño', 'Cocina'], False, 'No aplica'),
    'COR-IAGADCP14KC': ('Piso y muro', ['Baño', 'Cocina', 'Terraza'], False, 'Residencial'),
    'BAN-CER-150': ('Muro', ['Baño'], False, 'No aplica'),
    'TEST-EXT-PIS-CER-145': ('Muro', ['Baño', 'Cocina'], False, 'No aplica'),
    'BAN-POR-144': ('Piso', ['Baño'], True, 'Residencial'),
    'SFI-CER-PIS-NAT-60': ('Piso', ['Cocina', 'Living', 'Comedor'], False, 'Residencial'),
}


CAMPOS = (
    'Aplicación', 'Ambientes recomendados', 'Zona húmeda',
    'Antideslizante', 'Nivel de tránsito',
)


def clasificar_ceramicas(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    for sku, (aplicacion, ambientes, antideslizante, transito) in CLASIFICACION.items():
        producto = Producto.objects.filter(sku=sku).first()
        if not producto:
            continue
        ficha = dict(producto.especificaciones or {})
        ficha.update({
            'Aplicación': aplicacion,
            'Ambientes recomendados': ambientes,
            'Zona húmeda': any(
                ambiente in {'Baño', 'Cocina'} for ambiente in ambientes
            ),
            'Antideslizante': antideslizante,
            'Nivel de tránsito': transito,
        })
        producto.especificaciones = ficha
        producto.save(update_fields=['especificaciones'])


def retirar_clasificacion(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    for producto in Producto.objects.filter(sku__in=CLASIFICACION):
        ficha = dict(producto.especificaciones or {})
        for campo in CAMPOS:
            ficha.pop(campo, None)
        producto.especificaciones = ficha
        producto.save(update_fields=['especificaciones'])


class Migration(migrations.Migration):
    dependencies = [('productos', '0056_ceramicas_bano_cocina')]

    operations = [
        migrations.RunPython(clasificar_ceramicas, retirar_clasificacion),
    ]
