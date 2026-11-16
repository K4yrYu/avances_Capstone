from django.db import migrations


COMPONENTES_BOMBA = [
    ('SFI-GAS-RET-034', 'Válvula de retención bronce 3/4 pulgada', 8990, 45, 'Evita el retorno de agua hacia el estanque cuando la bomba se detiene.', 'Válvula check 3/4 pulgadas para redes de agua a presión.'),
    ('SFI-GAS-UNI-PPR25', 'Unión americana PPR 25 mm', 4990, 60, 'Permite desmontar la bomba o un tramo de tubería para mantención.', 'Unión desmontable PPR de 25 mm.'),
    ('SFI-GAS-ADA-PPR25-34', 'Adaptador PPR 25 mm x rosca bronce 3/4 pulgada', 3590, 80, 'Conecta la tubería PPR con las roscas de la bomba, válvulas o accesorios.', 'Transición PPR 25 mm a rosca de bronce 3/4 pulgadas.'),
    ('SFI-GAS-FIL-SED-34', 'Filtro de sedimentos lavable 3/4 pulgada', 22990, 20, 'Retiene partículas antes de que lleguen a la bomba y ayuda a protegerla.', 'Filtro lavable para línea de agua de 3/4 pulgadas.'),
    ('SFI-GAS-FLE-ANT-34', 'Flexible antivibración para bomba 3/4 pulgada x 50 cm', 10990, 28, 'Reduce la transmisión de vibraciones entre la bomba y la red hidráulica.', 'Flexible de conexión para bomba de 3/4 pulgadas y 50 cm.'),
    ('SFI-GAS-CON-PRE-34', 'Controlador automático de presión para bomba 3/4 pulgada', 44990, 16, 'Enciende y detiene la bomba según la demanda de agua y protege ante falta de caudal.', 'Controlador de presión para conexión de 3/4 pulgadas.'),
    ('SFI-GAS-MAN-100-34', 'Manómetro para agua 0 a 100 psi rosca 1/4 pulgada', 7990, 35, 'Permite revisar la presión de trabajo del sistema hidráulico.', 'Manómetro para agua, rango 0 a 100 psi.'),
    ('SFI-GAS-TEF-12-12', 'Cinta PTFE teflón 12 mm x 12 m', 990, 180, 'Sella conexiones roscadas de agua para ayudar a prevenir filtraciones.', 'Cinta PTFE de 12 mm por 12 m.'),
    ('SFI-ELE-CON-PVC20-3', 'Conduit PVC eléctrico 20 mm x 3 m', 2490, 95, 'Canaliza y protege el cable de alimentación de la bomba.', 'Tubo conduit PVC de 20 mm y 3 m.'),
    ('SFI-ELE-CAJ-EST-100', 'Caja estanca eléctrica 100 x 100 mm', 4990, 48, 'Protege empalmes eléctricos en sectores expuestos a humedad o polvo.', 'Caja eléctrica estanca de 100 x 100 mm.'),
    ('SFI-ELE-DIF-25-30', 'Interruptor diferencial 25 A 30 mA', 29990, 24, 'Aporta protección ante fugas de corriente en el circuito que alimenta la bomba.', 'Diferencial de 25 A y sensibilidad de 30 mA.'),
    ('SFI-HER-TER-PPR20-25', 'Termofusora PPR 20 a 25 mm 800 W', 39990, 12, 'Une tuberías y fittings PPR mediante termofusión.', 'Termofusora de 800 W para PPR de 20 y 25 mm.'),
    ('SFI-HER-COR-PPR-42', 'Cortatubo plástico PPR hasta 42 mm', 10990, 30, 'Realiza cortes rectos en tuberías PPR antes de termofusionar.', 'Cortatubo para plástico hasta 42 mm.'),
    ('SFI-HER-LLA-CAÑ-12', 'Llave de cañería ajustable 12 pulgadas', 16990, 25, 'Aprieta o afloja conexiones roscadas de la instalación hidráulica.', 'Llave de cañería ajustable de 12 pulgadas.'),
    ('SFI-HER-MUL-DIG', 'Multímetro digital básico', 14990, 30, 'Permite comprobar tensión y continuidad antes de intervenir conexiones eléctricas.', 'Multímetro digital para mediciones eléctricas básicas.'),
]


def cargar_componentes_bomba(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Proveedor = apps.get_model('productos', 'Proveedor')
    proveedor = Proveedor.objects.filter(nombre='Proveedor General SFI', activo=True).first()
    for sku, nombre, precio, stock, uso, ficha in COMPONENTES_BOMBA:
        categoria = 'Herramientas' if sku.startswith('SFI-HER-') else (
            'Electricidad' if sku.startswith('SFI-ELE-') else 'Gasfitería'
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
                    'Estado de ficha': 'Datos de catálogo interno; validar compatibilidad y montaje antes de compra.',
                },
                'informacion_tecnica_verificada': False,
            },
        )


def retirar_componentes_bomba(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.filter(sku__in=[item[0] for item in COMPONENTES_BOMBA]).delete()


class Migration(migrations.Migration):
    dependencies = [('productos', '0036_materiales_quincho_moldaje_y_extraccion')]
    operations = [migrations.RunPython(cargar_componentes_bomba, retirar_componentes_bomba)]
