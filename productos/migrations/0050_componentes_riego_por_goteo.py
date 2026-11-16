from django.db import migrations


# Componentes de riego localizado solicitados por el asistente. Se registra
# una ficha técnica concreta para que las recomendaciones no queden como
# elementos ausentes del catálogo.
PRODUCTOS_RIEGO = [
    {
        'sku': 'SFI-RIE-TUB-PE-16-50',
        'nombre': 'Tubo polietileno para riego 16 mm x 50 m',
        'categoria': 'Jardinería',
        'precio': 24990,
        'stock': 35,
        'contenido': '50.000',
        'unidad': 'm',
        'tipo_calculo': 'longitud',
        'rendimiento': '50.000',
        'unidad_rendimiento': 'm_unidad',
        'uso': 'Conducir agua en líneas principales o secundarias de riego por goteo de 16 mm compatibles.',
        'ficha': {
            'Material': 'Polietileno',
            'Diámetro exterior': '16 mm',
            'Largo del rollo': '50 m',
            'Compatibilidad': 'Fittings y goteros para riego de 16 mm',
            'Uso recomendado': 'Huertos, jardines y maceteros con riego localizado',
            'Instalación': 'Cortar recto y usar conectores compatibles; purgar la línea antes de instalar goteros.',
        },
    },
    {
        'sku': 'SFI-RIE-GOT-REG-10',
        'nombre': 'Gotero regulable para riego por goteo pack 10',
        'categoria': 'Jardinería',
        'precio': 3990,
        'stock': 80,
        'contenido': '10.000',
        'unidad': 'unidad',
        'tipo_calculo': 'unidad',
        'rendimiento': None,
        'unidad_rendimiento': '',
        'uso': 'Entregar agua de forma localizada en la base de cada planta desde una línea de riego compatible.',
        'ficha': {
            'Tipo': 'Gotero regulable',
            'Contenido': '10 unidades',
            'Compatibilidad': 'Tubo de polietileno para riego de 16 mm',
            'Uso recomendado': 'Maceteros, huertos y plantas con necesidades de riego diferenciadas',
            'Instalación': 'Instalar después de limpiar la línea; ajustar el caudal según la necesidad de cada planta.',
        },
    },
    {
        'sku': 'SFI-HER-TIJ-PE-16-32',
        'nombre': 'Tijera cortatubo para polietileno 16 a 32 mm',
        'categoria': 'Herramientas',
        'precio': 8990,
        'stock': 30,
        'contenido': '1.000',
        'unidad': 'unidad',
        'tipo_calculo': 'ninguno',
        'rendimiento': None,
        'unidad_rendimiento': '',
        'uso': 'Cortar tubos de polietileno de riego de forma recta antes de instalar fittings o goteros.',
        'ficha': {
            'Tipo': 'Tijera manual para tubería plástica',
            'Rango de corte': '16 a 32 mm',
            'Material compatible': 'Polietileno y tubería plástica dentro del rango indicado',
            'Uso recomendado': 'Riego por goteo, mangueras y montaje de fittings compatibles',
            'Seguridad': 'Mantener la hoja cerrada cuando no se utilice y cortar lejos del cuerpo.',
        },
    },
]


def cargar_componentes_riego(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Proveedor = apps.get_model('productos', 'Proveedor')
    proveedor = Proveedor.objects.filter(
        nombre='Proveedor General SFI', activo=True
    ).first()

    for producto in PRODUCTOS_RIEGO:
        Producto.objects.update_or_create(
            sku=producto['sku'],
            defaults={
                'nombre': producto['nombre'],
                'descripcion': producto['uso'],
                'precio': producto['precio'],
                'stock': producto['stock'],
                'stock_minimo': max(3, producto['stock'] // 6),
                'categoria': producto['categoria'],
                'marca': 'Genérico SFI',
                'modelo': producto['sku'],
                'imagen': '',
                'activo': True,
                'ambiente_uso': 'exterior',
                'superficies_compatibles': [],
                'tipo_pintura': 'no_aplica',
                'terminacion': 'no_aplica',
                'propiedades_pintura': [],
                'preparaciones_recomendadas': [],
                'unidad_venta': 'rollo' if producto['unidad'] == 'm' else 'paquete' if producto['contenido'] == '10.000' else 'unidad',
                'contenido': producto['contenido'],
                'unidad_contenido': producto['unidad'],
                'tipo_calculo': producto['tipo_calculo'],
                'rendimiento': producto['rendimiento'],
                'unidad_rendimiento': producto['unidad_rendimiento'],
                'porcentaje_desperdicio': '0.00',
                'proveedor_id': proveedor.pk if proveedor else None,
                'uso_recomendado': producto['uso'],
                'especificaciones': producto['ficha'],
                'informacion_tecnica_verificada': True,
            },
        )


def retirar_componentes_riego(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.filter(
        sku__in=[producto['sku'] for producto in PRODUCTOS_RIEGO]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [('productos', '0049_imagenes_catalogo_guia')]

    operations = [
        migrations.RunPython(cargar_componentes_riego, retirar_componentes_riego),
    ]
