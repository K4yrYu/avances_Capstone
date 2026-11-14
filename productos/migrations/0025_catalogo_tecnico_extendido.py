from django.db import migrations


# Catálogo genérico de prueba. Las medidas forman parte del nombre y de la
# ficha técnica para que el asistente pueda distinguir formatos compatibles.
PRODUCTOS = [
    # Tabiques, cielos y aislación
    dict(sku='TEST-EXT-TAB-YES-RH', nombre='Plancha yeso-cartón RH 12,5 mm 1,20 x 2,40 m', precio=15990, stock=45, categoria='Construcción', contenido='2.880', unidad='m2', calculo='superficie', rendimiento='2.880', medida='12,5 mm; 1,20 x 2,40 m', uso='Tabiques y cielos interiores en zonas húmedas protegidas.'),
    dict(sku='TEST-EXT-TAB-YES-RF', nombre='Plancha yeso-cartón RF 12,5 mm 1,20 x 2,40 m', precio=18990, stock=36, categoria='Construcción', contenido='2.880', unidad='m2', calculo='superficie', rendimiento='2.880', medida='12,5 mm; 1,20 x 2,40 m', uso='Tabiques y cielos interiores donde se especifique resistencia al fuego.'),
    dict(sku='TEST-EXT-TAB-PAS-25', nombre='Pasta para juntas yeso-cartón saco 25 kg', precio=17990, stock=30, categoria='Construcción', contenido='25.000', unidad='kg', calculo='superficie', rendimiento='35.000', medida='Saco 25 kg; cobertura referencial 35 m²', uso='Tratamiento de juntas de yeso-cartón con cinta compatible.'),
    dict(sku='TEST-EXT-TAB-CIN-75', nombre='Cinta de papel para juntas 50 mm x 75 m', precio=4990, stock=55, categoria='Construcción', contenido='75.000', unidad='m', calculo='longitud', medida='50 mm x 75 m', uso='Refuerzo de juntas de planchas de yeso-cartón.'),
    dict(sku='TEST-EXT-TAB-ESQ-25', nombre='Esquinero galvanizado 25 mm x 2,40 m', precio=2490, stock=70, categoria='Construcción', contenido='2.400', unidad='m', calculo='longitud', medida='25 mm x 2,40 m', uso='Protección y terminación de esquinas exteriores de tabiques.'),
    dict(sku='TEST-EXT-TAB-MON-90', nombre='Perfil montante galvanizado 90 x 38 mm x 2,40 m', precio=4990, stock=65, categoria='Construcción', contenido='2.400', unidad='m', calculo='longitud', medida='90 x 38 mm; largo 2,40 m', uso='Estructura interior de tabiques no estructurales.'),
    dict(sku='TEST-EXT-TAB-CAN-90', nombre='Perfil canal galvanizado 92 x 30 mm x 3 m', precio=4590, stock=60, categoria='Construcción', contenido='3.000', unidad='m', calculo='longitud', medida='92 x 30 mm; largo 3 m', uso='Solera superior e inferior para tabiques con montante de 90 mm.'),
    dict(sku='TEST-EXT-TAB-TOR-25', nombre='Tornillo yeso-cartón punta fina 6 x 1 pulgada caja 1000', precio=10990, stock=25, categoria='Ferretería', contenido='1000.000', unidad='unidad', calculo='unidad', medida='6 x 1 pulgada; caja 1000 unidades', uso='Fijación de planchas de yeso-cartón a perfilería metálica liviana.'),
    dict(sku='TEST-EXT-AIS-ROC-72', nombre='Lana mineral 50 mm paquete 7,20 m²', precio=34990, stock=22, categoria='Construcción', contenido='7.200', unidad='m2', calculo='superficie', rendimiento='7.200', medida='Espesor 50 mm; cobertura 7,20 m²', uso='Aislación termoacústica protegida en tabiques y cielos.'),

    # Techumbre y evacuación de aguas lluvia
    dict(sku='TEST-EXT-TEC-POL-A6', nombre='Policarbonato alveolar 6 mm 1,05 x 2,90 m', precio=32990, stock=32, categoria='Construcción', contenido='3.045', unidad='m2', calculo='superficie', rendimiento='3.045', medida='6 mm; 1,05 x 2,90 m', uso='Cubiertas livianas con estructura y perfiles compatibles.'),
    dict(sku='TEST-EXT-TEC-POL-O8', nombre='Policarbonato ondulado 0,8 mm 0,90 x 2,80 m', precio=22990, stock=38, categoria='Construcción', contenido='2.520', unidad='m2', calculo='superficie', rendimiento='2.520', medida='0,8 mm; 0,90 x 2,80 m', uso='Cubiertas livianas con pendiente y apoyos definidos por el fabricante.'),
    dict(sku='TEST-EXT-TEC-ZIN-250', nombre='Plancha zinc acanalado 0,35 mm x 2,50 m', precio=16990, stock=42, categoria='Construcción', contenido='2.125', unidad='m2', calculo='superficie', rendimiento='2.125', medida='0,35 mm; ancho útil 0,85 m; largo 2,50 m', uso='Cubiertas exteriores con traslape, pendiente y fijación compatibles.'),
    dict(sku='TEST-EXT-TEC-CUM-200', nombre='Cumbrera galvanizada 0,35 mm x 2 m', precio=10990, stock=35, categoria='Construcción', contenido='2.000', unidad='m', calculo='longitud', medida='0,35 mm x 2 m', uso='Remate superior de cubiertas metálicas compatibles.'),
    dict(sku='TEST-EXT-TEC-BUT-10', nombre='Cinta butílica impermeable 100 mm x 10 m', precio=12990, stock=28, categoria='Adhesivos', contenido='10.000', unidad='m', calculo='longitud', medida='100 mm x 10 m', uso='Sellado de encuentros y traslapes autorizados por el sistema de cubierta.'),
    dict(sku='TEST-EXT-TEC-TOR-100', nombre='Tornillo techo autoperforante 12 x 2 pulgadas pack 100', precio=13990, stock=40, categoria='Ferretería', contenido='100.000', unidad='unidad', calculo='unidad', medida='12 x 2 pulgadas; golilla EPDM; pack 100', uso='Fijación de cubierta metálica sobre estructura compatible.'),
    dict(sku='TEST-EXT-TEC-CAN-G3', nombre='Canaleta galvanizada aguas lluvia 125 mm x 3 m', precio=18990, stock=30, categoria='Construcción', contenido='3.000', unidad='m', calculo='longitud', medida='Diámetro nominal 125 mm; largo 3 m', uso='Recolección de aguas lluvia en techumbres compatibles.'),
    dict(sku='TEST-EXT-TEC-BAJ-G3', nombre='Bajada galvanizada aguas lluvia 80 mm x 3 m', precio=15990, stock=30, categoria='Construcción', contenido='3.000', unidad='m', calculo='longitud', medida='Diámetro 80 mm; largo 3 m', uso='Conducción vertical de aguas lluvia desde canaletas compatibles.'),

    # Hormigón, albañilería e impermeabilización
    dict(sku='TEST-EXT-ALB-FIE-08', nombre='Fierro estriado 8 mm x 6 m', precio=4990, stock=90, categoria='Construcción', contenido='6.000', unidad='m', calculo='longitud', medida='Diámetro 8 mm; largo 6 m', uso='Armaduras según cálculo y especificación estructural.'),
    dict(sku='TEST-EXT-ALB-FIE-12', nombre='Fierro estriado 12 mm x 6 m', precio=8990, stock=75, categoria='Construcción', contenido='6.000', unidad='m', calculo='longitud', medida='Diámetro 12 mm; largo 6 m', uso='Armaduras según cálculo y especificación estructural.'),
    dict(sku='TEST-EXT-ALB-HOR-25', nombre='Hormigón predosificado H20 saco 25 kg', precio=4990, stock=110, categoria='Construcción', contenido='25.000', unidad='kg', calculo='peso', medida='Saco 25 kg', uso='Hormigonado de elementos no críticos según dosificación y ficha del fabricante.'),
    dict(sku='TEST-EXT-ALB-EST-25', nombre='Estuco exterior predosificado saco 25 kg', precio=6990, stock=75, categoria='Construcción', contenido='25.000', unidad='kg', calculo='superficie', rendimiento='5.000', medida='Saco 25 kg; cobertura 5 m² a espesor indicado', uso='Revestimiento de muros exteriores minerales preparados.'),
    dict(sku='TEST-EXT-ALB-IMP-20', nombre='Impermeabilizante cementicio saco 20 kg', precio=24990, stock=38, categoria='Construcción', contenido='20.000', unidad='kg', calculo='superficie', rendimiento='10.000', medida='Saco 20 kg; cobertura 10 m²', uso='Impermeabilización cementicia de superficies minerales compatibles.'),
    dict(sku='TEST-EXT-ALB-BLO-19', nombre='Bloque hormigón 19 x 19 x 39 cm', precio=2490, stock=240, categoria='Construcción', contenido='1.000', unidad='unidad', calculo='unidad', medida='19 x 19 x 39 cm', uso='Muros y cierres según diseño, fundación y refuerzo especificados.'),
    dict(sku='TEST-EXT-ALB-ADO-50', nombre='Adoquín de hormigón 10 x 20 x 6 cm pack 50', precio=34990, stock=35, categoria='Construcción', contenido='1.000', unidad='m2', calculo='superficie', rendimiento='1.000', medida='10 x 20 x 6 cm; pack para 1 m²', uso='Pavimentos peatonales sobre base compactada y confinada.'),

    # Pisos y revestimientos
    dict(sku='TEST-EXT-PIS-CER-145', nombre='Cerámica muro blanca 30 x 60 cm caja 1,44 m²', precio=15990, stock=48, categoria='Construcción', contenido='1.440', unidad='m2', calculo='superficie', rendimiento='1.440', medida='Palmeta 30 x 60 cm; caja 1,44 m²', uso='Revestimiento de muros interiores preparados.'),
    dict(sku='TEST-EXT-PIS-VIN-220', nombre='Piso vinílico SPC 5 mm caja 2,20 m²', precio=39990, stock=40, categoria='Construcción', contenido='2.200', unidad='m2', calculo='superficie', rendimiento='2.200', medida='Espesor 5 mm; caja 2,20 m²', uso='Pisos interiores nivelados y preparados según sistema de instalación.'),
    dict(sku='TEST-EXT-PIS-NIV-20', nombre='Nivelador de piso saco 20 kg', precio=18990, stock=42, categoria='Construcción', contenido='20.000', unidad='kg', calculo='superficie', rendimiento='4.000', medida='Saco 20 kg; cobertura 4 m² a 3 mm', uso='Nivelación de superficies interiores compatibles antes del revestimiento.'),
    dict(sku='TEST-EXT-PIS-GUA-240', nombre='Guardapolvo MDF blanco 70 x 12 mm x 2,40 m', precio=6990, stock=80, categoria='Construcción', contenido='2.400', unidad='m', calculo='longitud', medida='70 x 12 mm; largo 2,40 m', uso='Terminación perimetral interior de pisos.'),
    dict(sku='TEST-EXT-PIS-SEP-200', nombre='Separador cerámico cruz 3 mm bolsa 200', precio=2990, stock=65, categoria='Ferretería', contenido='200.000', unidad='unidad', calculo='unidad', medida='Cruz 3 mm; bolsa 200 unidades', uso='Control de junta durante instalación de cerámicas.'),
    dict(sku='TEST-EXT-PIS-FRA-02', nombre='Fragüe flexible gris bolsa 2 kg', precio=4990, stock=55, categoria='Adhesivos', contenido='2.000', unidad='kg', calculo='superficie', rendimiento='8.000', medida='Bolsa 2 kg; cobertura 8 m² referencial', uso='Relleno de juntas de revestimientos compatibles.'),

    # Agua potable y alcantarillado
    dict(sku='TEST-EXT-GAS-PPR-25', nombre='Tubo PPR agua potable 25 mm x 6 m', precio=10990, stock=45, categoria='Gasfitería', contenido='6.000', unidad='m', calculo='longitud', medida='Diámetro 25 mm; largo 6 m', uso='Redes de agua potable termofusionadas por instalador competente.'),
    dict(sku='TEST-EXT-GAS-COD-25', nombre='Codo PPR 25 mm 90 grados', precio=1290, stock=120, categoria='Gasfitería', contenido='1.000', unidad='unidad', calculo='unidad', medida='Diámetro 25 mm; ángulo 90°', uso='Cambio de dirección en redes PPR de 25 mm.'),
    dict(sku='TEST-EXT-GAS-TEE-25', nombre='Tee PPR 25 mm', precio=1590, stock=100, categoria='Gasfitería', contenido='1.000', unidad='unidad', calculo='unidad', medida='Tres conexiones de 25 mm', uso='Derivación de redes PPR de 25 mm.'),
    dict(sku='TEST-EXT-GAS-PVC-50', nombre='Tubo PVC sanitario 50 mm x 6 m', precio=10990, stock=50, categoria='Gasfitería', contenido='6.000', unidad='m', calculo='longitud', medida='Diámetro 50 mm; largo 6 m', uso='Descargas sanitarias compatibles con diámetro de 50 mm.'),
    dict(sku='TEST-EXT-GAS-PVC-75', nombre='Tubo PVC sanitario 75 mm x 6 m', precio=16990, stock=40, categoria='Gasfitería', contenido='6.000', unidad='m', calculo='longitud', medida='Diámetro 75 mm; largo 6 m', uso='Descargas sanitarias compatibles con diámetro de 75 mm.'),
    dict(sku='TEST-EXT-GAS-ADH-250', nombre='Adhesivo PVC sanitario 250 ml', precio=5990, stock=60, categoria='Adhesivos', contenido='250.000', unidad='ml', calculo='unidad', medida='Envase 250 ml', uso='Unión cementada de tuberías y fittings PVC compatibles.'),
    dict(sku='TEST-EXT-GAS-SIF-UNI', nombre='Sifón extensible universal 1 1/2 pulgada', precio=7990, stock=50, categoria='Gasfitería', contenido='1.000', unidad='unidad', calculo='unidad', medida='Conexión 1 1/2 pulgada; largo ajustable', uso='Conexión de descarga de lavaplatos o lavamanos compatibles.'),
    dict(sku='TEST-EXT-GAS-VAL-34', nombre='Válvula bola bronce 3/4 pulgada', precio=8990, stock=55, categoria='Gasfitería', contenido='1.000', unidad='unidad', calculo='unidad', medida='Rosca 3/4 pulgada', uso='Corte de suministro en redes de agua compatibles.'),

    # Electricidad domiciliaria
    dict(sku='TEST-EXT-ELE-CAB-60', nombre='Cable eléctrico 6 mm² rollo 100 m', precio=119990, stock=16, categoria='Electricidad', contenido='100.000', unidad='m', calculo='longitud', medida='Sección 6 mm²; rollo 100 m', uso='Circuitos dimensionados y protegidos por instalador SEC.'),
    dict(sku='TEST-EXT-ELE-CON-25', nombre='Conduit PVC eléctrico 25 mm x 3 m', precio=2490, stock=90, categoria='Electricidad', contenido='3.000', unidad='m', calculo='longitud', medida='Diámetro 25 mm; largo 3 m', uso='Canalización eléctrica embutida o protegida compatible.'),
    dict(sku='TEST-EXT-ELE-AUT-25', nombre='Interruptor automático 25 A curva C', precio=10990, stock=35, categoria='Electricidad', contenido='1.000', unidad='unidad', calculo='unidad', medida='1 polo; 25 A; curva C', uso='Protección de circuito dimensionado por instalador SEC.'),
    dict(sku='TEST-EXT-ELE-DIF-40', nombre='Interruptor diferencial 2P 40 A 30 mA', precio=29990, stock=24, categoria='Electricidad', contenido='1.000', unidad='unidad', calculo='unidad', medida='2 polos; 40 A; sensibilidad 30 mA', uso='Protección diferencial en tablero diseñado por instalador SEC.'),
    dict(sku='TEST-EXT-ELE-TOM-16', nombre='Enchufe doble embutido 16 A blanco', precio=6990, stock=70, categoria='Electricidad', contenido='1.000', unidad='unidad', calculo='unidad', medida='Doble; 16 A; 250 V', uso='Punto de conexión en circuito y caja compatibles.'),
    dict(sku='TEST-EXT-ELE-TAB-12', nombre='Tablero eléctrico sobrepuesto 12 módulos', precio=24990, stock=25, categoria='Electricidad', contenido='12.000', unidad='unidad', calculo='unidad', medida='Capacidad 12 módulos DIN', uso='Alojamiento de protecciones eléctricas dimensionadas por instalador SEC.'),

    # Carpintería y mobiliario
    dict(sku='TEST-EXT-MAD-PIN-22', nombre='Pino dimensionado 2 x 2 pulgadas x 3,20 m', precio=6990, stock=85, categoria='Construcción', contenido='3.200', unidad='m', calculo='longitud', medida='2 x 2 pulgadas; largo 3,20 m', uso='Estructuras livianas de madera según diseño y protección requerida.'),
    dict(sku='TEST-EXT-MAD-PIN-26', nombre='Pino dimensionado 2 x 6 pulgadas x 3,20 m', precio=14990, stock=55, categoria='Construcción', contenido='3.200', unidad='m', calculo='longitud', medida='2 x 6 pulgadas; largo 3,20 m', uso='Estructuras de madera según cálculo y condición de exposición.'),
    dict(sku='TEST-EXT-MAD-TER-12', nombre='Tablero terciado estructural 12 mm 1,22 x 2,44 m', precio=26990, stock=40, categoria='Construcción', contenido='2.977', unidad='m2', calculo='superficie', rendimiento='2.977', medida='12 mm; 1,22 x 2,44 m', uso='Revestimientos y componentes de madera protegidos según proyecto.'),
    dict(sku='TEST-EXT-MAD-COL-01', nombre='Adhesivo para madera interior envase 1 kg', precio=7990, stock=45, categoria='Adhesivos', contenido='1.000', unidad='kg', calculo='unidad', medida='Envase 1 kg', uso='Encolado de uniones de madera interior limpias y ajustadas.'),

    # Jardín y riego
    dict(sku='TEST-EXT-JAR-GOT-25', nombre='Manguera riego por goteo 16 mm x 25 m', precio=18990, stock=30, categoria='Otra', contenido='25.000', unidad='m', calculo='longitud', medida='Diámetro 16 mm; rollo 25 m', uso='Líneas de riego por goteo con presión y conectores compatibles.'),
    dict(sku='TEST-EXT-JAR-SUS-50', nombre='Sustrato universal saco 50 litros', precio=8990, stock=60, categoria='Otra', contenido='1.000', unidad='unidad', calculo='unidad', medida='Saco 50 litros', uso='Preparación de maceteros y mejoramiento de suelo según especie vegetal.'),
    dict(sku='TEST-EXT-JAR-BOR-10', nombre='Borde jardín flexible 10 cm x 10 m', precio=12990, stock=35, categoria='Otra', contenido='10.000', unidad='m', calculo='longitud', medida='Alto 10 cm; rollo 10 m', uso='Separación y contención de áreas de jardín.'),
]


