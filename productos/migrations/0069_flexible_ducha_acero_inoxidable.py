from django.db import migrations


SKU = 'SFI-GAS-FLE-DUC-150'
IMAGEN = 'productos/Flexible_ducha_acero_inoxidable_150_cm.jpg'


def registrar_flexible_ducha(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Proveedor = apps.get_model('productos', 'Proveedor')
    proveedor = Proveedor.objects.filter(
        nombre='Proveedor General SFI', activo=True,
    ).first()

    Producto.objects.update_or_create(
        sku=SKU,
        defaults={
            'nombre': 'Flexible de ducha acero inoxidable cromado 1,5 m',
            'descripcion': (
                'Manguera flexible para conectar el monomando o salida de agua con '
                'una ducha teléfono compatible.'
            ),
            'precio': 10990,
            'imagen': IMAGEN,
            'stock': 40,
            'stock_minimo': 8,
            'categoria': 'Gasfitería',
            'marca': 'Duschy',
            'modelo': 'Manguera flexible 1,5 m metal cromo',
            'ambiente_uso': 'interior',
            'superficies_compatibles': [],
            'tipo_pintura': 'no_aplica',
            'terminacion': 'no_aplica',
            'propiedades_pintura': [],
            'preparaciones_recomendadas': [],
            'unidad_venta': 'unidad',
            'contenido': '1.500',
            'unidad_contenido': 'm',
            'tipo_calculo': 'ninguno',
            'rendimiento': None,
            'unidad_rendimiento': '',
            'porcentaje_desperdicio': '0.00',
            'proveedor_id': proveedor.pk if proveedor else None,
            'uso_recomendado': (
                'Reemplazar o instalar el flexible entre el monomando y la ducha '
                'teléfono cuando ambas conexiones sean compatibles.'
            ),
            'especificaciones': {
                'Tipo': 'Manguera flexible para ducha teléfono',
                'Material': 'Acero inoxidable',
                'Terminación': 'Metal cromado',
                'Largo': '1,5 m',
                'Modelo': 'Manguera flexible',
                'Compatibilidad': (
                    'Verificar el tipo y diámetro de rosca del monomando y de la '
                    'ducha teléfono antes de comprar.'
                ),
                'Instalación': (
                    'Enroscar manualmente con sus sellos en buen estado; no forzar '
                    'las conexiones ni usar el flexible dañado.'
                ),
                'Uso recomendado': 'Baños y duchas con ducha teléfono compatible.',
            },
            'informacion_tecnica_verificada': True,
            'activo': True,
        },
    )


def retirar_flexible_ducha(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.filter(sku=SKU).delete()


class Migration(migrations.Migration):
    dependencies = [('productos', '0068_asociar_imagenes_productos')]

    operations = [
        migrations.RunPython(registrar_flexible_ducha, retirar_flexible_ducha),
    ]
