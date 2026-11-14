from django.db import migrations


# Catálogo genérico de prueba para ampliar la cobertura del asistente. Los
# productos técnicos requieren confirmar ficha, compatibilidad y certificación.
PRODUCTOS = [
    # Puertas y ventanas
    ('PUE-ACE-8020', 'Puerta exterior de acero 80 x 200 cm', 129990, 12, 'Construcción', 'Cierre exterior en vano compatible; confirmar mano, marco y anclajes.'),
    ('PUE-MDF-7020', 'Puerta interior MDF 70 x 200 cm', 59990, 18, 'Construcción', 'Cierre interior en vano compatible con marco y quincallería.'),
    ('VEN-ALU-1010', 'Ventana aluminio corredera 100 x 100 cm', 109990, 10, 'Construcción', 'Ventana para vano preparado; confirmar sellado, vidrio y anclajes.'),
    ('MAR-PIN-7020', 'Marco pino para puerta 70 x 200 cm', 29990, 22, 'Construcción', 'Marco para puerta interior de formato compatible.'),
    ('CER-EMB-EXT', 'Cerradura embutida para puerta exterior', 24990, 30, 'Ferretería', 'Cierre de puerta exterior con espesores y perforaciones compatibles.'),

    # Cocina
    ('COC-LAV-8050', 'Lavaplatos acero inoxidable 80 x 50 cm', 69990, 14, 'Gasfitería', 'Lavado y preparación en cubierta compatible con desagüe y grifería.'),
    ('COC-MUE-BASE80', 'Mueble base cocina melamina 80 cm', 119990, 10, 'Construcción', 'Almacenamiento bajo cubierta de cocina en espacio seco y nivelado.'),
    ('COC-CUB-300', 'Cubierta postformada cocina 60 cm x 3 m', 89990, 16, 'Construcción', 'Superficie de trabajo para muebles base compatibles.'),
    ('COC-CAM-60', 'Campana cocina 60 cm acero inoxidable', 99990, 8, 'Electricidad', 'Extracción sobre zona de cocción con instalación eléctrica y ventilación adecuadas.'),
    ('COC-CON-LAV', 'Kit conexión lavaplatos con sifón y flexibles', 18990, 35, 'Gasfitería', 'Conexión de agua y descarga de lavaplatos compatible.'),

    # Cercos y portones
    ('CER-MAL-1825', 'Malla galvanizada para cerco 1,80 x 25 m', 89990, 20, 'Construcción', 'Cierre perimetral sobre postes y tensores compatibles.'),
    ('CER-POS-240', 'Poste galvanizado para cerco 60 mm x 2,40 m', 22990, 75, 'Construcción', 'Soporte vertical para sistemas de cierre compatibles.'),
    ('CER-ALA-50', 'Alambre tensor galvanizado rollo 50 m', 12990, 42, 'Ferretería', 'Tensado de malla en cercos con anclajes apropiados.'),
    ('CER-PAN-2520', 'Panel cerco electrosoldado 2,50 x 2 m', 64990, 26, 'Construcción', 'Cierre modular rígido entre postes compatibles.'),
    ('CER-POR-9020', 'Portón peatonal metálico 90 x 200 cm', 139990, 9, 'Construcción', 'Acceso peatonal en cierre con pilares y bisagras dimensionados.'),

    # Deck y terraza de madera
    ('DEC-PIN-1432', 'Tabla deck pino impregnado 1 x 4 pulgadas x 3,20 m', 8990, 95, 'Construcción', 'Superficie de deck exterior sobre estructura ventilada compatible.'),
    ('DEC-WPC-220', 'Tabla deck WPC 22 x 140 mm x 2,20 m', 19990, 70, 'Construcción', 'Terminación de deck exterior con separaciones y fijaciones del sistema.'),
    ('DEC-TOR-100', 'Tornillo deck inoxidable 5 x 60 mm pack 100', 15990, 38, 'Ferretería', 'Fijación de tablas de deck a estructura compatible.'),
    ('DEC-PRO-4L', 'Protector madera exterior para deck 4 litros', 34990, 24, 'Pinturas', 'Protección y terminación de madera exterior preparada.'),

    # Energía solar
    ('SOL-PAN-450', 'Panel solar fotovoltaico monocristalino 450 W', 159990, 14, 'Electricidad', 'Generación fotovoltaica en sistema calculado e instalado por especialista.'),
    ('SOL-INV-3K', 'Inversor solar onda pura 3 kW', 399990, 7, 'Electricidad', 'Conversión de energía en sistema fotovoltaico compatible y protegido.'),
    ('SOL-MPPT-40', 'Controlador carga solar MPPT 40 A', 149990, 10, 'Electricidad', 'Gestión de carga en sistema solar compatible con paneles y baterías.'),
    ('SOL-BAT-100', 'Batería solar LiFePO4 12 V 100 Ah', 449990, 6, 'Electricidad', 'Almacenamiento de energía en sistema dimensionado y protegido.'),
    ('SOL-RIE-240', 'Riel aluminio para panel solar 2,40 m', 24990, 35, 'Construcción', 'Soporte de paneles con anclajes definidos para la cubierta.'),

    # Calefacción y gas
    ('GAS-CAL-GN10', 'Calefont tiro natural 10 litros gas natural', 229990, 7, 'Gasfitería', 'Producción de agua caliente; instalación y ventilación por profesional autorizado.'),
    ('GAS-CAL-GL10', 'Calefont tiro natural 10 litros gas licuado', 229990, 7, 'Gasfitería', 'Producción de agua caliente; instalación y ventilación por profesional autorizado.'),
    ('GAS-TUB-CU12', 'Tubo cobre tipo L 1/2 pulgada x 6 m', 39990, 24, 'Gasfitería', 'Conducción en instalación dimensionada y ejecutada por profesional autorizado.'),
    ('GAS-REG-GLP', 'Regulador gas licuado baja presión', 18990, 20, 'Gasfitería', 'Regulación en instalación de gas compatible y certificada.'),
    ('GAS-VAL-12', 'Válvula corte gas bronce 1/2 pulgada', 10990, 32, 'Gasfitería', 'Corte de suministro en red compatible instalada por profesional autorizado.'),

    # Piscina
    ('PIS-BOM-1HP', 'Bomba piscina autocebante 1 HP', 219990, 8, 'Gasfitería', 'Circulación de agua en sistema hidráulico de piscina dimensionado.'),
    ('PIS-FIL-500', 'Filtro arena piscina 500 mm', 269990, 6, 'Gasfitería', 'Filtración en conjunto compatible con bomba, caudal y volumen de piscina.'),
    ('PIS-SKI-UNI', 'Skimmer piscina boca estándar', 49990, 15, 'Gasfitería', 'Captación superficial en piscina compatible con su sistema hidráulico.'),
    ('PIS-PVC-506', 'Tubo PVC presión 50 mm x 6 m', 22990, 36, 'Gasfitería', 'Conducción de agua en circuito de piscina con fittings compatibles.'),
    ('PIS-FOC-12V', 'Foco LED piscina 12 V', 89990, 12, 'Iluminación', 'Iluminación sumergible mediante transformador y protección compatibles.'),
    ('PIS-LIM-KIT', 'Kit limpieza piscina con pértiga y aspirador', 59990, 18, 'Otra', 'Limpieza manual de fondo y superficie de piscina.'),

    # Automatización de portón
    ('AUT-MOT-600', 'Motor portón corredera hasta 600 kg', 299990, 6, 'Electricidad', 'Automatización de portón compatible con peso, recorrido y alimentación.'),
    ('AUT-CRE-100', 'Cremallera nylon para portón automático 1 m', 17990, 30, 'Ferretería', 'Transmisión de movimiento entre motor y portón compatible.'),
    ('AUT-FOT-PAR', 'Fotocelda seguridad portón automático par', 39990, 16, 'Electricidad', 'Detección de obstáculos como parte de un sistema automático compatible.'),
    ('AUT-CON-REM', 'Control remoto portón automático 433 MHz', 14990, 28, 'Electricidad', 'Accionamiento de receptor compatible con la misma frecuencia y codificación.'),

    # Ventilación
    ('VEN-EXT-150', 'Extractor baño 150 mm', 34990, 20, 'Electricidad', 'Renovación de aire en baño con descarga y alimentación adecuadas.'),
    ('VEN-DUC-100', 'Ducto flexible ventilación 100 mm x 3 m', 12990, 34, 'Construcción', 'Conducción de aire entre extractor y descarga compatible.'),
    ('VEN-REJ-100', 'Rejilla exterior ventilación 100 mm', 6990, 45, 'Construcción', 'Terminación exterior de descarga de ventilación compatible.'),
    ('VEN-LIN-150', 'Extractor en línea 150 mm', 79990, 10, 'Electricidad', 'Extracción en ducto dimensionado para el caudal requerido.'),

    # Iluminación
    ('ILU-REF-50', 'Reflector LED exterior 50 W IP65', 24990, 30, 'Iluminación', 'Iluminación exterior en circuito y soporte compatibles.'),
    ('ILU-PLA-18', 'Plafón LED sobrepuesto 18 W', 15990, 38, 'Iluminación', 'Iluminación general interior en punto eléctrico compatible.'),
    ('ILU-SEN-MOV', 'Sensor movimiento exterior 180 grados', 16990, 26, 'Iluminación', 'Control automático de luminaria compatible.'),
    ('ILU-EST-JAR', 'Estaca LED jardín exterior', 12990, 32, 'Iluminación', 'Iluminación de senderos y jardín con alimentación compatible.'),
    ('ILU-AMP-12', 'Ampolleta LED E27 12 W luz cálida', 3990, 85, 'Iluminación', 'Iluminación en portalámpara E27 compatible.'),

    # Muebles y carpintería
    ('MUE-COR-450', 'Corredera telescópica cajón 45 cm par', 9990, 45, 'Ferretería', 'Deslizamiento de cajón con dimensiones y carga compatibles.'),
    ('MUE-BIS-35', 'Bisagra cazoleta 35 mm cierre suave par', 6990, 60, 'Ferretería', 'Apertura de puerta de mueble perforada para cazoleta compatible.'),
    ('MUE-TIR-128', 'Tirador mueble 128 mm acero', 3990, 80, 'Ferretería', 'Apertura de puerta o cajón con perforación de 128 mm.'),
    ('MUE-MEL-18', 'Plancha melamina blanca 18 mm 1,83 x 2,50 m', 49990, 28, 'Construcción', 'Fabricación de muebles interiores en ambiente seco.'),
    ('MUE-CUB-MAD', 'Cubierta madera finger joint 30 mm 60 x 240 cm', 79990, 14, 'Construcción', 'Cubierta de mueble interior con sellado y apoyo adecuados.'),

    # Obras sanitarias mayores
    ('SAN-EST-1000', 'Estanque agua potable vertical 1000 litros', 249990, 8, 'Gasfitería', 'Almacenamiento de agua en base nivelada y sistema sanitario compatible.'),
    ('SAN-BOM-PRE', 'Bomba presurizadora agua 1 HP', 189990, 9, 'Gasfitería', 'Presurización de red dimensionada con protecciones compatibles.'),
    ('SAN-CAM-6040', 'Cámara inspección PVC 60 x 40 cm', 79990, 12, 'Gasfitería', 'Acceso de inspección en red sanitaria diseñada con cotas adecuadas.'),
    ('SAN-DRE-110', 'Tubo drenaje perforado 110 mm x 6 m', 29990, 28, 'Gasfitería', 'Drenaje subterráneo con pendiente, geotextil y relleno apropiados.'),
    ('SAN-SUM-100', 'Sumidero piso acero inoxidable 100 mm', 15990, 34, 'Gasfitería', 'Recepción de agua superficial conectada a descarga compatible.'),
]


def cargar_catalogo(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    for codigo, nombre, precio, stock, categoria, uso in PRODUCTOS:
        Producto.objects.update_or_create(sku=f'TEST-AMP-{codigo}', defaults={
            'nombre': nombre,
            'descripcion': uso,
            'precio': precio,
            'imagen': '',
            'stock': stock,
            'stock_minimo': 3,
            'marca': 'Genérico SFI',
            'categoria': categoria,
            'activo': True,
            'unidad_venta': 'unidad',
            'contenido': None,
            'unidad_contenido': '',
            'tipo_calculo': 'unidad',
            'rendimiento': None,
            'unidad_rendimiento': '',
            'porcentaje_desperdicio': '0.00',
            'uso_recomendado': uso,
            'especificaciones': {
                'Validación necesaria': 'Confirmar ficha, compatibilidad y condiciones de instalación con el proveedor.',
                'Origen del registro': 'Ampliación de catálogo de prueba SFI 13-11-2026',
            },
            'informacion_tecnica_verificada': False,
        })


def retirar_catalogo(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.filter(sku__startswith='TEST-AMP-').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('productos', '0028_catalogo_tejas'),
    ]

    operations = [
        migrations.RunPython(cargar_catalogo, retirar_catalogo),
    ]
