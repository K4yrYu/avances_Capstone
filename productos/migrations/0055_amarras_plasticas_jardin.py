from django.db import migrations


SKU = 'SFI-JAR-AMA-PLA-20-50'


def registrar_amarras_jardin(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Proveedor = apps.get_model('productos', 'Proveedor')
    proveedor = Proveedor.objects.filter(
        nombre='Proveedor General SFI', activo=True,
    ).first()

    Producto.objects.update_or_create(
        sku=SKU,
        defaults={
            'nombre': 'Amarras plásticas para jardín 20 cm pack 50',
            'descripcion': (
                'Sujetar tallos y ramas a tutores, enrejados o soportes de jardín '
                'sin usar alambre rígido directamente sobre la planta.'
            ),
            'precio': 2490,
            'imagen': '',
            'stock': 90,
            'stock_minimo': 15,
            'categoria': 'Jardinería',
            'marca': 'Genérico SFI',
            'modelo': SKU,
            'ambiente_uso': 'exterior',
            'superficies_compatibles': [],
            'tipo_pintura': 'no_aplica',
            'terminacion': 'no_aplica',
            'propiedades_pintura': [],
            'preparaciones_recomendadas': [],
            'unidad_venta': 'paquete',
            'contenido': '50.000',
            'unidad_contenido': 'unidad',
            'tipo_calculo': 'unidad',
            'rendimiento': None,
            'unidad_rendimiento': '',
            'porcentaje_desperdicio': '0.00',
            'proveedor_id': proveedor.pk if proveedor else None,
            'uso_recomendado': (
                'Fijar plantas, tallos o ramas a tutores y soportes de jardín '
                'sin apretar en exceso para permitir su crecimiento.'
            ),
            'especificaciones': {
                'Tipo': 'Amarra plástica para jardín',
                'Largo': '20 cm',
                'Contenido': 'Pack de 50 unidades',
                'Uso recomendado': 'Tutores de bambú, enrejados, huertos y plantas trepadoras',
                'Instalación': (
                    'Rodear suavemente el tallo y el tutor, dejando holgura para '
                    'evitar dañar la planta durante su crecimiento.'
                ),
                'Advertencia': (
                    'Revisar periódicamente el ajuste y reemplazar las amarras '
                    'deterioradas por exposición exterior.'
                ),
                'Términos relacionados': (
                    'amarras jardín, amarra plantas, sujetar tutor, amarras plásticas, '
                    'plantas trepadoras'
                ),
            },
            'informacion_tecnica_verificada': True,
            'activo': True,
        },
    )


def retirar_amarras_jardin(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.filter(sku=SKU).delete()


class Migration(migrations.Migration):
    dependencies = [('productos', '0054_tapagoteras_wet_dynal_1kg')]

    operations = [
        migrations.RunPython(registrar_amarras_jardin, retirar_amarras_jardin),
    ]
