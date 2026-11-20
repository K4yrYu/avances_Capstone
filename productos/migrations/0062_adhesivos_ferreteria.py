from decimal import Decimal

from django.db import migrations


PRODUCTOS = (
    {
        'sku': 'SFI-ADH-GOT-LIQ-2',
        'nombre': 'Adhesivo instantáneo La Gotita líquido 2 ml',
        'marca': 'La Gotita',
        'modelo': 'Líquido 2 ml',
        'precio': 3990,
        'contenido': '2.000',
        'unidad_contenido': 'ml',
        'stock': 30,
        'descripcion': (
            'Adhesivo instantáneo transparente para reparaciones pequeñas y piezas que '
            'encajan correctamente. Une en pocos segundos aplicando una sola gota.'
        ),
        'uso_recomendado': (
            'Pequeños arreglos de cerámica, madera, metal, goma, porcelana y plásticos '
            'compatibles. No usar en polietileno, polipropileno ni PTFE/Teflón.'
        ),
        'superficies': ['cerámica', 'madera', 'metal', 'goma', 'porcelana', 'plástico compatible'],
        'especificaciones': {
            'familia_adhesivo': 'cianoacrilato instantáneo',
            'consistencia': 'líquida',
            'color': 'transparente',
            'tiempo_sujecion_segundos': 60,
            'aplicacion_recomendada': 'Una gota sobre una de las superficies',
            'preparacion': 'Piezas limpias, secas y con encaje correcto',
            'no_compatible': ['polietileno', 'polipropileno', 'PTFE/Teflón'],
            'fuente_tecnica': 'https://servicioalconsumidor.akapol.com/hc/es-419/articles/47103687481108--C%C3%B3mo-se-usa-LA-GOTITA',
            'fuente_precio': 'https://www.sodimac.cl/sodimac-cl/articulo/110325337/adhesivo-instantaneo-la-gotita-liquido-2-ml/110325340',
        },
    },
    {
        'sku': 'SFI-ADH-GOT-GEL-3',
        'nombre': 'Adhesivo instantáneo La Gotita Gel 3 g',
        'marca': 'La Gotita',
        'modelo': 'Gel 3 g',
        'precio': 4990,
        'contenido': '3.000',
        'unidad_contenido': 'g',
        'stock': 25,
        'descripcion': (
            'Adhesivo instantáneo en gel para aplicaciones controladas, superficies '
            'verticales y pequeñas holguras donde un adhesivo líquido podría escurrir.'
        ),
        'uso_recomendado': (
            'Reparaciones pequeñas en cerámica, madera, metal, goma, porcelana y plásticos '
            'compatibles. No usar en polietileno, polipropileno ni PTFE/Teflón.'
        ),
        'superficies': ['cerámica', 'madera', 'metal', 'goma', 'porcelana', 'plástico compatible'],
        'especificaciones': {
            'familia_adhesivo': 'cianoacrilato instantáneo',
            'consistencia': 'gel',
            'color': 'transparente',
            'aplicacion_recomendada': 'Cantidad pequeña sobre una de las superficies',
            'preparacion': 'Superficies limpias, secas y libres de grasa',
            'no_compatible': ['polietileno', 'polipropileno', 'PTFE/Teflón'],
            'fuente_tecnica': 'https://akapol.com/wp-content/uploads/2023/03/La-Gotita-GEL.pdf',
            'fuente_precio': 'https://www.sodimac.cl/sodimac-cl/b/la-gotita',
        },
    },
    {
        'sku': 'SFI-ADH-ECC-9',
        'nombre': 'Adhesivo transparente Éccole para calzado 9 g',
        'marca': 'Éccole',
        'modelo': 'Calzado 9 g',
        'precio': 6290,
        'contenido': '9.000',
        'unidad_contenido': 'g',
        'stock': 24,
        'descripcion': (
            'Adhesivo transparente tipo gel, flexible y de secado rápido, formulado para '
            'reparaciones localizadas de zapatos y zapatillas.'
        ),
        'uso_recomendado': (
            'Punteras, bordes, talones, suelas y capelladas de cuero, tela y ciertos '
            'plásticos de calzado. No destinar a inmersión continua en agua.'
        ),
        'superficies': ['cuero', 'tela', 'goma de calzado', 'plástico compatible'],
        'especificaciones': {
            'familia_adhesivo': 'adhesivo flexible para calzado',
            'consistencia': 'gel',
            'color': 'transparente',
            'tiempo_sujecion_segundos': 60,
            'resistencia_agua': 'Uso normal; no contacto continuo',
            'aplicacion_recomendada': 'Cubrir una superficie, unir de inmediato y presionar',
            'preparacion': 'Limpiar con alcohol y dejar seco, sin grasa ni polvo',
            'fuente_tecnica': 'https://www.sodimac.cl/sodimac-cl/articulo/110323479/adhesivo-transparente-eccole-9-gr/110323489',
        },
    },
    {
        'sku': 'SFI-ADH-POX-MET-14',
        'nombre': 'Adhesivo epóxico Poxipol metálico 10 minutos 14 ml',
        'marca': 'Poxipol',
        'modelo': 'Metálico 10 minutos',
        'precio': 6990,
        'contenido': '14.000',
        'unidad_contenido': 'ml',
        'stock': 22,
        'descripcion': (
            'Adhesivo epóxico bicomponente de alta resistencia para uniones y reparaciones '
            'durables. Endurece en 10 minutos y alcanza su resistencia máxima a las 24 horas.'
        ),
        'uso_recomendado': (
            'Unir o reparar metal, cemento, loza, madera, mármol, vidrio, hormigón, '
            'fibrocemento, cerámica, granito y porcelana.'
        ),
        'superficies': ['metal', 'cemento', 'loza', 'madera', 'mármol', 'vidrio', 'hormigón', 'fibrocemento', 'cerámica', 'granito', 'porcelana'],
        'especificaciones': {
            'familia_adhesivo': 'epóxico bicomponente',
            'color': 'metálico',
            'proporcion_mezcla': 'Partes iguales de componentes A y B',
            'tiempo_mezcla_minutos': 1,
            'endurecimiento_minutos': 10,
            'curado_maximo_horas': 24,
            'temperatura_maxima_c': 120,
            'resistencia_agua': True,
            'no_compatible': ['polietileno', 'polipropileno', 'PVC flexible', 'PTFE/Teflón'],
            'fuente_tecnica': 'https://www.akapol.com/wp-content/uploads/2023/10/Ficha_Tecnica_Poxipol_2023_retrabajo_21.pdf',
            'fuente_precio': 'https://www.sodimac.cl/sodimac-cl/articulo/110315048/adhesivo-soldadura-plastica-poxipol-14-ml/110315058',
        },
    },
    {
        'sku': 'SFI-ADH-POXIL-70',
        'nombre': 'Masilla epóxica Poxilina 10 minutos 70 g',
        'marca': 'Poxilina',
        'modelo': '10 minutos 70 g',
        'precio': 8490,
        'contenido': '70.000',
        'unidad_contenido': 'g',
        'stock': 20,
        'descripcion': (
            'Masilla epóxica de dos componentes que se corta, amasa y aplica para rellenar, '
            'restaurar y reconstruir piezas, incluida la reparación de caños.'
        ),
        'uso_recomendado': (
            'Reparaciones localizadas, relleno de faltantes y pinchaduras de caños. '
            'Confirmar material, presión, temperatura y aptitud sanitaria antes de usar.'
        ),
        'superficies': ['metal', 'hormigón', 'cerámica', 'madera', 'cañerías compatibles'],
        'especificaciones': {
            'familia_adhesivo': 'masilla epóxica bicomponente',
            'endurecimiento_minutos': 10,
            'aplicacion_recomendada': 'Cortar, amasar hasta homogeneizar y aplicar',
            'uso_bajo_agua': True,
            'advertencia': 'Una reparación de cañería no reemplaza la evaluación de un gasfíter',
            'fuente_tecnica': 'https://akapol.com/marcas/poxilina/',
            'fuente_precio': 'https://www.sodimac.cl/sodimac-cl/b/poxipol',
        },
    },
    {
        'sku': 'SFI-ADH-AGO-CON-118',
        'nombre': 'Adhesivo de contacto Agorex 1/32 galón',
        'marca': 'Agorex',
        'modelo': 'Contacto 1/32 galón',
        'precio': 5790,
        'contenido': '118.000',
        'unidad_contenido': 'ml',
        'stock': 26,
        'descripcion': (
            'Adhesivo de contacto de alta resistencia en formato pequeño para unir '
            'combinaciones compatibles de materiales en reparaciones y terminaciones.'
        ),
        'uso_recomendado': (
            'Pegado por contacto de madera, cuero, piedra y metal compatibles. Aplicar '
            'según la ficha del fabricante y trabajar con ventilación adecuada.'
        ),
        'superficies': ['madera', 'cuero', 'piedra', 'metal'],
        'especificaciones': {
            'familia_adhesivo': 'adhesivo de contacto',
            'aplicacion_recomendada': 'Aplicar en ambas superficies según instrucciones del envase',
            'seguridad': 'Producto con solventes; usar ventilación y evitar fuentes de ignición',
            'fuente_tecnica': 'https://www.henkel.cl/marcas-y-negocios/adhesive-technologies/agorex-591802',
            'fuente_precio': 'https://www.sodimac.cl/sodimac-cl/lista/CATG11042/Adhesivo-de-Contacto/',
        },
    },
    {
        'sku': 'SFI-ADH-PUL-MON-50',
        'nombre': 'Adhesivo de montaje El Pulpito 50 g',
        'marca': 'El Pulpito',
        'modelo': 'Montaje 50 g',
        'precio': 2990,
        'contenido': '50.000',
        'unidad_contenido': 'g',
        'stock': 28,
        'descripcion': (
            'Adhesivo sintético de montaje, blanco y pintable una vez seco, para '
            'decoración y pequeñas reparaciones en interior o exterior protegido.'
        ),
        'uso_recomendado': (
            'Montaje liviano de zócalos, molduras, cablecanal, cerámicas, cartelería y '
            'adornos sobre sustratos rígidos compatibles.'
        ),
        'superficies': ['ladrillo', 'madera', 'yeso-cartón', 'yeso', 'poliestireno expandido', 'vidrio', 'mármol', 'bronce'],
        'especificaciones': {
            'familia_adhesivo': 'adhesivo sintético de montaje',
            'color': 'blanco',
            'pintable': True,
            'curado_final_horas': 24,
            'ambiente': 'Interior y exterior protegido',
            'aplicacion_recomendada': 'Aplicar, posicionar y presionar según el peso del elemento',
            'fuente_tecnica': 'https://elpulpito.cl/',
            'fuente_precio': 'https://www.sodimac.cl/sodimac-cl/articulo/114481801/adhesivo-montaje-el-pulpito-50-gr/114481808',
        },
    },
)


