from django.db import migrations


PRODUCTOS = (
    {
        'sku': 'SFI-ELE-ADA-EU-CL-10A',
        'nombre': 'Adaptador enchufe europeo a chileno Schuko 10 A 250 V',
        'descripcion': (
            'Adaptador para conectar un enchufe europeo Schuko a una toma '
            'compatible en Chile, conservando la conexión a tierra cuando el '
            'sistema completo es compatible.'
        ),
        'precio': 4390,
        'stock': 45,
        'stock_minimo': 8,
        'categoria': 'Electricidad',
        'marca': 'Fenix',
        'modelo': 'ASHUKO',
        'imagen': 'productos/Adaptador_enchufe_europeo_a_chileno_Schuko_10A_250V.jpg',
        'unidad_venta': 'unidad',
        'contenido': '1.000',
        'unidad_contenido': 'unidad',
        'uso_recomendado': (
            'Adaptar enchufes europeos Schuko a una toma chilena compatible '
            'en equipos de hasta 10 A y 250 V.'
        ),
        'especificaciones': {
            'Tipo': 'Adaptador europeo Schuko a chileno',
            'Entrada': 'Enchufe europeo Schuko 2P+T',
            'Salida': 'Toma compatible con estándar chileno',
            'Tensión nominal': '250 V~',
            'Corriente máxima': '10 A',
            'Potencia máxima declarada': '1500 W',
            'Conexión a tierra': '2 polos + tierra',
            'Seguridad': 'Confirmar certificación SEC vigente y compatibilidad antes de usar.',
            'No convierte': 'Voltaje ni frecuencia eléctrica.',
        },
    },
    {
        'sku': 'SFI-ELE-ADA-EUROAM-10A',
        'nombre': 'Adaptador euroamericano 2P 10 A 250 V',
        'descripcion': (
            'Adaptador de dos polos para usar enchufes europeos en tomas '
            'americanas o chilenas compatibles, sin conversión de voltaje.'
        ),
        'precio': 2190,
        'stock': 60,
        'stock_minimo': 10,
        'categoria': 'Electricidad',
        'marca': 'Vimar',
        'modelo': 'S10 01352',
        'imagen': 'productos/Adaptador_euroamericano_Vimar_2P_10A_250V.jpg',
        'unidad_venta': 'unidad',
        'contenido': '1.000',
        'unidad_contenido': 'unidad',
        'uso_recomendado': (
            'Adaptar un enchufe europeo de dos polos a un tomacorriente '
            'compatible de estándar americano o chileno.'
        ),
        'especificaciones': {
            'Tipo': 'Adaptador euroamericano',
            'Polos': '2P',
            'Tensión nominal': '250 V~',
            'Corriente máxima': '10 A',
            'Material': 'Plástico aislante',
            'Compatibilidad': 'Enchufe europeo de dos polos y toma compatible.',
            'No incluye': 'Conversión de voltaje, transformador ni conexión a tierra.',
            'Seguridad': 'Verificar potencia del artefacto y estado de la toma antes de usar.',
        },
    },
    {
        'sku': 'SFI-ELE-ADA-UNIV-VIAJE',
        'nombre': 'Adaptador universal de viaje US EU UK AU 10 A 250 V',
        'descripcion': (
            'Adaptador universal plegable para enchufes de los formatos US, '
            'EU, UK y AU en tomas compatibles; pensado para viajes y equipos de baja potencia.'
        ),
        'precio': 8990,
        'stock': 30,
        'stock_minimo': 5,
        'categoria': 'Electricidad',
        'marca': 'Genérico SFI',
        'modelo': 'Universal viaje 4 formatos',
        'imagen': 'productos/Adaptador_universal_viaje_US_EU_UK_AU_10A_250V.jpg',
        'unidad_venta': 'unidad',
        'contenido': '1.000',
        'unidad_contenido': 'unidad',
        'uso_recomendado': (
            'Conectar equipos compatibles durante viajes utilizando formatos '
            'de enchufe US, EU, UK o AU.'
        ),
        'especificaciones': {
            'Tipo': 'Adaptador universal de viaje',
            'Formatos compatibles': 'US, EU, UK y AU',
            'Tensión máxima': '250 V~',
            'Corriente máxima': '10 A',
            'Entradas y salidas': 'Una conexión a la vez',
            'Material': 'Plástico ABS',
            'Uso': 'Viaje y compatibilidad física de enchufes.',
            'No convierte': 'Voltaje ni frecuencia; no reemplaza un transformador.',
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
    dependencies = [('productos', '0070_flexible_calefont_y_copla_pvc')]

    operations = [migrations.RunPython(registrar_productos, retirar_productos)]
