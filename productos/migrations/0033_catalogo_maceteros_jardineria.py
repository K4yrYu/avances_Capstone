from django.db import migrations


PRODUCTOS_MACETEROS = [
    {
        'sku': 'SFI-JAR-MAC-PLA-25',
        'nombre': 'Macetero plástico redondo terracota 25 cm',
        'precio': 2490,
        'stock': 80,
        'stock_minimo': 12,
        'modelo': 'MAC-PLA-25',
        'contenido': '5.000',
        'unidad_contenido': 'l',
        'uso': 'Macetero liviano para plantas pequeñas y hierbas en balcones, patios o interiores protegidos.',
        'especificaciones': {
            'Material declarado': 'Plástico',
            'Diámetro superior declarado': '25 cm',
            'Capacidad aproximada': '5 L',
            'Drenaje': 'Orificios inferiores',
            'Color': 'Terracota',
        },
    },
    {
        'sku': 'SFI-JAR-MAC-PLA-35',
        'nombre': 'Macetero plástico redondo terracota 35 cm',
        'precio': 4990,
        'stock': 65,
        'stock_minimo': 10,
        'modelo': 'MAC-PLA-35',
        'contenido': '14.000',
        'unidad_contenido': 'l',
        'uso': 'Macetero para plantas ornamentales de tamaño medio en exteriores o interiores ventilados.',
        'especificaciones': {
            'Material declarado': 'Plástico',
            'Diámetro superior declarado': '35 cm',
            'Capacidad aproximada': '14 L',
            'Drenaje': 'Orificios inferiores',
            'Color': 'Terracota',
        },
    },
    {
        'sku': 'SFI-JAR-MAC-REC-50',
        'nombre': 'Macetero rectangular plástico grafito 50 x 20 x 18 cm',
        'precio': 6990,
        'stock': 50,
        'stock_minimo': 8,
        'modelo': 'MAC-REC-50',
        'contenido': '15.000',
        'unidad_contenido': 'l',
        'uso': 'Jardinera para hierbas, flores o plantas de raíz corta en ventanas, terrazas y balcones.',
        'especificaciones': {
            'Material declarado': 'Plástico',
            'Medidas declaradas': '50 x 20 x 18 cm',
            'Capacidad aproximada': '15 L',
            'Drenaje': 'Orificios inferiores',
            'Color': 'Grafito',
        },
    },
    {
        'sku': 'SFI-JAR-MAC-CER-30',
        'nombre': 'Macetero cerámico esmaltado 30 cm',
        'precio': 12990,
        'stock': 35,
        'stock_minimo': 6,
        'modelo': 'MAC-CER-30',
        'contenido': '10.000',
        'unidad_contenido': 'l',
        'uso': 'Macetero decorativo para plantas de interior o sectores exteriores protegidos.',
        'especificaciones': {
            'Material declarado': 'Cerámica esmaltada',
            'Diámetro superior declarado': '30 cm',
            'Capacidad aproximada': '10 L',
            'Drenaje': 'Orificio inferior',
            'Color': 'Blanco',
        },
    },
    {
        'sku': 'SFI-JAR-MAC-CEM-40',
        'nombre': 'Macetero de cemento gris 40 cm',
        'precio': 24990,
        'stock': 20,
        'stock_minimo': 4,
        'modelo': 'MAC-CEM-40',
        'contenido': '28.000',
        'unidad_contenido': 'l',
        'uso': 'Macetero pesado para arbustos y plantas ornamentales que requieran mayor estabilidad en exterior.',
        'especificaciones': {
            'Material declarado': 'Cemento',
            'Diámetro superior declarado': '40 cm',
            'Capacidad aproximada': '28 L',
            'Drenaje': 'Orificio inferior',
            'Color': 'Gris',
        },
    },
    {
        'sku': 'SFI-JAR-MAC-TEX-30',
        'nombre': 'Macetero textil geotextil 30 L con asas',
        'precio': 5990,
        'stock': 55,
        'stock_minimo': 10,
        'modelo': 'MAC-TEX-30L',
        'contenido': '30.000',
        'unidad_contenido': 'l',
        'uso': 'Contenedor flexible para cultivo de hortalizas, flores o plantas en patios y huertos domésticos.',
        'especificaciones': {
            'Material declarado': 'Geotextil',
            'Capacidad declarada': '30 L',
            'Transporte': 'Asas laterales',
            'Drenaje': 'Material permeable',
            'Color': 'Negro',
        },
    },
    {
        'sku': 'SFI-JAR-PLA-MAC-30',
        'nombre': 'Plato recolector para macetero 30 cm terracota',
        'precio': 1490,
        'stock': 90,
        'stock_minimo': 15,
        'modelo': 'PLA-MAC-30',
        'contenido': '1.000',
        'unidad_contenido': 'unidad',
        'uso': 'Recoge el excedente de riego bajo maceteros compatibles para proteger pisos y superficies interiores.',
        'especificaciones': {
            'Material declarado': 'Plástico',
            'Diámetro declarado': '30 cm',
            'Compatibilidad': 'Maceteros de diámetro similar o menor',
            'Color': 'Terracota',
        },
    },
]


def cargar_catalogo_maceteros(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Proveedor = apps.get_model('productos', 'Proveedor')
    proveedor = Proveedor.objects.filter(
        nombre='Proveedor General SFI', activo=True,
    ).first()

    for registro in PRODUCTOS_MACETEROS:
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
                'categoria': 'Otra',
                'activo': True,
                'marca': 'Genérico SFI',
                'ambiente_uso': 'interior_exterior',
                'proveedor_id': proveedor.pk if proveedor else None,
                'unidad_venta': 'unidad',
                'tipo_calculo': 'unidad',
                'rendimiento': None,
                'unidad_rendimiento': '',
                'porcentaje_desperdicio': '0.00',
                'uso_recomendado': uso,
                'especificaciones': {
                    **especificaciones,
                    'Estado de ficha': 'Datos de catálogo interno; validar dimensiones y drenaje con proveedor antes de compra.',
                },
                'informacion_tecnica_verificada': False,
            },
        )


def retirar_catalogo_maceteros(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.filter(sku__startswith='SFI-JAR-').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('productos', '0032_catalogo_soldadura'),
    ]

    operations = [
        migrations.RunPython(cargar_catalogo_maceteros, retirar_catalogo_maceteros),
    ]
