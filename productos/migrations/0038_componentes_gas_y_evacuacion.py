from django.db import migrations


COMPONENTES_GAS = [
    ('SFI-GAS-DUC-RIG-100', 'Ducto rígido para evacuación de gases 100 mm x 1 m', 15990, 30, 'Conducir gases de combustión hacia el exterior en equipos compatibles.', 'Ducto rígido de 100 mm; confirmar compatibilidad con manual del artefacto.'),
    ('SFI-GAS-COD-RIG-100', 'Codo rígido para ducto de evacuación 100 mm 90 grados', 8990, 24, 'Permitir cambios de dirección en un sistema de evacuación compatible.', 'Codo rígido de 100 mm para evacuación; validar recorrido y fabricante.'),
    ('SFI-GAS-TER-100', 'Terminal exterior para ducto de evacuación 100 mm', 12990, 20, 'Rematar el ducto de evacuación hacia el exterior en instalaciones compatibles.', 'Terminal exterior de 100 mm; requiere definición profesional del sistema.'),
    ('SFI-GAS-COL-100', 'Collarín metálico para ducto de calefont 100 mm', 5990, 28, 'Unir el artefacto con el conducto de evacuación compatible.', 'Collarín metálico de 100 mm; validar diámetro del calefont.'),
    ('SFI-GAS-ABR-100', 'Abrazadera metálica para ducto 100 mm', 2490, 60, 'Afirmar tramos de ducto rígido a muro o soporte compatible.', 'Abrazadera para ducto de 100 mm.'),
    ('SFI-GAS-REJ-150', 'Rejilla de ventilación permanente 150 mm', 4990, 40, 'Permitir ventilación permanente en recintos donde el diseño autorizado la requiera.', 'Rejilla de 150 mm; ubicación y cantidad deben ser definidas por instalador autorizado.'),
    ('SFI-GAS-VAL-COR-12', 'Válvula de corte para gas 1/2 pulgada', 7990, 55, 'Interrumpir el suministro de gas para operación y mantención autorizada.', 'Válvula de corte 1/2 pulgada para gas; validar certificación y compatibilidad.'),
    ('SFI-GAS-FLE-CER-12', 'Flexible para gas 1/2 pulgada x 1 m', 11990, 35, 'Conectar artefactos de gas solo cuando el modelo, la normativa y la certificación aplicable lo permitan.', 'Flexible de gas 1/2 pulgada; verificar sello y uso autorizado antes de compra.'),
    ('SFI-GAS-TUB-COB-12-3', 'Tubo cobre rígido para gas 1/2 pulgada x 3 m', 28990, 30, 'Conducir gas en tramos definidos por un proyecto autorizado.', 'Tubo de cobre rígido de 1/2 pulgada; requiere diseño e instalación profesional.'),
    ('SFI-GAS-COD-COB-12', 'Codo cobre para gas 1/2 pulgada', 3490, 70, 'Realizar cambios de dirección en tubería de cobre para gas definida por un instalador.', 'Codo de cobre 1/2 pulgada para gas.'),
    ('SFI-GAS-UNI-COB-12', 'Unión cobre para gas 1/2 pulgada', 2990, 70, 'Unir tramos de tubería de cobre según el sistema definido por el instalador.', 'Unión de cobre 1/2 pulgada para gas.'),
    ('SFI-GAS-SEL-ROS-50', 'Sellador de roscas para gas 50 ml', 8990, 38, 'Sellar uniones roscadas compatibles en instalaciones de gas autorizadas.', 'Sellador para roscas de gas; confirmar aplicación y compatibilidad del fabricante.'),
    ('SFI-GAS-DET-FUG-250', 'Detector de fugas para gas spray 250 ml', 6990, 45, 'Ayudar a identificar fugas en uniones durante una revisión profesional.', 'Spray detector de fugas para gas de 250 ml.'),
    ('SFI-SEG-DET-CO', 'Detector de monóxido de carbono con alarma', 24990, 22, 'Alertar sobre presencia de monóxido de carbono como medida complementaria de seguridad.', 'Detector de CO con alarma; no reemplaza ventilación ni instalación autorizada.'),
    ('SFI-HER-MAN-GAS', 'Manómetro para prueba de presión de gas', 34990, 12, 'Apoyar pruebas de presión realizadas por personal competente.', 'Manómetro para prueba de gas; uso técnico profesional.'),
    ('SFI-HER-LLA-TUB-14', 'Llave grifa para tubería 14 pulgadas', 19990, 20, 'Manipular tuberías y conexiones en trabajos de gasfitería realizados por personal competente.', 'Llave grifa de 14 pulgadas.'),
]


def cargar_componentes_gas(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Proveedor = apps.get_model('productos', 'Proveedor')
    proveedor = Proveedor.objects.filter(nombre='Proveedor General SFI', activo=True).first()
    for sku, nombre, precio, stock, uso, ficha in COMPONENTES_GAS:
        categoria = 'Herramientas' if sku.startswith('SFI-HER-') else (
            'Seguridad' if sku.startswith('SFI-SEG-') else 'Gasfitería'
        )
        Producto.objects.update_or_create(
            sku=sku,
            defaults={
                'nombre': nombre, 'descripcion': uso, 'precio': precio, 'stock': stock,
                'stock_minimo': max(2, stock // 6), 'categoria': categoria, 'modelo': sku,
                'imagen': '', 'activo': True, 'marca': 'Genérico SFI',
                'ambiente_uso': 'especial', 'unidad_venta': 'unidad',
                'contenido': '1.000', 'unidad_contenido': 'unidad',
                'tipo_calculo': 'unidad', 'rendimiento': None, 'unidad_rendimiento': '',
                'porcentaje_desperdicio': '0.00',
                'proveedor_id': proveedor.pk if proveedor else None,
                'uso_recomendado': uso,
                'especificaciones': {
                    'Ficha declarada': ficha,
                    'Seguridad': 'Validar sello, compatibilidad y normativa vigente con instalador de gas autorizado SEC.',
                },
                'informacion_tecnica_verificada': False,
            },
        )


def retirar_componentes_gas(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.filter(sku__in=[item[0] for item in COMPONENTES_GAS]).delete()


class Migration(migrations.Migration):
    dependencies = [('productos', '0037_componentes_bomba_presurizadora')]
    operations = [migrations.RunPython(cargar_componentes_gas, retirar_componentes_gas)]
