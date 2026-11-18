from decimal import Decimal

from django.db import migrations


PRODUCTOS = (
    {
        'sku': 'SFI-PFL-GRAFITO-244',
        'nombre': 'Piso flotante Roble Grafito AC4 8 mm caja 2,44 m²',
        'marca': 'Lautaro',
        'color': 'Roble grafito',
        'precio': 18300,
        'cobertura': '2.440',
        'stock': 36,
        'ambientes': ['dormitorio', 'living_comedor', 'pasillo', 'oficina'],
        'ficha': {
            'espesor_mm': 8, 'abrasion': 'AC4', 'clase_uso': '32',
            'sistema_union': 'Click', 'resistencia_agua_horas': None,
            'fuente_tecnica': 'https://lautaromc.cl/categoria/pisos/',
        },
    },
    {
        'sku': 'SFI-PFL-MARENGO-244',
        'nombre': 'Piso flotante Gris Marengo AC4 8 mm caja 2,44 m²',
        'marca': 'Lautaro',
        'color': 'Gris marengo',
        'precio': 18300,
        'cobertura': '2.440',
        'stock': 34,
        'ambientes': ['dormitorio', 'living_comedor', 'pasillo', 'oficina'],
        'ficha': {
            'espesor_mm': 8, 'abrasion': 'AC4', 'clase_uso': '32',
            'sistema_union': 'Click', 'resistencia_agua_horas': None,
            'fuente_tecnica': 'https://lautaromc.cl/categoria/pisos/',
        },
    },
    {
        'sku': 'SFI-PFL-WALNUT-244',
        'nombre': 'Piso flotante Walnut AC4 8 mm caja 2,44 m²',
        'marca': 'Lautaro',
        'color': 'Nogal oscuro',
        'precio': 19276,
        'cobertura': '2.440',
        'stock': 32,
        'ambientes': ['dormitorio', 'living_comedor', 'pasillo', 'oficina'],
        'ficha': {
            'espesor_mm': 8, 'abrasion': 'AC4', 'clase_uso': '32',
            'sistema_union': 'Click', 'resistencia_agua_horas': None,
            'fuente_tecnica': 'https://lautaromc.cl/categoria/pisos/',
        },
    },
    {
        'sku': 'SFI-PFL-EVOKE-244',
        'nombre': 'Piso flotante Evoke Concrete AC4 8 mm caja 2,44 m²',
        'marca': 'Lautaro',
        'color': 'Gris concreto',
        'precio': 21716,
        'cobertura': '2.440',
        'stock': 28,
        'ambientes': ['dormitorio', 'living_comedor', 'pasillo', 'oficina'],
        'ficha': {
            'espesor_mm': 8, 'abrasion': 'AC4', 'clase_uso': '32',
            'sistema_union': 'Click', 'resistencia_agua_horas': None,
            'fuente_tecnica': 'https://lautaromc.cl/categoria/pisos/',
        },
    },
    {
        'sku': 'SFI-PFL-DANUBE-190',
        'nombre': 'Piso fotolaminado River Danube AC4 8 mm caja 1,90 m²',
        'marca': 'Kastamonu',
        'color': 'Roble natural',
        'precio': 24824,
        'cobertura': '1.899',
        'stock': 30,
        'ambientes': ['dormitorio', 'living_comedor', 'pasillo', 'oficina', 'cocina'],
        'ficha': {
            'espesor_mm': 8, 'abrasion': 'AC4', 'clase_uso': '32',
            'formato_mm': '1205 x 197', 'sistema_union': 'Uniclic',
            'resistencia_agua_horas': 72,
            'fuente_tecnica': 'https://www.abkupfer.cl/piso-fotolaminado-river-danube-ac4-1205x197x8-mm/p',
        },
    },
    {
        'sku': 'SFI-PFL-GANGES-190',
        'nombre': 'Piso fotolaminado River Ganges AC4 8 mm caja 1,90 m²',
        'marca': 'Kastamonu',
        'color': 'Gris natural',
        'precio': 26567,
        'cobertura': '1.899',
        'stock': 26,
        'ambientes': ['dormitorio', 'living_comedor', 'pasillo', 'oficina'],
        'ficha': {
            'espesor_mm': 8, 'abrasion': 'AC4', 'formato_mm': '1205 x 197',
            'sistema_union': 'Click', 'resistencia_agua_horas': None,
            'fuente_tecnica': 'https://www.pyramid.cl/inicio/209-piso-fotolaminado-river-ganges-197-x-1205-x-8-mm.html',
        },
    },
    {
        'sku': 'SFI-PFL-KRONOTEX-213',
        'nombre': 'Piso flotante Kronotex Roble Marrón AC4 8 mm caja 2,13 m²',
        'marca': 'Kronotex',
        'color': 'Roble marrón',
        'precio': 31929,
        'cobertura': '2.130',
        'stock': 24,
        'ambientes': ['dormitorio', 'living_comedor', 'pasillo', 'oficina'],
        'ficha': {
            'espesor_mm': 8, 'abrasion': 'AC4', 'clase_uso': '32',
            'sistema_union': 'Click 5G', 'resistencia_agua_horas': None,
            'fuente_tecnica': 'https://www.floorcarpet.cl/product-page/piso-flotante-kronotex-roble-marr%C3%B3n-biselado-8-mm',
        },
    },
)


def crear_productos(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    for registro in PRODUCTOS:
        ficha = {
            'tipo_piso': 'laminado',
            'aplicacion': 'piso',
            'ambientes_recomendados': registro['ambientes'],
            'requiere_manta': True,
            'requiere_revision_barrera_vapor': True,
            'instalacion': 'Flotante',
            **registro['ficha'],
        }
        Producto.objects.update_or_create(
            sku=registro['sku'],
            defaults={
                'nombre': registro['nombre'],
                'descripcion': (
                    'Piso laminado de instalación flotante. La base debe estar firme, '
                    'seca, limpia y nivelada; la manta y barrera de vapor se seleccionan '
                    'según la base y las instrucciones del fabricante.'
                ),
                'precio': registro['precio'],
                'imagen': '',
                'stock': registro['stock'],
                'stock_minimo': 5,
                'categoria': 'Construcción',
                'marca': registro['marca'],
                'modelo': registro['nombre'][:120],
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
                    'Pisos interiores sobre una base compatible, firme, seca y nivelada. '
                    'Revisar en la ficha los ambientes recomendados y la resistencia al agua.'
                ),
                'especificaciones': ficha,
                'informacion_tecnica_verificada': True,
            },
        )


def eliminar_productos(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.filter(sku__in=[item['sku'] for item in PRODUCTOS]).delete()


class Migration(migrations.Migration):
    dependencies = [('productos', '0057_clasificacion_ceramicas_por_uso')]

    operations = [migrations.RunPython(crear_productos, eliminar_productos)]
