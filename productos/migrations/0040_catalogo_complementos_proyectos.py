from django.db import migrations


PRODUCTOS_COMPLEMENTARIOS = [
    # Techumbre y aguas lluvia.
    ('SFI-TEC-TAP-1KG', 'Tapagoteras acrílico impermeabilizante 1 kg', 8990, 48, 'Sellar filtraciones menores y encuentros exteriores de cubiertas compatibles.', 'Impermeabilizante acrílico para reparaciones localizadas; revisar compatibilidad con la cubierta.'),
    ('SFI-TEC-BAJ-PVC-75', 'Bajada PVC aguas lluvia 75 mm x 3 m', 7990, 42, 'Conducir el agua desde una canaleta hacia la descarga definida.', 'Bajada PVC de 75 mm por 3 m para aguas lluvia.'),
    ('SFI-TEC-COD-BAJ-75', 'Codo PVC bajada aguas lluvia 75 mm 90 grados', 2490, 65, 'Cambiar la dirección de una bajada de aguas lluvia.', 'Codo de 90 grados para bajada PVC de 75 mm.'),
    ('SFI-TEC-SOP-CAN-125', 'Soporte para canaleta galvanizada 125 mm', 1590, 90, 'Sostener una canaleta galvanizada según la separación indicada por el fabricante.', 'Soporte individual para canaleta galvanizada de 125 mm.'),
    ('SFI-TEC-AIS-LVG-50', 'Aislante lana de vidrio 50 mm rollo 12 m2', 32990, 26, 'Mejorar la aislación térmica bajo cubiertas y entre elementos de techumbre.', 'Rollo de lana de vidrio de 50 mm con cobertura declarada de 12 m².'),
    # Portones y automatización.
    ('SFI-AUT-RIE-6M', 'Riel acero para portón corredera 6 m', 49990, 18, 'Guiar el desplazamiento de un portón corredero compatible.', 'Riel de acero de 6 m para portón corredera.'),
    ('SFI-AUT-RUE-80', 'Rueda portón corredera 80 mm con canal V', 12990, 32, 'Permitir el desplazamiento de una hoja de portón sobre riel compatible.', 'Rueda de 80 mm con canal V para portón corredera.'),
    ('SFI-AUT-GUI-SUP', 'Guía superior regulable para portón corredera', 10990, 28, 'Mantener alineada la parte superior de un portón corredera durante su recorrido.', 'Guía superior regulable para hoja de portón corredera.'),
    ('SFI-AUT-TOPE-GOM', 'Tope de goma para portón corredera', 4990, 40, 'Amortiguar y limitar el cierre o apertura de un portón corredera.', 'Tope de goma con base de fijación.'),
    ('SFI-AUT-BAL-LED', 'Baliza LED intermitente para portón automático', 15990, 22, 'Señalizar visualmente el movimiento de un portón automatizado.', 'Baliza LED compatible con sistemas de automatización de portón.'),
    # Baño y cocina.
    ('SFI-GAS-VAL-LAV-4', 'Válvula desagüe lavaplatos 4 pulgadas con canastillo', 8990, 55, 'Conectar y filtrar la descarga del lavaplatos antes del sifón.', 'Válvula de desagüe de 4 pulgadas con canastillo para lavaplatos.'),
    ('SFI-GAS-SIF-RIG-112', 'Sifón rígido lavaplatos 1 1/2 pulgada', 6490, 60, 'Conducir el desagüe del lavaplatos y formar un sello hidráulico.', 'Sifón rígido de 1 1/2 pulgada para lavaplatos.'),
    ('SFI-GAS-GRI-COC-MON', 'Monomando lavaplatos cuello alto cromado', 49990, 24, 'Controlar agua fría y caliente en un lavaplatos de cocina.', 'Grifería monomando de cocina con cuello alto.'),
    ('SFI-GAS-MAN-DES-40', 'Manguera desagüe corrugada 40 mm x 1,5 m', 3990, 65, 'Extender una descarga de desagüe en instalaciones compatibles.', 'Manguera corrugada de desagüe de 40 mm por 1,5 m.'),
    ('SFI-GAS-LLA-ING-10', 'Llave angular cromada 1/2 x 3/8 pulgada', 4990, 75, 'Cortar el suministro de agua hacia artefactos de lavamanos o cocina.', 'Llave angular con entrada de 1/2 y salida de 3/8 pulgada.'),
    # Riego y agua exterior.
    ('SFI-JAR-PRO-MAN-12', 'Programador riego digital 1 salida', 24990, 34, 'Automatizar horarios de riego en una salida de manguera compatible.', 'Programador digital para una salida de riego.'),
    ('SFI-JAR-PIST-8F', 'Pistola riego 8 funciones con conector', 8990, 58, 'Regular el chorro de agua para riego y limpieza exterior.', 'Pistola de riego con ocho patrones de salida.'),
    ('SFI-JAR-TEE-GOT-16', 'Tee para riego por goteo 16 mm pack 10', 3490, 90, 'Derivar líneas de riego por goteo de 16 mm.', 'Pack de 10 conexiones tipo tee para manguera de goteo de 16 mm.'),
    ('SFI-JAR-VAL-GOT-16', 'Válvula riego por goteo 16 mm', 1490, 100, 'Abrir o cerrar un sector de riego por goteo.', 'Válvula manual para manguera de riego de 16 mm.'),
    ('SFI-JAR-TIE-VEG-40', 'Tierra vegetal preparada saco 40 L', 4990, 110, 'Mejorar la base de plantación en maceteros y áreas de jardín.', 'Saco de tierra vegetal preparada de 40 litros.'),
    ('SFI-JAR-COM-25', 'Compost orgánico para jardín saco 25 L', 5990, 85, 'Aportar materia orgánica a la preparación de suelo y maceteros.', 'Saco de compost orgánico de 25 litros.'),
    # Pisos y revestimientos.
    ('SFI-PIS-COR-POR-60', 'Cortadora manual porcelanato 600 mm', 69990, 16, 'Realizar cortes rectos en porcelanato dentro de la capacidad de la herramienta.', 'Cortadora manual para porcelanato de hasta 600 mm.'),
    ('SFI-PIS-DIS-DIA-115', 'Disco diamantado continuo porcelanato 115 mm', 11990, 44, 'Cortar porcelanato con esmeril angular compatible.', 'Disco diamantado continuo de 115 mm para porcelanato.'),
    ('SFI-PIS-SEP-NIV-100', 'Sistema nivelador cerámica clip 2 mm pack 100', 8990, 70, 'Ayudar a mantener niveladas las piezas durante la instalación de revestimientos.', 'Pack de 100 clips niveladores de 2 mm para cerámica o porcelanato.'),
    ('SFI-PIS-CUN-NIV-100', 'Cuñas reutilizables nivelador cerámica pack 100', 7990, 66, 'Aplicar presión en clips niveladores durante la instalación de revestimientos.', 'Pack de 100 cuñas reutilizables para nivelador de cerámica.'),
    ('SFI-PIS-LLA-DEN-10', 'Llana dentada acero 10 mm', 8990, 45, 'Distribuir adhesivo de forma uniforme al instalar cerámica o porcelanato.', 'Llana dentada de acero con diente de 10 mm.'),
    # Carpintería y muebles.
    ('SFI-CAR-COL-MAD-500', 'Cola fría para madera 500 g', 4990, 72, 'Adherir piezas de madera en uniones limpias y bien ajustadas.', 'Adhesivo cola fría para madera de 500 g.'),
    ('SFI-CAR-TAP-ENC-22', 'Tapacanto melamina blanco 22 mm x 5 m', 3490, 60, 'Dar terminación a los cantos expuestos de tableros de melamina.', 'Rollo de tapacanto blanco de 22 mm por 5 m.'),
    ('SFI-CAR-TIR-MUE-128', 'Tirador mueble acero inoxidable 128 mm', 3490, 80, 'Permitir abrir puertas o cajones de muebles.', 'Tirador de acero inoxidable con distancia de 128 mm entre perforaciones.'),
    ('SFI-CAR-ESC-LIJ-120', 'Lija para madera grano 120 pack 5', 2990, 95, 'Preparar madera antes de aplicar barniz, pintura o protección.', 'Pack de cinco lijas para madera grano 120.'),
    # Soldadura y metal.
    ('SFI-SOL-ESM-850', 'Esmeril angular 4 1/2 pulgadas 850 W', 39990, 24, 'Cortar, desbastar o limpiar metal con el disco adecuado.', 'Esmeril angular de 4 1/2 pulgadas y 850 W.'),
    ('SFI-SOL-DIS-COR-115', 'Disco corte metal 115 mm x 1 mm pack 10', 8990, 62, 'Cortar perfiles y piezas metálicas con esmeril compatible.', 'Pack de 10 discos de corte para metal de 115 mm.'),
    ('SFI-SOL-DIS-DES-115', 'Disco desbaste metal 115 mm x 6 mm', 2490, 75, 'Desbastar cordones de soldadura y bordes metálicos.', 'Disco de desbaste para metal de 115 mm.'),
    ('SFI-SOL-PER-CUA-30', 'Perfil cuadrado acero 30 x 30 x 2 mm x 6 m', 24990, 30, 'Fabricar bastidores y estructuras metálicas livianas.', 'Perfil cuadrado de acero de 30 x 30 x 2 mm por 6 m.'),
    ('SFI-SOL-ANT-400', 'Primer anticorrosivo metal gris 400 ml', 6990, 50, 'Proteger metal preparado antes de aplicar una terminación exterior compatible.', 'Primer anticorrosivo en aerosol de 400 ml para metal.'),
]


