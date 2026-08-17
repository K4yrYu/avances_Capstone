from decimal import Decimal

from django.db import migrations


REFERENCIA_SODIMAC = 'Catálogo Sodimac Chile consultado el 17-08-2026'

PRODUCTOS = [
    # Tornillos para madera, metal y techumbre.
    ('SFI-QUI-TOR-001', 'Tornillo Turbo Screw madera 5-1/2 x 14 mm, 4 unidades', 'Fixser', 2990, 4, 'Madera', '5-1/2 pulgadas x 14 mm', 'Cabeza avellanada', 'productos/quincalleria-tornillos.png'),
    ('SFI-QUI-TOR-002', 'Tornillo Turbo Screw tirafondo madera 4 x 14 mm, 4 unidades', 'Fixser', 1990, 4, 'Madera', '4 pulgadas x 14 mm', 'Tirafondo', 'productos/quincalleria-tornillos.png'),
    ('SFI-QUI-TOR-003', 'Tornillo para madera 1-1/2 x 8 mm, 12 unidades', 'Fixser', 1090, 12, 'Madera', '1-1/2 pulgadas x 8 mm', 'Rosca para madera', 'productos/quincalleria-tornillos.png'),
    ('SFI-QUI-TOR-004', 'Tornillo para techo de madera 2-1/2 x 12 mm, 100 unidades', 'Fixser', 12990, 100, 'Madera y techumbre', '2-1/2 pulgadas x 12 mm', 'Fijación de techumbre', 'productos/quincalleria-tornillos.png'),
    ('SFI-QUI-TOR-005', 'Tornillo autoperforante metal 1-1/2 x 12 mm, 100 unidades', 'Fixser', 9700, 100, 'Metal', '1-1/2 pulgadas x 12 mm', 'Punta broca', 'productos/quincalleria-tornillos.png'),
    ('SFI-QUI-TOR-006', 'Tornillo autoperforante metal 2 x 25 mm, 50 unidades', 'Fixser', 19990, 50, 'Metal', '2 pulgadas x 25 mm', 'Punta broca', 'productos/quincalleria-tornillos.png'),

    # Tarugos y anclajes.
    ('SFI-QUI-ANC-001', 'Tarugo para concreto 6 mm, 200 unidades', 'Fixser', 3990, 200, 'Hormigón y albañilería', '6 mm', 'Nylon', 'productos/quincalleria-anclajes.png'),
    ('SFI-QUI-ANC-002', 'Tarugo para concreto 8 mm, 100 unidades', 'Fixser', 3490, 100, 'Hormigón y albañilería', '8 mm', 'Nylon', 'productos/quincalleria-anclajes.png'),
    ('SFI-QUI-ANC-003', 'Tarugo con tornillo 8 mm, 10 unidades', 'Fixser', 2590, 10, 'Hormigón y albañilería', '8 mm', 'Nylon con tornillo', 'productos/quincalleria-anclajes.png'),
    ('SFI-QUI-ANC-004', 'Tarugo DuoPower 8 mm con tornillo 5x45 mm, 25 unidades', 'Fischer', 8390, 25, 'Material macizo o hueco compatible', 'Tarugo 8 mm; tornillo 5x45 mm', 'Nylon con tornillo', 'productos/quincalleria-anclajes.png'),
    ('SFI-QUI-ANC-005', 'Tarugo clavo M6 x 35 mm, 50 unidades', 'Mamut', 3990, 50, 'Hormigón y albañilería', 'M6 x 35 mm', 'Tarugo clavo', 'productos/quincalleria-anclajes.png'),
    ('SFI-QUI-ANC-006', 'Perno de anclaje 3/8 x 3 pulgadas, 6 unidades', 'Dimafi', 6990, 6, 'Hormigón', '3/8 x 3 pulgadas', 'Acero zincado', 'productos/quincalleria-anclajes.png'),

    # Candados y cilindros de seguridad.
    ('SFI-QUI-SEG-001', 'Candado de bronce 40 mm con llaves', 'Odis', 7790, 1, 'Casilleros, portones y bodegas', '40 mm', 'Cuerpo de bronce', 'productos/quincalleria-seguridad.png'),
    ('SFI-QUI-SEG-002', 'Candado de bronce 50 mm con llaves', 'Odis', 17590, 1, 'Portones y bodegas', '50 mm', 'Cuerpo de bronce', 'productos/quincalleria-seguridad.png'),
    ('SFI-QUI-SEG-003', 'Set de candados B30, 3 unidades', 'Odis', 13990, 3, 'Casilleros y cierres livianos', '30 mm', 'Set de tres candados', 'productos/quincalleria-seguridad.png'),
    ('SFI-QUI-SEG-004', 'Candado Off Road 60 mm con llaves', 'Odis', 24990, 1, 'Uso exterior y portones', '60 mm', 'Protección exterior', 'productos/quincalleria-seguridad.png'),
    ('SFI-QUI-SEG-005', 'Candado Citylock 652C', 'Odis', 24990, 1, 'Bicicletas y seguridad móvil', 'Modelo 652C', 'Sistema Citylock', 'productos/quincalleria-seguridad.png'),
    ('SFI-QUI-SEG-006', 'Cilindro llave-llave 70 mm', 'Odis', 13990, 1, 'Puertas con cerradura compatible', '70 mm', 'Cilindro doble llave', 'productos/quincalleria-seguridad.png'),

    # Herrajes para muebles y puertas.
    ('SFI-QUI-HER-001', 'Clavo escuadra zincado 4.0 x 3 pulgadas, 4 unidades', 'Mamut', 1090, 4, 'Madera', '4.0 x 3 pulgadas', 'Acero zincado', 'productos/quincalleria-muebles.png'),
    ('SFI-QUI-HER-002', 'Clavo escuadra zincado 3.0 x 1 pulgada, 5 unidades', 'Mamut', 390, 5, 'Madera', '3.0 x 1 pulgada', 'Acero zincado', 'productos/quincalleria-muebles.png'),
    ('SFI-QUI-HER-003', 'Set de escuadras para silla 2 pulgadas, 4 unidades', 'Fixser', 3990, 4, 'Madera y muebles', '2 pulgadas', 'Acero', 'productos/quincalleria-muebles.png'),
    ('SFI-QUI-HER-004', 'Bisagra recta cierre suave 35 mm 110°, 2 unidades', 'Fixser', 990, 2, 'Puertas de muebles', 'Cazoleta 35 mm; apertura 110°', 'Acero niquelado', 'productos/quincalleria-muebles.png'),
    ('SFI-QUI-HER-005', 'Corredera extensión total cierre suave 45 x 450 mm', 'Fixser', 6190, 1, 'Cajones de muebles', '45 x 450 mm', 'Acero zincado', 'productos/quincalleria-muebles.png'),
    ('SFI-QUI-HER-006', 'Tope de puerta recto a muro color plata', 'Odis', 4990, 1, 'Puertas y muros interiores', 'Formato recto a muro', 'Metal acabado plata', 'productos/quincalleria-muebles.png'),
]

