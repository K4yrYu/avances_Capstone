from django.db import migrations


COMPONENTES_ELECTRICOS = [
    ('SFI-ELE-UNI-CON20', 'Unión conduit PVC 20 mm', 790, 180, 'Unir tramos rectos de conduit PVC de 20 mm en una canalización eléctrica.', 'Accesorio de unión para conduit PVC de 20 mm.'),
    ('SFI-ELE-COD-CON20', 'Codo conduit PVC 20 mm 90 grados', 990, 160, 'Cambiar la dirección de una canalización de conduit PVC sin forzar el cable.', 'Codo de 90 grados para conduit PVC de 20 mm.'),
    ('SFI-ELE-ABR-CON20', 'Abrazadera conduit PVC 20 mm pack 20', 2490, 110, 'Fijar conduit PVC de 20 mm a muro o cielo en una canalización.', 'Pack de 20 abrazaderas para conduit PVC de 20 mm.'),
    ('SFI-ELE-CAJ-EMB-10', 'Caja eléctrica embutida rectangular 10 unidades', 2990, 95, 'Alojar enchufes o interruptores embutidos de una instalación eléctrica.', 'Pack de 10 cajas rectangulares embutidas.'),
    ('SFI-ELE-PLA-ENCH-DOB', 'Placa para enchufe doble blanca', 1490, 120, 'Dar terminación y protección a un enchufe doble instalado en caja eléctrica.', 'Placa blanca para enchufe doble.'),
    ('SFI-ELE-CON-12P', 'Conector eléctrico regleta 12 polos', 1990, 100, 'Ordenar y conectar conductores dentro de una caja de derivación compatible.', 'Regleta de conexión de 12 polos.'),
    ('SFI-ELE-CIN-AIS-18', 'Cinta aisladora eléctrica PVC 18 mm x 20 m', 1490, 180, 'Aislar empalmes eléctricos realizados de forma adecuada dentro de cajas compatibles.', 'Cinta aisladora PVC de 18 mm por 20 m.'),
    ('SFI-ELE-TOM-EST-16', 'Enchufe exterior estanco 16 A con tapa', 8990, 45, 'Proteger un punto de conexión eléctrica en exterior o zonas expuestas.', 'Enchufe estanco de 16 A con tapa protectora.'),
    ('SFI-ELE-TIE-COB-58', 'Jabalina cobreada puesta a tierra 5/8 pulgada x 1,5 m', 19990, 30, 'Formar parte de un sistema de puesta a tierra definido por un electricista competente.', 'Jabalina cobreada de 5/8 pulgadas por 1,5 m.'),
    ('SFI-ELE-GRA-TIE-58', 'Abrazadera para puesta a tierra 5/8 pulgada', 2990, 55, 'Conectar el conductor de tierra a una jabalina compatible.', 'Abrazadera para jabalina de 5/8 pulgadas.'),
    ('SFI-ILU-AMP-LED-9W', 'Ampolleta LED E27 luz cálida 9 W', 2490, 120, 'Iluminar espacios interiores con bajo consumo eléctrico.', 'Ampolleta LED E27 de 9 W, luz cálida.'),
    ('SFI-ILU-AMP-LED-12W', 'Ampolleta LED E27 luz fría 12 W', 2990, 100, 'Iluminar áreas de trabajo o circulación con luz fría.', 'Ampolleta LED E27 de 12 W, luz fría.'),
    ('SFI-ILU-AMP-LED-15W', 'Ampolleta LED E27 luz neutra 15 W', 3490, 85, 'Iluminar espacios de uso general con una potencia mayor.', 'Ampolleta LED E27 de 15 W, luz neutra.'),
    ('SFI-HER-PEL-CAB', 'Pelacables manual para cable 0,8 a 2,6 mm', 8990, 35, 'Retirar aislación de conductores antes de realizar conexiones autorizadas.', 'Pelacables manual para conductores de 0,8 a 2,6 mm.'),
    ('SFI-HER-PAS-CAB-10', 'Pasacables de acero 10 m', 10990, 28, 'Guiar conductores por conduit o canalizaciones antes de la conexión final.', 'Pasacables de acero de 10 m.'),
    ('SFI-HER-PRO-TEN', 'Probador de tensión sin contacto', 12990, 32, 'Comprobar presencia aproximada de tensión antes de intervenir una instalación eléctrica.', 'Probador de tensión sin contacto; no reemplaza procedimientos de seguridad.'),
]


def cargar_componentes_electricos(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Proveedor = apps.get_model('productos', 'Proveedor')
    proveedor = Proveedor.objects.filter(nombre='Proveedor General SFI', activo=True).first()
    for sku, nombre, precio, stock, uso, ficha in COMPONENTES_ELECTRICOS:
        categoria = 'Herramientas' if sku.startswith('SFI-HER-') else (
            'Iluminación' if sku.startswith('SFI-ILU-') else 'Electricidad'
        )
        Producto.objects.update_or_create(
            sku=sku,
            defaults={
                'nombre': nombre,
                'descripcion': uso,
                'precio': precio,
                'stock': stock,
                'stock_minimo': max(3, stock // 6),
                'categoria': categoria,
                'modelo': sku,
                'imagen': '',
                'activo': True,
                'marca': 'Genérico SFI',
                'ambiente_uso': 'interior_exterior',
                'unidad_venta': 'unidad',
                'contenido': '1.000',
                'unidad_contenido': 'unidad',
                'tipo_calculo': 'unidad',
                'rendimiento': None,
                'unidad_rendimiento': '',
                'porcentaje_desperdicio': '0.00',
                'proveedor_id': proveedor.pk if proveedor else None,
                'uso_recomendado': uso,
                'especificaciones': {
                    'Ficha declarada': ficha,
                    'Seguridad': 'Validar sección de conductor, protecciones y normativa con instalador eléctrico competente.',
                },
                'informacion_tecnica_verificada': False,
            },
        )


def retirar_componentes_electricos(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.filter(sku__in=[item[0] for item in COMPONENTES_ELECTRICOS]).delete()


class Migration(migrations.Migration):
    dependencies = [('productos', '0038_componentes_gas_y_evacuacion')]
    operations = [migrations.RunPython(cargar_componentes_electricos, retirar_componentes_electricos)]
