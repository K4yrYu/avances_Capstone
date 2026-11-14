from django.db import migrations


TEJAS = [
    dict(sku='TEST-TEJ-ASF-3TAB', nombre='Teja asfáltica 3 tabs paquete 3,10 m²', precio=34990, stock=36, medida='Paquete con cobertura comercial referencial de 3,10 m²', uso='Cubiertas inclinadas sobre base continua y sistema de instalación compatible.'),
    dict(sku='TEST-TEJ-ASF-LAM', nombre='Teja asfáltica laminada paquete 3 m²', precio=44990, stock=28, medida='Paquete con cobertura comercial referencial de 3 m²', uso='Cubiertas inclinadas con terminación laminada sobre base continua compatible.'),
    dict(sku='TEST-TEJ-ARC-COL', nombre='Teja colonial de arcilla terracota 42 x 21 cm', precio=1590, stock=520, medida='Pieza 42 x 21 cm', uso='Cubiertas inclinadas de apariencia tradicional con estructura y traslapes definidos por el fabricante.'),
    dict(sku='TEST-TEJ-ARC-POR', nombre='Teja portuguesa de arcilla 41 x 24 cm', precio=1890, stock=430, medida='Pieza 41 x 24 cm', uso='Cubiertas inclinadas tradicionales con apoyos y traslapes compatibles.'),
    dict(sku='TEST-TEJ-HOR-COL', nombre='Teja colonial de hormigón 42 x 33 cm', precio=2290, stock=360, medida='Pieza 42 x 33 cm', uso='Cubiertas inclinadas cuya estructura haya sido dimensionada para su peso.'),
    dict(sku='TEST-TEJ-PVC-300', nombre='Teja colonial PVC 0,96 x 3 m', precio=39990, stock=34, medida='Panel 0,96 x 3 m', uso='Cubiertas livianas con pendiente, apoyos y fijaciones compatibles.'),
    dict(sku='TEST-TEJ-MET-GRA', nombre='Teja metálica gravillada panel 1,34 x 0,42 m', precio=14990, stock=95, medida='Panel 1,34 x 0,42 m', uso='Cubiertas metálicas livianas con estructura y fijaciones definidas para el sistema.'),
    dict(sku='TEST-TEJ-MET-CON', nombre='Teja continua acero prepintado 0,45 mm x 3 m', precio=28990, stock=48, medida='Espesor 0,45 mm; largo 3 m', uso='Cubiertas de acero conformado con traslape, pendiente y fijación compatibles.'),
]


def cargar_tejas(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    for registro in TEJAS:
        datos = dict(registro)
        sku = datos.pop('sku')
        medida = datos.pop('medida')
        uso = datos.pop('uso')
        Producto.objects.update_or_create(sku=sku, defaults={
            **datos,
            'descripcion': uso,
            'imagen': '',
            'stock_minimo': 10,
            'marca': 'Genérico SFI',
            'categoria': 'Construcción',
            'activo': True,
            'unidad_venta': 'paquete' if 'paquete' in datos['nombre'].casefold() else 'unidad',
            'contenido': None,
            'unidad_contenido': '',
            'tipo_calculo': 'unidad',
            'rendimiento': None,
            'unidad_rendimiento': '',
            'porcentaje_desperdicio': '10.00',
            'uso_recomendado': uso,
            'especificaciones': {
                'Formato comercial': medida,
                'Validación necesaria': 'Confirmar rendimiento útil, pendiente, traslape y fijación con el proveedor.',
                'Origen del registro': 'Catálogo de prueba de tejas SFI 13-11-2026',
            },
            'informacion_tecnica_verificada': False,
        })


def retirar_tejas(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.filter(sku__startswith='TEST-TEJ-').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('productos', '0027_catalogo_quinchos'),
    ]

    operations = [
        migrations.RunPython(cargar_tejas, retirar_tejas),
    ]
