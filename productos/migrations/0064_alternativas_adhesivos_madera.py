from decimal import Decimal

from django.db import migrations


PRODUCTOS = (
    {
        'sku': 'SFI-ADH-WAL-MAD-250',
        'nombre': 'Adhesivo cola fría para madera Waltek 250 g',
        'marca': 'Waltek',
        'modelo': 'WKA01103',
        'precio': 1890,
        'stock': 40,
        'contenido': '250.000',
        'descripcion': (
            'Cola fría en formato pequeño para pegado doméstico de piezas de madera '
            'porosas, limpias y con buen ajuste.'
        ),
        'uso_recomendado': (
            'Reparaciones pequeñas y ensambles interiores de madera que puedan '
            'mantenerse prensados durante el secado.'
        ),
        'especificaciones': {
            'familia_adhesivo': 'cola fría PVA para madera',
            'nivel_prestacion': 'económico',
            'ambiente': 'interior seco',
            'materiales_compatibles': ['madera', 'tableros de madera porosos'],
            'preparacion': 'Superficies limpias, secas, sin polvo ni grasa y con buen encaje',
            'aplicacion_recomendada': 'Aplicar una capa uniforme, unir y mantener prensado según el envase',
            'cantidad_orientativa': 'Una presentación de 250 g sirve para reparaciones pequeñas; el consumo depende del área y porosidad',
            'fuente_tecnica': 'https://www.easy.cl/adhesivo-cola-fria-para-madera-500g-waltek-mkd1wdbgru/p',
            'fuente_precio': 'https://www.evepro.cl/collections/adhesivos-y-espumas',
        },
    },
    {
        'sku': 'SFI-ADH-AFX-PIN-500',
        'nombre': 'Cola fría Afix madera pintable 500 g',
        'marca': 'Afix',
        'modelo': 'Madera Pintable 500 g',
        'precio': 3590,
        'stock': 38,
        'contenido': '500.000',
        'descripcion': (
            'Adhesivo acuoso para madera con terminación pintable, destinado a trabajos '
            'domésticos, manualidades y uniones interiores compatibles.'
        ),
        'uso_recomendado': (
            'Pegado interior de madera, papel y cartón, especialmente cuando la unión '
            'deba recibir una terminación pintada.'
        ),
        'especificaciones': {
            'familia_adhesivo': 'cola fría PVA pintable',
            'nivel_prestacion': 'económico',
            'ambiente': 'interior seco',
            'acabado': 'mate y pintable',
            'materiales_compatibles': ['madera', 'papel', 'cartón'],
            'preparacion': 'Superficies limpias, secas y ajustadas',
            'aplicacion_recomendada': 'Aplicar uniformemente y mantener las piezas prensadas durante el secado',
            'cantidad_orientativa': 'Depende del área, porosidad y ajuste de la unión',
            'fuente_tecnica': 'https://www.youtube.com/watch?v=FfvkgK1W4zs',
            'fuente_precio': 'https://www.easy.cl/materiales-de-construccion/adhesivos-y-selladores/cola-fria',
        },
    },
    {
        'sku': 'SFI-ADH-SIK-232-500',
        'nombre': 'SikaBond-232 cola fría profesional para madera 500 g',
        'marca': 'Sika',
        'modelo': 'SikaBond-232 500 g',
        'precio': 6850,
        'stock': 28,
        'contenido': '500.000',
        'descripcion': (
            'Adhesivo profesional extra rápido de polivinilacetato para ensambles de '
            'muebles, maderas nobles, maderas densas y otros materiales porosos.'
        ),
        'uso_recomendado': (
            'Ensambles, entarugados y reparaciones de muebles interiores que requieran '
            'curado rápido y prensado controlado.'
        ),
        'especificaciones': {
            'familia_adhesivo': 'cola fría PVA profesional D2',
            'nivel_prestacion': 'profesional',
            'ambiente': 'interior; humedad ocasional conforme a clase D2',
            'norma_resistencia': 'DIN EN 204 D2',
            'materiales_compatibles': ['madera', 'maderas nobles', 'maderas densas', 'papel', 'cartón', 'corcho'],
            'humedad_madera': '8-12 %',
            'consumo': '100-200 g/m²',
            'tiempo_abierto_minutos': 8,
            'tiempo_prensado_minutos': 15,
            'curado_maximo_horas': 24,
            'preparacion': 'Superficies limpias, secas, ajustadas y madera con 8-12 % de humedad',
            'aplicacion_recomendada': 'Aplicar uniformemente, unir y prensar; resistencia máxima a las 24 horas',
            'cantidad_orientativa': '100-200 g/m² según porosidad, geometría y condiciones de aplicación',
            'fuente_tecnica': 'https://chl.sika.com/dam/dms/cl01/e/sikabond-232-professionalwoodglue.pdf',
            'fuente_precio': 'https://matscann.com/producto/447957',
        },
    },
    {
        'sku': 'SFI-ADH-AGO-PRO-1000',
        'nombre': 'Agorex Profesional cola fría extra rápida 1 kg',
        'marca': 'Agorex',
        'modelo': 'Profesional Extra Rápida 1 kg',
        'precio': 10990,
        'stock': 24,
        'contenido': '1000.000',
        'descripcion': (
            'Cola fría profesional de base acuosa y secado rápido para ensambles, '
            'enchapes, entarugados y trabajos de carpintería de mayor volumen.'
        ),
        'uso_recomendado': (
            'Fabricación y reparación interior de muebles, ensambles, enchapes y '
            'entarugados cuando se requiera una presentación de mayor capacidad.'
        ),
        'especificaciones': {
            'familia_adhesivo': 'cola fría profesional para madera',
            'nivel_prestacion': 'profesional',
            'ambiente': 'interior',
            'materiales_compatibles': ['madera', 'chapas de madera', 'papel', 'cartón', 'corcho'],
            'tiempo_prensado_minutos': 15,
            'preparacion': 'Superficies limpias, secas y con ajuste correcto',
            'aplicacion_recomendada': 'Aplicar en una superficie, unir, prensar 15 minutos y limpiar el exceso antes de secar',
            'cantidad_orientativa': 'Formato de 1 kg para trabajos repetidos o de mayor superficie; calcular según la unión',
            'fuente_tecnica': 'https://henkeltepremia.cl/wp-content/uploads/2021/01/Catalogo-Henkel-AC-2021.pdf',
            'fuente_precio': 'https://www.easy.cl/materiales-de-construccion/adhesivos-y-selladores/cola-fria',
        },
    },
)


