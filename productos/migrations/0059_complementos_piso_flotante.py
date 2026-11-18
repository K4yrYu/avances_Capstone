from decimal import Decimal

from django.db import migrations


PRODUCTOS = (
    {
        'sku': 'SFI-PFL-VAP-AQUA-40',
        'nombre': 'Barrera de vapor polietileno Aquastop rollo 40 m²',
        'marca': 'Aquastop',
        'precio': 39600,
        'stock': 24,
        'unidad_venta': 'rollo',
        'contenido': Decimal('40.000'),
        'unidad_contenido': 'm2',
        'tipo_calculo': 'superficie',
        'rendimiento': Decimal('40.000'),
        'unidad_rendimiento': 'm2_unidad',
        'uso': (
            'Barrera de vapor para bases cementicias bajo manta y piso flotante. '
            'La continuidad, los traslapos y la compatibilidad deben confirmarse '
            'según la ficha del piso seleccionado.'
        ),
        'fuente': 'https://pisochile.cl/producto/polietileno-aquastop-40-m2/',
    },
    {
        'sku': 'SFI-PFL-PER-T-200',
        'nombre': 'Perfil T níquel mate 20 x 8 mm x 2 m',
        'marca': 'Genérico',
        'precio': 4990,
        'stock': 45,
        'unidad_venta': 'unidad',
        'contenido': Decimal('2.000'),
        'unidad_contenido': 'm',
        'tipo_calculo': 'longitud',
        'rendimiento': Decimal('2.000'),
        'unidad_rendimiento': 'm_unidad',
        'uso': (
            'Perfil de transición para encuentros entre pisos. La cantidad depende '
            'del ancho y número de puertas o cambios de revestimiento.'
        ),
        'fuente': 'https://www.pisoymuro.cl/categoria-producto/piso-perfiles-para-flotante-y-spc/',
    },
    {
        'sku': 'SFI-PFL-KIT-INST',
        'nombre': 'Kit de instalación para piso laminado',
        'marca': 'Toolmak',
        'precio': 8000,
        'stock': 20,
        'unidad_venta': 'juego',
        'contenido': Decimal('1.000'),
        'unidad_contenido': 'unidad',
        'tipo_calculo': 'ninguno',
        'rendimiento': None,
        'unidad_rendimiento': '',
        'uso': (
            'Juego opcional con bloque de impacto, barra de tracción y separadores '
            'para respetar la junta perimetral durante la instalación.'
        ),
        'fuente': 'https://efloan.cl/products/kit-instalacion-piso-laminado-toolmak',
    },
)


def crear_complementos(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    for registro in PRODUCTOS:
        Producto.objects.update_or_create(
            sku=registro['sku'],
            defaults={
                'nombre': registro['nombre'],
                'descripcion': registro['uso'],
                'precio': registro['precio'],
                'imagen': '',
                'stock': registro['stock'],
                'stock_minimo': 4,
                'categoria': 'Construcción',
                'marca': registro['marca'],
                'modelo': registro['nombre'][:120],
                'ambiente_uso': 'interior',
                'activo': True,
                'unidad_venta': registro['unidad_venta'],
                'contenido': registro['contenido'],
                'unidad_contenido': registro['unidad_contenido'],
                'tipo_calculo': registro['tipo_calculo'],
                'rendimiento': registro['rendimiento'],
                'unidad_rendimiento': registro['unidad_rendimiento'],
                'porcentaje_desperdicio': Decimal('0.00'),
                'uso_recomendado': registro['uso'],
                'especificaciones': {
                    'aplicacion': 'piso flotante',
                    'fuente_tecnica': registro['fuente'],
                    'requiere_confirmar_compatibilidad': True,
                },
                'informacion_tecnica_verificada': True,
            },
        )


def eliminar_complementos(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.filter(sku__in=[item['sku'] for item in PRODUCTOS]).delete()


class Migration(migrations.Migration):
    dependencies = [('productos', '0058_pisos_flotantes_laminados')]

    operations = [migrations.RunPython(crear_complementos, eliminar_complementos)]