def cargar_catalogo(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    for registro in PRODUCTOS:
        datos = dict(registro)
        sku = datos.pop('sku')
        medida = datos.pop('medida')
        uso = datos.pop('uso')
        unidad = datos.pop('unidad')
        calculo = datos.pop('calculo')
        rendimiento = datos.pop('rendimiento', None)
        defaults = {
            **datos,
            'descripcion': uso,
            'imagen': '',
            'stock_minimo': 5,
            'marca': 'Genérico SFI',
            'activo': True,
            'unidad_venta': 'unidad',
            'unidad_contenido': unidad,
            'tipo_calculo': calculo,
            'rendimiento': rendimiento,
            'unidad_rendimiento': 'm2_unidad' if calculo == 'superficie' else '',
            'porcentaje_desperdicio': '10.00' if calculo == 'superficie' else '0.00',
            'uso_recomendado': uso,
            'especificaciones': {
                'Medidas o presentación': medida,
                'Origen del registro': 'Catálogo técnico extendido de prueba SFI 13-11-2026',
            },
            'informacion_tecnica_verificada': True,
        }
        Producto.objects.update_or_create(sku=sku, defaults=defaults)


def retirar_catalogo(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.filter(sku__startswith='TEST-EXT-').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('productos', '0024_catalogo_ampliado_proyectos'),
    ]

    operations = [
        migrations.RunPython(cargar_catalogo, retirar_catalogo),
    ]
