from django.db import migrations


HERRAMIENTAS_TIERRA = [
    {
        'sku': 'SFI-JAR-PIC-2500',
        'nombre': 'Picota jardinera acero 2,5 kg mango fibra',
        'precio': 18990,
        'stock': 24,
        'stock_minimo': 5,
        'categoria': 'Herramientas',
        'modelo': 'PIC-2500-SFI',
        'uso': 'Aflojar tierra compactada y romper pequeños sectores duros antes de retirar material con pala.',
        'especificaciones': {
            'Cabeza declarada': 'Acero',
            'Peso declarado': '2,5 kg',
            'Mango declarado': 'Fibra',
            'Uso': 'Jardinería y preparación manual de terreno',
        },
    },
    {
        'sku': 'SFI-JAR-CAR-90L',
        'nombre': 'Carretilla acero 90 L rueda neumática',
        'precio': 69990,
        'stock': 14,
        'stock_minimo': 3,
        'categoria': 'Herramientas',
        'modelo': 'CAR-90L-SFI',
        'uso': 'Transportar tierra, escombros livianos y materiales de jardinería dentro del patio o la obra.',
        'especificaciones': {
            'Batea declarada': 'Acero',
            'Capacidad declarada': '90 L',
            'Rueda': 'Neumática',
            'Uso': 'Transporte manual de materiales',
        },
    },
    {
        'sku': 'SFI-JAR-AZA-120',
        'nombre': 'Azadón acero 120 mm mango madera',
        'precio': 10990,
        'stock': 35,
        'stock_minimo': 6,
        'categoria': 'Herramientas',
        'modelo': 'AZA-120-SFI',
        'uso': 'Remover y nivelar tierra superficial, retirar malezas y preparar sectores pequeños del jardín.',
        'especificaciones': {
            'Cabeza declarada': 'Acero 120 mm',
            'Mango declarado': 'Madera',
            'Uso': 'Preparación superficial de suelo',
        },
    },
    {
        'sku': 'SFI-JAR-RAS-14',
        'nombre': 'Rastrillo metálico 14 dientes mango madera',
        'precio': 9990,
        'stock': 40,
        'stock_minimo': 8,
        'categoria': 'Herramientas',
        'modelo': 'RAS-14-SFI',
        'uso': 'Emparejar tierra suelta y recoger hojas o restos vegetales después de la excavación.',
        'especificaciones': {
            'Dientes declarados': '14 metálicos',
            'Mango declarado': 'Madera',
            'Uso': 'Nivelación y limpieza de jardín',
        },
    },
    {
        'sku': 'SFI-JAR-GUA-NIT-M',
        'nombre': 'Guantes de jardinería nitrilo talla M',
        'precio': 3990,
        'stock': 75,
        'stock_minimo': 12,
        'categoria': 'Seguridad',
        'modelo': 'GUA-JAR-NIT-M',
        'uso': 'Protección básica de las manos al manipular tierra, plantas y herramientas manuales.',
        'especificaciones': {
            'Material declarado': 'Tejido con recubrimiento de nitrilo',
            'Talla declarada': 'M',
            'Uso': 'Jardinería y manipulación general',
        },
    },
]


def cargar_herramientas_tierra(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Proveedor = apps.get_model('productos', 'Proveedor')
    proveedor = Proveedor.objects.filter(
        nombre='Proveedor General SFI', activo=True,
    ).first()
    for registro in HERRAMIENTAS_TIERRA:
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
                    'Estado de ficha': 'Datos de catálogo interno; validar características con proveedor antes de compra.',
                },
                'informacion_tecnica_verificada': False,
            },
        )


def retirar_herramientas_tierra(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.filter(sku__startswith='SFI-JAR-').filter(
        sku__in=[item['sku'] for item in HERRAMIENTAS_TIERRA]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('productos', '0033_catalogo_maceteros_jardineria'),
    ]

    operations = [
        migrations.RunPython(cargar_herramientas_tierra, retirar_herramientas_tierra),
    ]
