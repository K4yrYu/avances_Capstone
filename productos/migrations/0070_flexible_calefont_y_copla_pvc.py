from django.db import migrations


PRODUCTOS = (
    {
        'sku': 'SFI-GAS-FLE-CAL-20',
        'nombre': 'Flexible agua para calefont HI-HE 1/2 pulgada x 20 cm',
        'descripcion': (
            'Flexible mallado de acero inoxidable para conectar el agua a un '
            'calefont compatible.'
        ),
        'precio': 4990,
        'imagen': 'productos/Flexible_agua_calefont_HI_HE_12_20_cm.jpg',
        'stock': 50,
        'stock_minimo': 10,
        'categoria': 'Gasfitería',
        'marca': 'Stretto',
        'modelo': 'Flexible calefont HI-HE 1/2 x 20 cm',
        'unidad_venta': 'unidad',
        'contenido': '0.200',
        'unidad_contenido': 'm',
        'uso_recomendado': (
            'Conectar la entrada o salida de agua de un calefont compatible, '
            'verificando roscas, largo y especificación del fabricante.'
        ),
        'especificaciones': {
            'Tipo': 'Flexible mallado para agua de calefont',
            'Conexión': 'HI-HE 1/2 pulgada',
            'Largo': '20 cm',
            'Material exterior': 'Acero inoxidable mallado',
            'Uso': 'Agua fría o caliente en calefont compatible',
            'Compatibilidad': 'Confirmar tipo de rosca y distancia entre conexiones.',
            'Instalación': (
                'Revisar sellos y no forzar las roscas. La instalación del '
                'calefont debe realizarla personal autorizado cuando corresponda.'
            ),
        },
    },
    {
        'sku': 'SFI-GAS-COP-PVC-40',
        'nombre': 'Copla PVC sanitaria 40 mm',
        'descripcion': (
            'Accesorio de PVC sanitario para unir dos tubos de 40 mm en línea recta.'
        ),
        'precio': 1490,
        'imagen': 'productos/Copla_PVC_sanitaria_40_mm.jpg',
        'stock': 120,
        'stock_minimo': 20,
        'categoria': 'Gasfitería',
        'marca': 'Amanco',
        'modelo': 'Copla sanitaria lisa 40 mm',
        'unidad_venta': 'unidad',
        'contenido': '1.000',
        'unidad_contenido': 'unidad',
        'uso_recomendado': (
            'Unir dos tramos rectos de tubo PVC sanitario de 40 mm mediante '
            'adhesivo compatible para PVC.'
        ),
        'especificaciones': {
            'Tipo': 'Copla sanitaria lisa',
            'Diámetro nominal': '40 mm',
            'Material': 'PVC sanitario',
            'Unión': 'Cementada con adhesivo compatible para PVC',
            'Uso': 'Unir tramos rectos de desagüe sanitario de 40 mm',
            'No usar para': 'Gas ni redes de presión sin confirmar compatibilidad.',
            'Instalación': 'Limpiar, presentar y cementar según la ficha del adhesivo.',
        },
    },
)


def registrar_productos(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Proveedor = apps.get_model('productos', 'Proveedor')
    proveedor = Proveedor.objects.filter(
        nombre='Proveedor General SFI', activo=True,
    ).first()

    for datos in PRODUCTOS:
        Producto.objects.update_or_create(
            sku=datos['sku'],
            defaults={
                **datos,
                'ambiente_uso': 'interior',
                'superficies_compatibles': [],
                'tipo_pintura': 'no_aplica',
                'terminacion': 'no_aplica',
                'propiedades_pintura': [],
                'preparaciones_recomendadas': [],
                'tipo_calculo': 'ninguno',
                'rendimiento': None,
                'unidad_rendimiento': '',
                'porcentaje_desperdicio': '0.00',
                'proveedor_id': proveedor.pk if proveedor else None,
                'informacion_tecnica_verificada': True,
                'activo': True,
            },
        )


def retirar_productos(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.filter(sku__in=[producto['sku'] for producto in PRODUCTOS]).delete()


class Migration(migrations.Migration):
    dependencies = [('productos', '0069_flexible_ducha_acero_inoxidable')]

    operations = [
        migrations.RunPython(registrar_productos, retirar_productos),
    ]
