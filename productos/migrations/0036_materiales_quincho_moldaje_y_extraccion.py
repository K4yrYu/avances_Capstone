from django.db import migrations


MATERIALES_QUINCHO = [
    {
        'sku': 'SFI-QUI-MOL-MAD-RAD',
        'nombre': 'Madera para moldaje de radier 1 x 4 pulgadas x 3,2 m',
        'precio': 4490,
        'stock': 70,
        'stock_minimo': 12,
        'categoria': 'Construcción',
        'modelo': 'MOL-RAD-1X4-32',
        'uso': 'Formar y contener los bordes del radier durante el hormigonado.',
        'especificaciones': {
            'Sección declarada': '1 x 4 pulgadas',
            'Largo declarado': '3,2 m',
            'Uso': 'Moldaje temporal de bordes para radier',
        },
    },
    {
        'sku': 'SFI-QUI-PAR-INOX-60',
        'nombre': 'Parrilla acero inoxidable para quincho 60 x 40 cm',
        'precio': 69990,
        'stock': 18,
        'stock_minimo': 3,
        'categoria': 'Ferretería',
        'modelo': 'PAR-INOX-60X40',
        'uso': 'Sostener los alimentos sobre la zona de cocción del quincho.',
        'especificaciones': {
            'Material declarado': 'Acero inoxidable',
            'Medida declarada': '60 x 40 cm',
            'Uso': 'Parrilla para zona de cocción',
        },
    },
    {
        'sku': 'SFI-QUI-CAM-HUM-INOX',
        'nombre': 'Campana extractora de humo para quincho acero inoxidable',
        'precio': 189990,
        'stock': 8,
        'stock_minimo': 2,
        'categoria': 'Ferretería',
        'modelo': 'CAM-QUI-INOX',
        'uso': 'Captar el humo generado sobre la zona de fuego y conducirlo al ducto de evacuación.',
        'especificaciones': {
            'Material declarado': 'Acero inoxidable',
            'Uso': 'Captación de humo en quincho',
            'Instalación': 'Requiere ducto compatible y fijaciones según montaje',
        },
    },
    {
        'sku': 'SFI-QUI-DUC-CHIM-150',
        'nombre': 'Ducto chimenea para quincho galvanizado 150 mm x 1 m',
        'precio': 24990,
        'stock': 24,
        'stock_minimo': 4,
        'categoria': 'Construcción',
        'modelo': 'DUC-QUI-150-1M',
        'uso': 'Evacuar hacia el exterior el humo captado por la campana del quincho.',
        'especificaciones': {
            'Diámetro declarado': '150 mm',
            'Largo declarado': '1 m',
            'Material declarado': 'Acero galvanizado',
            'Uso': 'Evacuación de humo para quincho',
        },
    },
    {
        'sku': 'SFI-PIN-ANTICOR-1L',
        'nombre': 'Anticorrosivo para metal exterior rojo óxido 1 litro',
        'precio': 10990,
        'stock': 35,
        'stock_minimo': 6,
        'categoria': 'Pinturas',
        'modelo': 'ANTICOR-EXT-1L',
        'uso': 'Proteger estructuras metálicas frente a corrosión e intemperie antes de la terminación.',
        'especificaciones': {
            'Contenido declarado': '1 L',
            'Color declarado': 'Rojo óxido',
            'Uso': 'Protección anticorrosiva para metal exterior',
        },
    },
]


def cargar_materiales_quincho(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Proveedor = apps.get_model('productos', 'Proveedor')
    proveedor = Proveedor.objects.filter(nombre='Proveedor General SFI', activo=True).first()
    for registro in MATERIALES_QUINCHO:
        datos = dict(registro)
        sku = datos.pop('sku')
        uso = datos.pop('uso')
        especificaciones = datos.pop('especificaciones')
        Producto.objects.update_or_create(
            sku=sku,
            defaults={
                **datos,
                'descripcion': uso,
                'imagen': '',
                'activo': True,
                'marca': 'Genérico SFI',
                'ambiente_uso': 'exterior',
                'unidad_venta': 'unidad',
                'contenido': '1.000',
                'unidad_contenido': 'unidad',
                'tipo_calculo': 'unidad',
                'rendimiento': None,
                'unidad_rendimiento': '',
                'porcentaje_desperdicio': '0.00',
                'proveedor_id': proveedor.pk if proveedor else None,
                'uso_recomendado': uso,
                'especificaciones': {
                    **especificaciones,
                    'Estado de ficha': 'Datos de catálogo interno; validar compatibilidad y montaje antes de compra.',
                },
                'informacion_tecnica_verificada': False,
            },
        )


def retirar_materiales_quincho(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.filter(sku__in=[item['sku'] for item in MATERIALES_QUINCHO]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('productos', '0035_asociar_imagenes_catalogo_soldadura_jardineria'),
    ]

    operations = [
        migrations.RunPython(cargar_materiales_quincho, retirar_materiales_quincho),
    ]