def crear_productos(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    for registro in PRODUCTOS:
        Producto.objects.update_or_create(
            sku=registro['sku'],
            defaults={
                'nombre': registro['nombre'],
                'descripcion': registro['descripcion'],
                'precio': registro['precio'],
                'imagen': '',
                'stock': registro['stock'],
                'stock_minimo': 5,
                'categoria': 'Adhesivos',
                'marca': registro['marca'],
                'modelo': registro['modelo'],
                'ambiente_uso': 'interior',
                'superficies_compatibles': ['madera'],
                'activo': True,
                'unidad_venta': 'envase',
                'contenido': Decimal(registro['contenido']),
                'unidad_contenido': 'g',
                'tipo_calculo': 'ninguno',
                'rendimiento': None,
                'unidad_rendimiento': '',
                'porcentaje_desperdicio': Decimal('0.00'),
                'uso_recomendado': registro['uso_recomendado'],
                'especificaciones': {
                    **registro['especificaciones'],
                    'fecha_consulta_fuente': '2026-11-18',
                },
                'informacion_tecnica_verificada': True,
            },
        )


def eliminar_productos(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.filter(sku__in=[item['sku'] for item in PRODUCTOS]).delete()


class Migration(migrations.Migration):
    dependencies = [('productos', '0063_permitir_producto_sin_imagen')]

    operations = [migrations.RunPython(crear_productos, eliminar_productos)]