def cargar_catalogo_complementario(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Proveedor = apps.get_model('productos', 'Proveedor')
    proveedor = Proveedor.objects.filter(nombre='Proveedor General SFI', activo=True).first()
    for sku, nombre, precio, stock, uso, ficha in PRODUCTOS_COMPLEMENTARIOS:
        if sku.startswith('SFI-TEC-'):
            categoria = 'Construcción'
        elif sku.startswith('SFI-AUT-') or sku.startswith('SFI-ELE-'):
            categoria = 'Electricidad'
        elif sku.startswith('SFI-GAS-'):
            categoria = 'Gasfitería'
        elif sku.startswith('SFI-JAR-'):
            categoria = 'Jardinería'
        elif sku in {'SFI-PIS-COR-POR-60', 'SFI-PIS-LLA-DEN-10'}:
            categoria = 'Herramientas'
        elif sku.startswith('SFI-PIS-'):
            categoria = 'Construcción'
        elif sku.startswith('SFI-CAR-'):
            categoria = 'Carpintería'
        else:
            categoria = 'Herramientas' if sku.startswith('SFI-SOL-ESM') else 'Ferretería'
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
                'especificaciones': {'Ficha declarada': ficha},
                'informacion_tecnica_verificada': False,
            },
        )


def retirar_catalogo_complementario(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.filter(sku__in=[item[0] for item in PRODUCTOS_COMPLEMENTARIOS]).delete()


class Migration(migrations.Migration):
    dependencies = [('productos', '0039_componentes_electricos_instalacion')]
    operations = [migrations.RunPython(cargar_catalogo_complementario, retirar_catalogo_complementario)]
