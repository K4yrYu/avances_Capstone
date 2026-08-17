from django.db import migrations


SKUS = [
    *(f'SFI-QUI-TOR-{indice:03d}' for indice in range(1, 7)),
    *(f'SFI-QUI-ANC-{indice:03d}' for indice in range(1, 7)),
    *(f'SFI-QUI-SEG-{indice:03d}' for indice in range(1, 7)),
    *(f'SFI-QUI-HER-{indice:03d}' for indice in range(1, 7)),
]

IMAGEN_ANTERIOR = {
    'TOR': 'productos/quincalleria-tornillos.png',
    'ANC': 'productos/quincalleria-anclajes.png',
    'SEG': 'productos/quincalleria-seguridad.png',
    'HER': 'productos/quincalleria-muebles.png',
}


def asignar_imagenes(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    for sku in SKUS:
        producto = Producto.objects.filter(sku=sku).first()
        if not producto:
            continue
        producto.imagen = f'productos/quincalleria-{sku.lower()}.png'
        especificaciones = dict(producto.especificaciones or {})
        especificaciones['Imagen'] = 'Representación individual generada para el catálogo SFI'
        producto.especificaciones = especificaciones
        producto.save(update_fields=['imagen', 'especificaciones'])


def restaurar_imagenes_familia(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    for sku in SKUS:
        producto = Producto.objects.filter(sku=sku).first()
        if not producto:
            continue
        familia = sku.split('-')[2]
        producto.imagen = IMAGEN_ANTERIOR[familia]
        especificaciones = dict(producto.especificaciones or {})
        especificaciones['Imagen'] = 'Representativa de la familia del producto'
        producto.especificaciones = especificaciones
        producto.save(update_fields=['imagen', 'especificaciones'])


class Migration(migrations.Migration):
    dependencies = [('productos', '0018_catalogo_quincalleria')]
    operations = [
        migrations.RunPython(asignar_imagenes, restaurar_imagenes_familia),
    ]
