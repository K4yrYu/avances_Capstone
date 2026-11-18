from decimal import Decimal

from django.db import migrations


PRODUCTOS = (
    {
        'sku': 'SFI-PFL-ESSEN-296',
        'nombre': 'Piso laminado Essen Café Claro AC3 6 mm caja 2,96 m²',
        'modelo': 'Essen',
        'color': 'Café claro',
        'precio': 17727,
        'cobertura': '2.960',
        'stock': 42,
        'espesor': 6,
        'formato': '1290 x 194',
        'fuente': 'https://www.sodimac.cl/sodimac-cl/articulo/143308402/piso-laminado-6-mm-essen-cafe-claro-2-96-m2',
    },
    {
        'sku': 'SFI-PFL-BONN-300',
        'nombre': 'Piso laminado Bonn Café AC3 6 mm caja 3,00 m²',
        'modelo': 'Bonn',
        'color': 'Café',
        'precio': 19470,
        'cobertura': '3.000',
        'stock': 38,
        'espesor': 6,
        'formato': '1290 x 194',
        'fuente': 'https://www.sodimac.cl/sodimac-cl/articulo/143308412/piso-laminado-6-mm-bonn-cafe-3-m2',
    },
    {
        'sku': 'SFI-PFL-MISTY-238',
        'nombre': 'Piso laminado Misty Gris AC3 7 mm caja 2,38 m²',
        'modelo': 'Misty',
        'color': 'Gris',
        'precio': 16636,
        'cobertura': '2.380',
        'stock': 40,
        'espesor': 7,
        'formato': '1216 x 196',
        'fuente': 'https://www.sodimac.cl/sodimac-cl/articulo/150286825/piso-laminado-2-38-m2/150286826',
    },
)


def crear_productos(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    for registro in PRODUCTOS:
        Producto.objects.update_or_create(
            sku=registro['sku'],
            defaults={
                'nombre': registro['nombre'],
                'descripcion': (
                    'Piso laminado económico para uso residencial interior, con instalación '
                    'flotante mediante sistema click. Requiere una base firme, seca, limpia y '
                    'nivelada; no incluye manta y posee baja resistencia a la humedad.'
                ),
                'precio': registro['precio'],
                'imagen': '',
                'stock': registro['stock'],
                'stock_minimo': 5,
                'categoria': 'Construcción',
                'marca': 'Holztek',
                'modelo': registro['modelo'],
                'color': registro['color'],
                'ambiente_uso': 'interior',
                'activo': True,
                'unidad_venta': 'caja',
                'contenido': Decimal(registro['cobertura']),
                'unidad_contenido': 'm2',
                'tipo_calculo': 'superficie',
                'rendimiento': Decimal(registro['cobertura']),
                'unidad_rendimiento': 'm2_unidad',
                'porcentaje_desperdicio': Decimal('10.00'),
                'uso_recomendado': (
                    'Dormitorios, living y comedor de uso residencial interior. Confirmar '
                    'humedad, nivelación, manta y barrera de vapor antes de instalar.'
                ),
                'especificaciones': {
                    'tipo_piso': 'laminado',
                    'aplicacion': 'piso',
                    'ambientes_recomendados': ['dormitorio', 'living_comedor'],
                    'requiere_manta': True,
                    'requiere_revision_barrera_vapor': True,
                    'instalacion': 'Click patentado',
                    'espesor_mm': registro['espesor'],
                    'abrasion': 'AC3',
                    'clase_uso': '31',
                    'resistencia_trafico': 'Medio' if registro['modelo'] == 'Misty' else 'Bajo',
                    'resistencia_humedad': 'Baja',
                    'formato_mm': registro['formato'],
                    'acabado': 'Mate',
                    'resistencia_agua_horas': None,
                    'fuente_tecnica': registro['fuente'],
                    'fecha_consulta_fuente': '2026-11-18',
                },
                'informacion_tecnica_verificada': True,
            },
        )


def eliminar_productos(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.filter(sku__in=[item['sku'] for item in PRODUCTOS]).delete()


class Migration(migrations.Migration):
    dependencies = [('productos', '0060_corregir_unidad_manta_piso_flotante')]

    operations = [migrations.RunPython(crear_productos, eliminar_productos)]
