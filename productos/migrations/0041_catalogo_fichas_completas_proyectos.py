from django.db import migrations


# Productos complementarios para que las búsquedas del asistente tengan una
# ficha consistente: uso, medidas, material y compatibilidades. Las imágenes
# se mantienen vacías para ser cargadas desde Administración.
CATALOGO_FICHAS_COMPLETAS = [
    {
        'sku': 'SFI-ELE-CAN-2012', 'nombre': 'Canaleta adhesiva PVC 20 x 12 mm x 2 m',
        'precio': 2990, 'stock': 95, 'categoria': 'Electricidad', 'contenido': '2.000', 'unidad': 'm',
        'uso': 'Ordenar y proteger cables de baja tensión o alimentación en una instalación superficial interior.',
        'ficha': {'Material': 'PVC', 'Medidas': '20 x 12 mm x 2 m', 'Compatibilidad': 'Cableado superficial de sección adecuada', 'Instalación': 'Superficie limpia y seca; no reemplaza conduit en zonas exigidas.'},
    },
    {
        'sku': 'SFI-ELE-CAJ-PAS-100', 'nombre': 'Caja de paso eléctrica 100 x 100 x 50 mm',
        'precio': 3490, 'stock': 80, 'categoria': 'Electricidad', 'contenido': '1.000', 'unidad': 'unidad',
        'uso': 'Alojar derivaciones y empalmes eléctricos autorizados en una instalación protegida.',
        'ficha': {'Material': 'PVC autoextinguible', 'Medidas': '100 x 100 x 50 mm', 'Compatibilidad': 'Canalización eléctrica compatible', 'Instalación': 'Los empalmes deben ser realizados por personal competente.'},
    },
    {
        'sku': 'SFI-ELE-CON-RAP-3', 'nombre': 'Conector rápido eléctrico 3 polos pack 10',
        'precio': 5990, 'stock': 100, 'categoria': 'Electricidad', 'contenido': '10.000', 'unidad': 'unidad',
        'uso': 'Unir conductores eléctricos dentro de una caja de paso compatible.',
        'ficha': {'Material': 'Poliamida y cobre', 'Capacidad': '3 polos por conector', 'Compatibilidad': 'Conductores según calibre declarado por fabricante', 'Instalación': 'Usar dentro de caja de conexión protegida.'},
    },
    {
        'sku': 'SFI-ELE-INT-DOB-10', 'nombre': 'Interruptor doble sobrepuesto 10 A blanco',
        'precio': 4990, 'stock': 70, 'categoria': 'Electricidad', 'contenido': '1.000', 'unidad': 'unidad',
        'uso': 'Controlar dos circuitos de iluminación desde un punto superficial.',
        'ficha': {'Corriente nominal': '10 A', 'Tensión': '250 V', 'Color': 'Blanco', 'Compatibilidad': 'Caja o canaleta superficial compatible'},
    },
    {
        'sku': 'SFI-ELE-ENCH-SUP-16', 'nombre': 'Enchufe doble sobrepuesto 16 A blanco',
        'precio': 6490, 'stock': 65, 'categoria': 'Electricidad', 'contenido': '1.000', 'unidad': 'unidad',
        'uso': 'Incorporar dos puntos de conexión en una instalación eléctrica superficial interior.',
        'ficha': {'Corriente nominal': '16 A', 'Tensión': '250 V', 'Color': 'Blanco', 'Compatibilidad': 'Canaleta y cableado de sección adecuada'},
    },
    {
        'sku': 'SFI-ELE-CAB-TIE-25', 'nombre': 'Cable puesta a tierra verde 2,5 mm2 rollo 50 m',
        'precio': 37990, 'stock': 30, 'categoria': 'Electricidad', 'contenido': '50.000', 'unidad': 'm',
        'uso': 'Formar parte del conductor de protección de un circuito eléctrico dimensionado.',
        'ficha': {'Sección': '2,5 mm²', 'Color': 'Verde', 'Largo': '50 m', 'Compatibilidad': 'Sistema de puesta a tierra definido por electricista competente'},
    },
    {
        'sku': 'SFI-ILU-SOC-E27', 'nombre': 'Portalámpara E27 sobrepuesto blanco',
        'precio': 1990, 'stock': 95, 'categoria': 'Iluminación', 'contenido': '1.000', 'unidad': 'unidad',
        'uso': 'Instalar una ampolleta de base E27 en un punto de iluminación superficial.',
        'ficha': {'Base': 'E27', 'Color': 'Blanco', 'Uso': 'Interior', 'Compatibilidad': 'Ampolletas E27 dentro de potencia permitida'},
    },
    {
        'sku': 'SFI-GAS-COD-PVC-40', 'nombre': 'Codo PVC sanitario 40 mm 90 grados',
        'precio': 1290, 'stock': 120, 'categoria': 'Gasfitería', 'contenido': '1.000', 'unidad': 'unidad',
        'uso': 'Cambiar dirección en una descarga sanitaria de PVC de 40 mm.',
        'ficha': {'Material': 'PVC sanitario', 'Diámetro': '40 mm', 'Ángulo': '90 grados', 'Compatibilidad': 'Tubería PVC sanitaria de 40 mm'},
    },
    {
        'sku': 'SFI-GAS-TEE-PVC-40', 'nombre': 'Tee PVC sanitario 40 mm',
        'precio': 1490, 'stock': 110, 'categoria': 'Gasfitería', 'contenido': '1.000', 'unidad': 'unidad',
        'uso': 'Derivar una descarga sanitaria en tubería de PVC de 40 mm.',
        'ficha': {'Material': 'PVC sanitario', 'Diámetro': '40 mm', 'Tipo': 'Tee', 'Compatibilidad': 'Tubería PVC sanitaria de 40 mm'},
    },
    {
        'sku': 'SFI-GAS-PEG-PVC-240', 'nombre': 'Adhesivo PVC sanitario 240 ml',
        'precio': 4990, 'stock': 65, 'categoria': 'Adhesivos', 'contenido': '240.000', 'unidad': 'ml',
        'uso': 'Unir fittings y tubos de PVC sanitario limpios y compatibles.',
        'ficha': {'Contenido': '240 ml', 'Material compatible': 'PVC sanitario', 'Preparación': 'Corte limpio, prueba en seco y superficies limpias', 'Uso': 'Uniones de desagüe; no usar para agua potable presurizada.'},
    },
    {
        'sku': 'SFI-GAS-TEE-PPR-25', 'nombre': 'Tee PPR agua potable 25 mm',
        'precio': 2490, 'stock': 100, 'categoria': 'Gasfitería', 'contenido': '1.000', 'unidad': 'unidad',
        'uso': 'Derivar una línea de agua en una red PPR de 25 mm termofusionada.',
        'ficha': {'Material': 'PPR', 'Diámetro': '25 mm', 'Tipo': 'Tee', 'Compatibilidad': 'Tubo PPR de 25 mm y termofusora adecuada'},
    },
    {
        'sku': 'SFI-GAS-LLA-PVC-25', 'nombre': 'Válvula bola PVC presión 25 mm',
        'precio': 6990, 'stock': 50, 'categoria': 'Gasfitería', 'contenido': '1.000', 'unidad': 'unidad',
        'uso': 'Abrir o cortar el paso de agua en una línea de PVC presión de 25 mm.',
        'ficha': {'Material': 'PVC presión', 'Diámetro': '25 mm', 'Tipo': 'Válvula bola', 'Compatibilidad': 'Tubería PVC presión de 25 mm'},
    },
    {
        'sku': 'SFI-PIN-BAN-25', 'nombre': 'Bandeja para pintura 25 cm',
        'precio': 2990, 'stock': 85, 'categoria': 'Herramientas', 'contenido': '1.000', 'unidad': 'unidad',
        'uso': 'Cargar rodillos pequeños o medianos durante trabajos de pintura.',
        'ficha': {'Material': 'Plástico', 'Ancho útil': '25 cm', 'Compatibilidad': 'Rodillos de hasta 23 cm', 'Limpieza': 'Lavar tras uso con pintura al agua.'},
    },
    {
        'sku': 'SFI-PIN-EXT-2M', 'nombre': 'Extensión telescópica para rodillo 1 a 2 m',
        'precio': 8990, 'stock': 54, 'categoria': 'Herramientas', 'contenido': '1.000', 'unidad': 'unidad',
        'uso': 'Extender el alcance de un rodillo al pintar muros o cielos.',
        'ficha': {'Material': 'Acero', 'Largo ajustable': '1 a 2 m', 'Compatibilidad': 'Rodillos con rosca estándar', 'Uso': 'Pintura interior o exterior desde suelo firme.'},
    },
    {
        'sku': 'SFI-PIN-ESP-100', 'nombre': 'Espátula acero flexible 100 mm',
        'precio': 3490, 'stock': 76, 'categoria': 'Herramientas', 'contenido': '1.000', 'unidad': 'unidad',
        'uso': 'Aplicar pasta muro, retirar pintura suelta o reparar imperfecciones pequeñas.',
        'ficha': {'Material': 'Acero flexible', 'Ancho': '100 mm', 'Compatibilidad': 'Pasta muro y preparación de superficies', 'Uso': 'Preparación previa a pintura.'},
    },
    {
        'sku': 'SFI-PIN-SEL-ACR-300', 'nombre': 'Sellador acrílico pintable blanco 300 ml',
        'precio': 3990, 'stock': 70, 'categoria': 'Adhesivos', 'contenido': '300.000', 'unidad': 'ml',
        'uso': 'Sellar grietas finas y uniones interiores antes de pintar.',
        'ficha': {'Base': 'Acrílica', 'Contenido': '300 ml', 'Color': 'Blanco', 'Compatibilidad': 'Yeso, estuco, hormigón y madera interior; confirmar secado antes de pintar.'},
    },
    {
        'sku': 'SFI-CON-MAL-RAS-80', 'nombre': 'Malla raschel sombra 80% verde rollo 2 x 10 m',
        'precio': 24990, 'stock': 34, 'categoria': 'Construcción', 'contenido': '20.000', 'unidad': 'm2',
        'uso': 'Generar sombra en patios, viveros y cierres livianos temporales.',
        'ficha': {'Material': 'Polietileno HDPE', 'Sombra': '80%', 'Medidas': '2 x 10 m', 'Compatibilidad': 'Estructuras livianas con fijación adecuada'},
    },
    {
        'sku': 'SFI-CON-PER-COC-38', 'nombre': 'Perno coche galvanizado 3/8 x 4 pulgadas pack 10',
        'precio': 6990, 'stock': 62, 'categoria': 'Ferretería', 'contenido': '10.000', 'unidad': 'unidad',
        'uso': 'Unir piezas de madera o estructuras livianas mediante perforación pasante.',
        'ficha': {'Material': 'Acero galvanizado', 'Medida': '3/8 x 4 pulgadas', 'Contenido': '10 unidades', 'Compatibilidad': 'Madera perforada y tuerca/arandela compatible'},
    },
    {
        'sku': 'SFI-CAR-BIS-3', 'nombre': 'Bisagra puerta acero zincado 3 pulgadas par',
        'precio': 4490, 'stock': 70, 'categoria': 'Ferretería', 'contenido': '2.000', 'unidad': 'unidad',
        'uso': 'Permitir el giro de puertas livianas de madera o muebles.',
        'ficha': {'Material': 'Acero zincado', 'Medida': '3 pulgadas', 'Contenido': 'Par', 'Compatibilidad': 'Puertas livianas con tornillos adecuados'},
    },
    {
        'sku': 'SFI-CAR-TOR-MAD-8X2', 'nombre': 'Tornillo para madera 8 x 2 pulgadas pack 100',
        'precio': 5990, 'stock': 100, 'categoria': 'Ferretería', 'contenido': '100.000', 'unidad': 'unidad',
        'uso': 'Fijar piezas de madera en muebles, revestimientos o estructuras livianas.',
        'ficha': {'Material': 'Acero zincado', 'Medida': '8 x 2 pulgadas', 'Contenido': '100 unidades', 'Compatibilidad': 'Madera y tableros; realizar perforación guía cuando corresponda.'},
    },
    {
        'sku': 'SFI-HER-COM-4LB', 'nombre': 'Combo acero 4 lb mango fibra',
        'precio': 18990, 'stock': 38, 'categoria': 'Herramientas', 'contenido': '1.000', 'unidad': 'unidad',
        'uso': 'Golpear cinceles, estacas o elementos de mampostería en trabajos de demolición controlada.',
        'ficha': {'Cabeza': '4 lb', 'Mango': 'Fibra', 'Compatibilidad': 'Cinceles y estacas adecuadas', 'Seguridad': 'Usar lentes y guantes de protección.'},
    },
    {
        'sku': 'SFI-HER-CIN-MAM-250', 'nombre': 'Cincel para mampostería 250 mm',
        'precio': 6990, 'stock': 44, 'categoria': 'Herramientas', 'contenido': '1.000', 'unidad': 'unidad',
        'uso': 'Picar piedra, ladrillo u hormigón de forma localizada junto con un combo compatible.',
        'ficha': {'Material': 'Acero templado', 'Largo': '250 mm', 'Compatibilidad': 'Combo o martillo adecuado', 'Seguridad': 'Usar lentes y guantes de protección.'},
    },
    {
        'sku': 'SFI-HER-BAR-1200', 'nombre': 'Barreta de acero 1,2 m',
        'precio': 17990, 'stock': 30, 'categoria': 'Herramientas', 'contenido': '1.000', 'unidad': 'unidad',
        'uso': 'Hacer palanca, remover piedras o aflojar suelo compacto de manera manual.',
        'ficha': {'Material': 'Acero', 'Largo': '1,2 m', 'Uso': 'Palanca y remoción manual', 'Seguridad': 'Usar guantes y mantener distancia de terceros.'},
    },
    {
        'sku': 'SFI-SEG-LEN-CLAR', 'nombre': 'Lentes seguridad policarbonato transparentes',
        'precio': 3490, 'stock': 120, 'categoria': 'Seguridad', 'contenido': '1.000', 'unidad': 'unidad',
        'uso': 'Proteger los ojos frente a partículas durante corte, perforación, lijado o picado.',
        'ficha': {'Material': 'Policarbonato', 'Color': 'Transparente', 'Uso': 'Protección ocular', 'Compatibilidad': 'Trabajos manuales y eléctricos de bajo riesgo'},
    },
    {
        'sku': 'SFI-SEG-RES-P95', 'nombre': 'Respirador reutilizable P95 con filtro',
        'precio': 14990, 'stock': 48, 'categoria': 'Seguridad', 'contenido': '1.000', 'unidad': 'unidad',
        'uso': 'Reducir exposición a polvo fino durante lijado, corte o manejo de materiales particulados.',
        'ficha': {'Protección': 'P95', 'Tipo': 'Reutilizable con filtro', 'Uso': 'Polvo y partículas', 'Limitación': 'No usar para gases ni ambientes sin ventilación adecuada.'},
    },
]