def crear_productos(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    for registro in PRODUCTOS:
        Producto.objects.update_or_create(
            sku=registro['sku'],
            defaults={
                'nombre': registro['nombre'],
                'descripcion': registro['descripcion'],
                'precio': registro['precio'],
                'imagen': '',
                'stock': registro['stock'],
                'stock_minimo': 5,
                'categoria': 'Adhesivos',
                'marca': registro['marca'],
                'modelo': registro['modelo'],
                'ambiente_uso': 'interior_exterior',
                'superficies_compatibles': [],
                'activo': True,
                'unidad_venta': 'envase',
                'contenido': Decimal(registro['contenido']),
                'unidad_contenido': registro['unidad_contenido'],
                'tipo_calculo': 'ninguno',
                'rendimiento': None,
                'unidad_rendimiento': '',
                'porcentaje_desperdicio': Decimal('0.00'),
                'uso_recomendado': registro['uso_recomendado'],
                'especificaciones': {
                    **registro['especificaciones'],
                    'materiales_compatibles': registro['superficies'],
                    'cantidad_orientativa': (
                        'Depende del área, holgura, porosidad y geometría de la reparación; '
                        'confirmar consumo en la ficha o el envase antes de comprar.'
                    ),
                    'fecha_consulta_fuente': '2026-11-18',
                },
                'informacion_tecnica_verificada': True,
            },
        )


def eliminar_productos(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.filter(sku__in=[item['sku'] for item in PRODUCTOS]).delete()


class Migration(migrations.Migration):
    dependencies = [('productos', '0061_alternativas_economicas_piso_flotante')]

    operations = [migrations.RunPython(crear_productos, eliminar_productos)]
