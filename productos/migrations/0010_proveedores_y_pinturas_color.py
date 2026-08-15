from decimal import Decimal

from django.db import migrations


SIPA_LATEX_URL = 'https://www.sipa.cl/productos/latex/latex-extracubriente'


def cargar_proveedores_y_colores(apps, schema_editor):
    Proveedor = apps.get_model('productos', 'Proveedor')
    Producto = apps.get_model('productos', 'Producto')

    proveedor_pinturas, _ = Proveedor.objects.update_or_create(
        nombre='Distribuidora SFI Pinturas',
        defaults={
            'nombre_contacto': 'Área de ventas',
            'email': 'ferremas.proyecto2026@gmail.com',
            'telefono': '',
            'activo': True,
        },
    )
    proveedor_general, _ = Proveedor.objects.update_or_create(
        nombre='Proveedor General SFI',
        defaults={
            'nombre_contacto': 'Área comercial',
            'email': 'ferremas.proyecto2026@gmail.com',
            'telefono': '',
            'activo': True,
        },
    )

    Producto.objects.exclude(categoria='Pinturas').update(
        proveedor=proveedor_general,
        stock_minimo=10,
    )
    Producto.objects.filter(categoria='Pinturas').update(
        proveedor=proveedor_pinturas,
        stock_minimo=20,
    )

    colores_existentes = {
        5: ('Blanco', '#FFFFFF'),
        11: ('Blanco mate', '#F8F7F2'),
        13: ('Blanco satinado', '#FAFAF6'),
        14: ('Blanco semibrillo', '#FFFFFF'),
        15: ('Blanco', '#F5F3EA'),
        16: ('Azul piscina', '#42A5CF'),
    }
    for producto_id, (color, color_hex) in colores_existentes.items():
        Producto.objects.filter(pk=producto_id).update(color=color, color_hex=color_hex)

    base = {
        'descripcion': 'Pintura látex base agua de terminación mate, bajo olor y alto poder cubridor para muros interiores y exteriores.',
        'precio': 22990,
        'imagen': 'productos/producto-5-pintura-latex-extracubriente.jpg',
        'categoria': 'Pinturas',
        'activo': True,
        'marca': 'Sipa',
        'modelo': 'Látex Extracubriente',
        'proveedor': proveedor_pinturas,
        'stock_minimo': 20,
        'unidad_venta': 'envase',
        'contenido': Decimal('3.785'),
        'unidad_contenido': 'l',
        'tipo_calculo': 'pintura',
        'rendimiento': Decimal('7.926'),
        'unidad_rendimiento': 'm2_l',
        'capas_recomendadas': 3,
        'porcentaje_desperdicio': Decimal('10.00'),
        'uso_recomendado': 'Muros de estuco, hormigón, ladrillo, fibrocemento, pasta muro, yeso y yeso-cartón, en interior o exterior.',
        'informacion_tecnica_verificada': True,
    }
    variantes = {
        17: ('Blanco Invierno', '#F2F0E7', 26),
        18: ('Hueso', '#E6DDC7', 19),
        19: ('Marfil', '#E9D6AE', 14),
        20: ('Rojo Colonial', '#8F3731', 8),
    }
    for producto_id, (color, color_hex, stock) in variantes.items():
        datos = {
            **base,
            'nombre': f'Sipa Látex Extracubriente {color} 1 galón',
            'color': color,
            'color_hex': color_hex,
            'stock': stock,
            'especificaciones': {
                'Color': color,
                'Base': 'Agua',
                'Terminación': 'Mate',
                'Rendimiento fabricante': '30 a 40 m²/galón/mano',
                'Criterio de cálculo': 'Mínimo declarado: 30 m² por galón y mano',
                'Capas': '2 a 3 según color y superficie',
                'Aplicación': 'Brocha, rodillo o pistola',
                'Repintado': '3 a 6 horas',
                'Fuente técnica': SIPA_LATEX_URL,
            },
        }
        Producto.objects.update_or_create(pk=producto_id, defaults=datos)


class Migration(migrations.Migration):
    dependencies = [('productos', '0009_reposicion_inventario')]

    operations = [
        migrations.RunPython(cargar_proveedores_y_colores, migrations.RunPython.noop),
    ]
