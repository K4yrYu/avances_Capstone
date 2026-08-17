from django.db import migrations


FAMILIAS = [
    {
        'base_pk': 5,
        'prefijo': 'LTX',
        'precio': 22990,
        'colores': [
            ('CW004W', 'Delicate Blue', '#DCE7EA'),
            ('CW015W', 'Perfect Mint', '#DDE8D5'),
            ('CW022W', 'Soft Gold', '#E8C875'),
            ('CW053W', 'Natural Bisque', '#D9C6A8'),
            ('CW059W', 'Fog Mist', '#B8BEC1'),
            ('AC116N', 'Roasted Pepper', '#9B4338'),
        ],
    },
    {
        'base_pk': 13,
        'prefijo': 'ESA',
        'precio': 32490,
        'colores': [
            ('7002W', 'Lavender Bubble', '#E6DDEB'),
            ('7050W', 'Blue Chill', '#D7E2E8'),
            ('0720', 'Silky Mint', '#C9DED2'),
            ('CW026W', 'Lemon Chiffon', '#F1E2A9'),
            ('CW032W', 'Orange Foam', '#EBC9A8'),
            ('CW058W', 'Dove Wing', '#D9D5CC'),
        ],
    },
    {
        'base_pk': 15,
        'prefijo': 'FEH',
        'precio': 42990,
        'colores': [
            ('AC102N', 'Raintree', '#596B50'),
            ('AC103Y', 'Sun Coast', '#D8A94A'),
            ('AC113N', 'Spiced Rum', '#8A5A45'),
            ('AC116N', 'Roasted Pepper', '#9B4338'),
            ('7055D', 'Pompeii', '#446C86'),
            ('0752', 'Cactus Valley', '#6F7750'),
        ],
    },
    {
        'base_pk': 14,
        'prefijo': 'EAS',
        'precio': 32990,
        'colores': [
            ('7045D', 'Blue Epic', '#315A78'),
            ('0726', 'Hidden Jade', '#527263'),
            ('0800', 'Yellow Umbrella', '#D9AE30'),
            ('CW070W', 'Plum Black Ashes', '#777277'),
            ('CW030W', 'Apple Peel', '#D5AA78'),
            ('AC110N', 'Fireking Red', '#9A3430'),
        ],
    },
]

STOCKS = [96, 112, 84, 135, 103, 89, 121, 98, 145, 82, 109, 130,
          88, 117, 101, 140, 93, 126, 80, 115, 137, 91, 124, 106]

CAMPOS_HEREDADOS = [
    'categoria', 'activo', 'marca', 'modelo', 'ambiente_uso',
    'superficies_compatibles', 'tipo_pintura', 'terminacion',
    'propiedades_pintura', 'preparaciones_recomendadas',
    'secado_tacto_horas', 'repintado_min_horas', 'repintado_max_horas',
    'proveedor_id', 'unidad_venta', 'contenido', 'unidad_contenido',
    'tipo_calculo', 'rendimiento', 'unidad_rendimiento',
    'capas_recomendadas', 'porcentaje_desperdicio', 'uso_recomendado',
    'informacion_tecnica_verificada', 'imagen',
]


def crear_variantes(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    indice_stock = 0
    for familia in FAMILIAS:
        base = Producto.objects.filter(pk=familia['base_pk']).first()
        if not base:
            continue
        for codigo_color, color, color_hex in familia['colores']:
            sku = f'SFI-SIP-{familia["prefijo"]}-{codigo_color}-1GL'
            existente = Producto.objects.filter(
                marca__iexact=base.marca,
                modelo__iexact=base.modelo,
                color__iexact=color,
                contenido=base.contenido,
                unidad_contenido=base.unidad_contenido,
            ).first()
            if existente:
                if not existente.sku:
                    existente.sku = sku
                    existente.save(update_fields=['sku'])
                indice_stock += 1
                continue

            especificaciones = dict(base.especificaciones or {})
            especificaciones.update({
                'Color': color,
                'Código de cartilla': codigo_color,
                'Referencia cromática': (
                    'Muestra digital aproximada; comprobar el tono físico antes de aplicar.'
                ),
            })
            datos = {campo: getattr(base, campo) for campo in CAMPOS_HEREDADOS}
            datos.update({
                'sku': sku,
                'nombre': f'Sipa {base.modelo} {color} 1 galón',
                'descripcion': (
                    f'{base.descripcion} Variante tintométrica {color} '
                    f'({codigo_color}) de la cartilla oficial Sipa.'
                ),
                'precio': familia['precio'],
                'stock': STOCKS[indice_stock],
                'stock_minimo': 20,
                'color': color,
                'color_hex': color_hex,
                'especificaciones': especificaciones,
            })
            Producto.objects.create(**datos)
            indice_stock += 1


def eliminar_variantes(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    skus = [
        f'SFI-SIP-{familia["prefijo"]}-{codigo}-1GL'
        for familia in FAMILIAS
        for codigo, _color, _hex in familia['colores']
    ]
    Producto.objects.filter(sku__in=skus).delete()


class Migration(migrations.Migration):
    dependencies = [('productos', '0015_producto_sku')]
    operations = [
        migrations.RunPython(crear_variantes, eliminar_variantes),
    ]