def cargar_catalogo_fichas_completas(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Proveedor = apps.get_model('productos', 'Proveedor')
    proveedor = Proveedor.objects.filter(nombre='Proveedor General SFI', activo=True).first()
    for producto in CATALOGO_FICHAS_COMPLETAS:
        Producto.objects.update_or_create(
            sku=producto['sku'],
            defaults={
                'nombre': producto['nombre'],
                'descripcion': producto['uso'],
                'precio': producto['precio'],
                'stock': producto['stock'],
                'stock_minimo': max(3, producto['stock'] // 6),
                'categoria': producto['categoria'],
                'modelo': producto['sku'],
                'imagen': '',
                'activo': True,
                'marca': 'Genérico SFI',
                'ambiente_uso': 'interior_exterior',
                'superficies_compatibles': [],
                'tipo_pintura': 'no_aplica',
                'terminacion': 'no_aplica',
                'propiedades_pintura': [],
                'preparaciones_recomendadas': [],
                'secado_tacto_horas': None,
                'repintado_min_horas': None,
                'repintado_max_horas': None,
                'unidad_venta': 'unidad',
                'contenido': producto['contenido'],
                'unidad_contenido': producto['unidad'],
                'tipo_calculo': 'unidad',
                'rendimiento': None,
                'unidad_rendimiento': '',
                'capas_recomendadas': None,
                'porcentaje_desperdicio': '0.00',
                'proveedor_id': proveedor.pk if proveedor else None,
                'uso_recomendado': producto['uso'],
                'especificaciones': producto['ficha'],
                'informacion_tecnica_verificada': False,
            },
        )


def retirar_catalogo_fichas_completas(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.filter(sku__in=[producto['sku'] for producto in CATALOGO_FICHAS_COMPLETAS]).delete()


class Migration(migrations.Migration):
    dependencies = [('productos', '0040_catalogo_complementos_proyectos')]
    operations = [migrations.RunPython(cargar_catalogo_fichas_completas, retirar_catalogo_fichas_completas)]