STOCKS = [96, 112, 84, 135, 103, 89, 121, 98, 145, 82, 109, 130,
          88, 117, 101, 140, 93, 126, 80, 115, 137, 91, 124, 106]


def cargar_quincalleria(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Proveedor = apps.get_model('productos', 'Proveedor')
    proveedor, _ = Proveedor.objects.get_or_create(
        nombre='Proveedor General SFI',
        defaults={
            'nombre_contacto': 'Área comercial',
            'email': 'compras@sfi.local',
            'telefono': '',
            'activo': True,
        },
    )
    for indice, producto in enumerate(PRODUCTOS):
        sku, nombre, marca, precio, contenido, aplicacion, medida, material, imagen = producto
        Producto.objects.update_or_create(
            sku=sku,
            defaults={
                'nombre': nombre,
                'descripcion': (
                    f'{nombre}. Producto de quincallería para {aplicacion.lower()}; '
                    'seleccionar la medida y fijación según la carga y el soporte real.'
                ),
                'precio': precio,
                'imagen': imagen,
                'stock': STOCKS[indice],
                'stock_minimo': 20,
                'categoria': 'Ferretería',
                'activo': True,
                'marca': marca,
                'modelo': medida,
                'proveedor': proveedor,
                'unidad_venta': 'paquete' if contenido > 1 else 'unidad',
                'contenido': Decimal(str(contenido)),
                'unidad_contenido': 'unidad',
                'tipo_calculo': 'unidad',
                'porcentaje_desperdicio': Decimal('0.00'),
                'uso_recomendado': aplicacion,
                'especificaciones': {
                    'Familia': sku.split('-')[2],
                    'Aplicación': aplicacion,
                    'Medida': medida,
                    'Material o característica': material,
                    'Contenido': f'{contenido} unidad(es)',
                    'Referencia comercial': REFERENCIA_SODIMAC,
                    'Imagen': 'Representativa de la familia del producto',
                    'Advertencia': (
                        'Confirmar carga, material base, diámetro y largo antes de instalar.'
                    ),
                },
                'informacion_tecnica_verificada': True,
            },
        )


def eliminar_quincalleria(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.filter(sku__in=[producto[0] for producto in PRODUCTOS]).delete()


class Migration(migrations.Migration):
    dependencies = [('productos', '0017_familia_cromatica_variantes')]
    operations = [
        migrations.RunPython(cargar_quincalleria, eliminar_quincalleria),
    ]
