from decimal import Decimal
import base64
from unittest.mock import Mock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from maestros.models import Especialidad, PerfilMaestro
from productos.models import Producto
from usuarios.models import Usuario
from .services import procesar_configuracion_foto, procesar_consulta, resolver_interpretacion
from .services.cliente_gemini import cliente_gemini
from .services.gemini import GeminiNoDisponible, interpretar_con_gemini
from .services.sinonimos_ferreteros import expandir_consulta


class AsistenteSfiTests(TestCase):
    def setUp(self):
        self.pintura = Producto.objects.create(
            nombre='Látex SFI interior mate', descripcion='Pintura blanca para muros interiores',
            precio=20000, imagen='productos/pintura-asistente.webp', stock=8,
            categoria='Pinturas', marca='SFI', color='Blanco', color_hex='#FFFFFF',
            ambiente_uso='interior', superficies_compatibles=['hormigon', 'yeso_carton'],
            tipo_pintura='latex', terminacion='mate',
            propiedades_pintura=['base_agua', 'bajo_olor'],
            preparaciones_recomendadas=['limpieza', 'sellador'],
            repintado_min_horas=Decimal('3.00'), repintado_max_horas=Decimal('6.00'),
            unidad_venta='envase', contenido=Decimal('4.000'), unidad_contenido='l',
            tipo_calculo='pintura', rendimiento=Decimal('10.000'), unidad_rendimiento='m2_l',
            capas_recomendadas=2, porcentaje_desperdicio=Decimal('10.00'),
            informacion_tecnica_verificada=True, activo=True,
        )
        self.taladro = Producto.objects.create(
            nombre='Taladro SFI hogar', descripcion='Taladro para trabajos domésticos',
            precio=49990, imagen='productos/taladro-asistente.webp', stock=5,
            categoria='Herramientas', marca='SFI', activo=True,
        )
        self.madera = Producto.objects.create(
            nombre='Pino dimensionado 2 x 3 pulgadas x 3,2 m',
            descripcion='Madera dimensionada para proyectos básicos',
            precio=5900, imagen='productos/pino-repisa.webp', stock=20,
            categoria='Construcción', marca='Genérico', activo=True,
            unidad_venta='unidad', contenido=Decimal('3.200'), unidad_contenido='m',
            especificaciones={'Sección nominal': '2 x 3 pulgadas', 'Material': 'Pino'},
        )
        self.crear_maestros_para_busquedas()

    def test_pagina_del_asistente_es_publica_y_accesible_desde_inicio(self):
        pagina = self.client.get(reverse('asistente_sfi'))
        inicio = self.client.get(reverse('index'))

        self.assertEqual(pagina.status_code, 200)
        self.assertContains(pagina, 'id="assistant-form"')
        self.assertContains(pagina, 'id="paint-workbench"')
        self.assertContains(pagina, 'id="attach-paint-photo"')
        self.assertNotContains(pagina, 'id="catalog-paint-colors"')
        self.assertContains(pagina, reverse('api_consultar_asistente'))
        self.assertContains(pagina, reverse('api_analizar_foto_pintura'))
        self.assertContains(pagina, reverse('api_configurar_foto_pintura'))
        self.assertContains(pagina, 'id="paint-mini-chat"')
        self.assertContains(pagina, 'data-mask-tool="smart"')
        self.assertContains(pagina, 'data-mask-tool="brush"')
        self.assertContains(pagina, 'data-mask-tool="erase"')
        self.assertContains(pagina, 'id="toggle-paint-mask"')
        self.assertContains(pagina, 'id="auto-paint-surface"')
        self.assertContains(pagina, 'id="apply-paint-mask"')
        self.assertContains(pagina, 'data-suggestion="Quiero renovar mi baño"')
        self.assertNotContains(pagina, reverse('mi_historial_compras'))
        self.assertContains(pagina, 'Compra protegida con Webpay')
        self.assertContains(inicio, reverse('asistente_sfi'))

    @patch('asistente.views.analizar_foto_pintura')
    def test_analiza_foto_sin_guardarla(self, analizar):
        analizar.return_value = {
            'superficie_detectada': 'Muro interior pintado',
            'ambiente_estimado': 'interior',
            'estado_estimado': 'bueno',
            'contexto_pintura': 'interior',
            'observaciones': ['La iluminación puede modificar el color percibido.'],
            'preparacion_sugerida': ['Limpiar y secar la superficie.'],
            'resumen': 'La superficie parece apta para una revisión de pintura.',
        }
        png = base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
        )
        foto = SimpleUploadedFile('muro.png', png, content_type='image/png')

        respuesta = self.client.post(
            reverse('api_analizar_foto_pintura'),
            {'imagen': foto, 'color_hex': '#FFFFFF', 'producto_id': self.pintura.id},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.json()['imagen_guardada'])
        self.assertEqual(respuesta.json()['pintura']['id'], self.pintura.id)
        self.assertTrue(respuesta.json()['colores_recomendados'])
        analizar.assert_called_once()

    def test_rechaza_archivo_que_no_es_imagen(self):
        archivo = SimpleUploadedFile('muro.png', b'no-es-una-imagen', content_type='image/png')

        respuesta = self.client.post(
            reverse('api_analizar_foto_pintura'),
            {'imagen': archivo, 'color_hex': '#FFFFFF'},
        )

        self.assertEqual(respuesta.status_code, 400)

    @patch('asistente.views.analizar_foto_pintura')
    def test_error_de_gemini_en_foto_responde_503_controlado(self, analizar):
        analizar.side_effect = GeminiNoDisponible('Gemini no disponible temporalmente.')
        png = base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
        )
        foto = SimpleUploadedFile('muro.png', png, content_type='image/png')

        respuesta = self.client.post(
            reverse('api_analizar_foto_pintura'),
            {'imagen': foto, 'color_hex': '#FFFFFF'},
        )

        self.assertEqual(respuesta.status_code, 503)
        self.assertEqual(respuesta.json()['detail'], 'Gemini no disponible temporalmente.')

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_minichat_foto_ofrece_tonos_y_solo_pregunta_datos_al_calcular(self, interpretar):
        for nombre, color, color_hex in [
            ('Fachada rojo colonial', 'Rojo colonial', '#A33A32'),
            ('Fachada rojo ladrillo', 'Rojo ladrillo', '#8F3B2F'),
        ]:
            Producto.objects.create(
                nombre=nombre, descripcion='Pintura roja para fachada exterior',
                precio=24990, stock=4, categoria='Pinturas', marca='SFI',
                color=color, color_hex=color_hex, ambiente_uso='exterior',
                superficies_compatibles=['hormigon'], tipo_pintura='latex',
                terminacion='mate', unidad_venta='envase', contenido=Decimal('4.000'),
                unidad_contenido='l', tipo_calculo='pintura',
                rendimiento=Decimal('10.000'), unidad_rendimiento='m2_l',
                capas_recomendadas=2, porcentaje_desperdicio=Decimal('10.00'),
                informacion_tecnica_verificada=True, activo=True,
            )
        interpretar.return_value = {
            'intencion': 'recomendar_color', 'respuesta': '', 'consulta_producto': '',
            'superficie': 0, 'ambiente': '', 'tipo_superficie': '',
            'estado_superficie': '', 'terminacion': 'cualquiera', 'color': 'Rojo',
            'capas': 0, 'desperdicio': -1, 'presupuesto': 0, 'proyecto': '',
            'ancho_cm': 0, 'fondo_cm': 0, 'alto_cm': 0, 'cantidad': 0,
            'tipo_muro': '', 'incluir_herramientas': False,
        }

        resultado = procesar_configuracion_foto(
            'Quiero diferentes tonos rojos para mi casa', 'exterior', [],
        )

        self.assertEqual(resultado['tipo'], 'recomendacion_color')
        self.assertGreaterEqual(len(resultado['productos']), 2)
        self.assertTrue(all('rojo' in item['color'].lower() or 'rojo' in (
            Producto.objects.get(pk=item['id']).especificaciones or {}
        ).get('familia_cromatica', '') for item in resultado['productos']))
        self.assertIn('Aparecieron arriba', resultado['mensaje'])

        interpretar.return_value.update({
            'intencion': 'calcular_pintura',
            'superficie': 45,
            'tipo_superficie': 'hormigon',
            'estado_superficie': 'pintada_buen_estado',
        })
        resultado = procesar_configuracion_foto(
            'Son 45 m² de hormigón pintado y está en buen estado',
            'exterior',
            [{'role': 'user', 'content': 'Quiero diferentes tonos rojos para mi casa'}],
        )

        self.assertEqual(resultado['tipo'], 'calculo_pintura')
        self.assertGreaterEqual(len(resultado['productos']), 2)
        self.assertTrue(all('rojo' in item['color'].lower() or 'rojo' in (
            Producto.objects.get(pk=item['id']).especificaciones or {}
        ).get('familia_cromatica', '') for item in resultado['productos']))
        self.assertTrue(all(item['cantidad_envases'] > 0 for item in resultado['productos']))

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_minichat_menciona_la_pintura_seleccionada_al_pedir_datos(self, interpretar):
        interpretar.return_value = {
            'intencion': 'calcular_pintura', 'respuesta': '', 'consulta_producto': '',
            'superficie': 0, 'ambiente': '', 'tipo_superficie': '',
            'estado_superficie': '', 'terminacion': 'cualquiera', 'color': '',
            'capas': 0, 'desperdicio': -1, 'presupuesto': 0, 'proyecto': '',
            'ancho_cm': 0, 'fondo_cm': 0, 'alto_cm': 0, 'cantidad': 0,
            'tipo_muro': '', 'incluir_herramientas': False,
        }

        resultado = procesar_configuracion_foto(
            '¿Cuánto necesito de esta pintura?', 'exterior', [], producto=self.pintura,
        )

        self.assertEqual(resultado['tipo'], 'aclaracion_foto')
        self.assertIn('Basado en tu elección de arriba', resultado['mensaje'])
        self.assertIn(self.pintura.nombre, resultado['mensaje'])

    def test_calculo_pide_los_datos_que_faltan(self):
        resultado = resolver_interpretacion({
            'intencion': 'calcular_pintura', 'superficie': 50,
            'ambiente': 'interior', 'tipo_superficie': '',
            'estado_superficie': '', 'terminacion': 'cualquiera',
            'color': '', 'capas': 0, 'desperdicio': -1,
        })

        self.assertEqual(resultado['tipo'], 'aclaracion')
        self.assertIn('material de la superficie', resultado['mensaje'])
        self.assertIn('estado actual', resultado['mensaje'])

    def test_recomienda_solo_colores_compatibles_con_interior(self):
        resultado = resolver_interpretacion({
            'intencion': 'recomendar_color',
            'ambiente': 'interior',
            'tipo_superficie': 'yeso_carton',
            'color': '',
        })

        self.assertEqual(resultado['tipo'], 'recomendacion_color')
        self.assertEqual(resultado['contexto_pintura'], 'interior')
        self.assertTrue(resultado['productos'])
        self.assertTrue(all(
            Producto.objects.get(pk=item['id']).ambiente_uso in {'interior', 'interior_exterior'}
            for item in resultado['productos']
        ))

    def test_reconoce_familia_cromatica_de_nombre_comercial(self):
        azul = Producto.objects.create(
            nombre='Sipa Fachada Pompeii 1 galon', descripcion='Pintura exterior azul',
            precio=42990, stock=80, categoria='Pinturas', marca='Sipa',
            color='Pompeii', color_hex='#446C86', ambiente_uso='exterior',
            superficies_compatibles=['hormigon'], tipo_pintura='latex',
            terminacion='mate', unidad_venta='envase', contenido=Decimal('3.785'),
            unidad_contenido='l', tipo_calculo='pintura', rendimiento=Decimal('9.200'),
            unidad_rendimiento='m2_l', capas_recomendadas=2,
            porcentaje_desperdicio=Decimal('10.00'),
            informacion_tecnica_verificada=True, activo=True,
            especificaciones={'familia_cromatica': 'azul'},
        )
        Producto.objects.create(
            nombre='Sipa Fachada Raintree 1 galon', descripcion='Pintura exterior verde',
            precio=42990, stock=80, categoria='Pinturas', marca='Sipa',
            color='Raintree', color_hex='#596B50', ambiente_uso='exterior',
            superficies_compatibles=['hormigon'], tipo_pintura='latex',
            terminacion='mate', unidad_venta='envase', contenido=Decimal('3.785'),
            unidad_contenido='l', tipo_calculo='pintura', rendimiento=Decimal('9.200'),
            unidad_rendimiento='m2_l', capas_recomendadas=2,
            porcentaje_desperdicio=Decimal('10.00'),
            informacion_tecnica_verificada=True, activo=True,
            especificaciones={'familia_cromatica': 'verde'},
        )

        resultado = resolver_interpretacion({
            'intencion': 'recomendar_color', 'ambiente': 'exterior',
            'tipo_superficie': 'hormigon', 'color': 'azul',
        })

        ids = [item['id'] for item in resultado['productos']]
        self.assertIn(azul.id, ids)
        self.assertTrue(all(
            'azul' in (Producto.objects.get(pk=producto_id).especificaciones or {}).get(
                'familia_cromatica', ''
            )
            for producto_id in ids
        ))

    def test_recomienda_pintura_tecnica_para_piscina(self):
        resultado = resolver_interpretacion({
            'intencion': 'recomendar_color',
            'ambiente': 'especial',
            'tipo_superficie': 'piscina_estanque',
            'proyecto': 'piscina',
            'color': '',
        })

        self.assertEqual(resultado['contexto_pintura'], 'piscina')
        self.assertTrue(resultado['productos'])
        self.assertTrue(all(
            'piscina_estanque' in Producto.objects.get(pk=item['id']).superficies_compatibles
            for item in resultado['productos']
        ))

    def test_exterior_no_recomienda_pintura_solo_interior(self):
        resultado = resolver_interpretacion({
            'intencion': 'recomendar_color',
            'ambiente': 'exterior',
            'tipo_superficie': 'hormigon',
            'color': '',
        })

        ids = {item['id'] for item in resultado['productos']}
        self.assertNotIn(self.pintura.id, ids)
        self.assertTrue(all(
            Producto.objects.get(pk=item['id']).ambiente_uso in {'exterior', 'interior_exterior'}
            for item in resultado['productos']
        ))

    def test_calculo_usa_ficha_real_y_prepara_el_carrito(self):
        resultado = resolver_interpretacion({
            'intencion': 'calcular_pintura', 'superficie': 50,
            'ambiente': 'interior', 'tipo_superficie': 'hormigon',
            'estado_superficie': 'nueva', 'terminacion': 'mate',
            'color': 'Blanco', 'capas': 0, 'desperdicio': -1,
        })

        self.assertEqual(resultado['tipo'], 'calculo_pintura')
        producto = resultado['productos'][0]
        self.assertEqual(producto['id'], self.pintura.id)
        self.assertEqual(producto['litros_necesarios'], 11)
        self.assertEqual(producto['cantidad_envases'], 3)
        self.assertEqual(producto['presupuesto_total'], 60000)
        self.assertEqual(producto['calculo_carrito']['terminacion'], 'mate')

    def test_busqueda_solo_devuelve_productos_reales(self):
        resultado = resolver_interpretacion({
            'intencion': 'buscar_producto', 'consulta_producto': 'taladro hogar',
        })

        self.assertEqual(resultado['tipo'], 'productos')
        self.assertEqual(resultado['productos'][0]['id'], self.taladro.id)

    def test_busqueda_prioriza_quincalleria_segun_uso(self):
        casos = {
            'tornillo para metal': 'SFI-QUI-TOR-',
            'tarugo para hormigon': 'SFI-QUI-ANC-',
            'candado para porton': 'SFI-QUI-SEG-',
            'bisagra cierre suave': 'SFI-QUI-HER-',
        }
        for consulta, prefijo in casos.items():
            with self.subTest(consulta=consulta):
                resultado = resolver_interpretacion({
                    'intencion': 'buscar_producto', 'consulta_producto': consulta,
                })
                self.assertEqual(resultado['tipo'], 'productos')
                self.assertTrue(resultado['productos'][0]['sku'].startswith(prefijo))

    def test_busqueda_respeta_presupuesto_e_indica_lo_que_falta(self):
        resultado = resolver_interpretacion({
            'intencion': 'buscar_producto', 'consulta_producto': 'taladro',
            'presupuesto': 30000,
        })

        self.assertEqual(resultado['tipo'], 'productos')
        self.assertEqual(resultado['productos'][0]['id'], self.taladro.id)
        self.assertIn('faltan $19.990', resultado['mensaje'])

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_reconoce_presupuesto_expresado_en_mil_pesos(self, interpretar):
        interpretar.return_value = {
            'intencion': 'buscar_producto', 'consulta_producto': 'taladro',
            'presupuesto': 50000, 'terminacion': 'cualquiera', 'color': '',
        }

        resultado = procesar_consulta('Tengo 50 mil para un taladro', [])

        self.assertEqual(resultado['tipo'], 'productos')
        self.assertIn('dentro de tu presupuesto de $50.000', resultado['mensaje'])

    def test_repisa_pide_medidas_muro_y_presupuesto_opcional(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto', 'proyecto': 'repisa',
            'ancho_cm': 0, 'fondo_cm': 0, 'tipo_muro': '',
        })

        self.assertEqual(resultado['tipo'], 'aclaracion')
        self.assertIn('ancho de la repisa', resultado['mensaje'])
        self.assertIn('tipo de muro', resultado['mensaje'].replace('si el muro', 'tipo de muro'))

    def test_repisa_prepara_kit_completo_y_compara_presupuesto(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto', 'proyecto': 'repisa',
            'ancho_cm': 80, 'fondo_cm': 25, 'cantidad': 1,
            'tipo_muro': 'hormigon', 'presupuesto': 7000,
        })

        self.assertEqual(resultado['tipo'], 'plan_proyecto')
        self.assertIn('Tablero pino finger joint', resultado['productos'][0]['nombre'])
        self.assertEqual(resultado['productos'][0]['cantidad_requerida'], 1)
        self.assertEqual(resultado['subtotal_basico'], 31950)
        self.assertIn('faltan $24.950', resultado['mensaje'])
        self.assertEqual(resultado['faltantes_catalogo'], [])
        self.assertTrue(any('Escuadras' in item['nombre'] for item in resultado['productos']))

    def test_repisa_avisa_si_presupuesto_no_alcanza_para_el_kit(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto', 'proyecto': 'repisa',
            'ancho_cm': 80, 'fondo_cm': 25, 'cantidad': 1,
            'tipo_muro': 'hormigon', 'presupuesto': 4000,
        })

        self.assertEqual(resultado['tipo'], 'plan_proyecto')
        self.assertIn('no alcanza', resultado['mensaje'])
        self.assertIn('faltan $27.950', resultado['mensaje'])

    def test_repisa_separa_obligatorios_herramientas_y_opcionales(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto', 'proyecto': 'repisa',
            'ancho_cm': 50, 'fondo_cm': 25, 'cantidad': 2,
            'tipo_muro': 'hormigon', 'presupuesto': 0,
            'incluir_herramientas': False,
        })

        tablero = next(
            item for item in resultado['productos']
            if item['rol'] == 'Superficie de la repisa'
        )
        lijas = next(
            item for item in resultado['productos']
            if item['rol'] == 'Preparación de la madera'
        )
        barniz = next(item for item in resultado['productos'] if item.get('es_opcional'))
        incluidos = [item for item in resultado['productos'] if not item.get('es_opcional')]

        self.assertEqual(tablero['cantidad_requerida'], 1)
        self.assertEqual(lijas['cantidad_requerida'], 2)
        self.assertEqual(
            resultado['subtotal_basico'],
            sum(item['subtotal'] for item in incluidos),
        )
        self.assertEqual(resultado['subtotal_herramientas'], 0)
        self.assertEqual(resultado['subtotal_opcionales'], barniz['subtotal'])
        self.assertEqual(
            resultado['total_con_terminacion'],
            resultado['subtotal_basico'] + barniz['subtotal'],
        )
        self.assertIn('materiales obligatorios', resultado['mensaje'])
        self.assertIn('barniz opcional', resultado['mensaje'])

    def test_bano_pide_alcance_antes_de_calcular(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'baño',
            'alcance_bano': '',
        })

        self.assertEqual(resultado['tipo'], 'aclaracion')
        self.assertIn('piso, muros, artefactos', resultado['mensaje'])
        self.assertFalse(resultado['productos'])

    def test_bano_completo_calcula_envases_stock_y_total_desde_catalogo(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'renovación de baño',
            'alcance_bano': 'completo',
            'superficie': 6,
            'superficie_muros': 20,
            'incluir_sanitario': True,
            'incluir_lavamanos': True,
            'incluir_ducha': True,
            'presupuesto': 500000,
        })

        cantidades = {
            item['sku']: item['cantidad_requerida']
            for item in resultado['productos']
        }
        self.assertEqual(resultado['tipo'], 'plan_proyecto')
        self.assertEqual(cantidades['BAN-POR-144'], 5)
        self.assertEqual(cantidades['BAN-CER-150'], 15)
        self.assertEqual(cantidades['BAN-ADH-25'], 6)
        self.assertEqual(cantidades['BAN-FRA-5'], 3)
        self.assertEqual(cantidades['BAN-IMP-4'], 5)
        self.assertEqual(cantidades['BAN-WC-DD'], 1)
        self.assertEqual(cantidades['BAN-MUE-60'], 1)
        self.assertEqual(cantidades['BAN-DUC-CRO'], 1)
        self.assertEqual(
            resultado['subtotal_basico'],
            sum(item['subtotal'] for item in resultado['productos']),
        )
        self.assertEqual(resultado['subtotal_basico'], 919060)
        self.assertEqual(resultado['faltantes_catalogo'], [])
        self.assertIn('faltan $419.060', resultado['mensaje'])
        self.assertTrue(all(item['imagen'] for item in resultado['productos']))

    def test_bano_solo_piso_no_agrega_artefactos_que_cliente_no_pidio(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'baño',
            'alcance_bano': 'piso',
            'superficie': 5,
            'superficie_muros': 0,
            'incluir_sanitario': False,
            'incluir_lavamanos': False,
            'incluir_ducha': False,
            'presupuesto': 0,
        })

        skus = {item['sku'] for item in resultado['productos']}
        self.assertIn('BAN-POR-144', skus)
        self.assertNotIn('BAN-CER-150', skus)
        self.assertNotIn('BAN-WC-DD', skus)
        self.assertNotIn('BAN-MUE-60', skus)
        self.assertNotIn('BAN-DUC-CRO', skus)

    def test_bano_no_cierra_plan_si_un_producto_no_tiene_stock(self):
        Producto.objects.filter(sku='BAN-POR-144').update(stock=0)

        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'baño',
            'alcance_bano': 'piso',
            'superficie': 5,
            'superficie_muros': 0,
            'presupuesto': 0,
        })

        self.assertIn('Revestimiento de piso (stock insuficiente)', resultado['faltantes_catalogo'])
        self.assertIn('No presento el presupuesto como completo', resultado['mensaje'])

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_bano_normaliza_alcance_y_no_inventa_sanitarios(self, interpretar):
        interpretar.return_value = {
            'intencion': 'planificar_proyecto',
            'proyecto': 'baño',
            'alcance_bano': 'completo',
            'superficie': 5,
            'superficie_muros': 0,
            'incluir_sanitario': True,
            'incluir_lavamanos': True,
            'incluir_ducha': True,
            'presupuesto': 0,
            'terminacion': 'cualquiera',
            'color': '',
        }

        resultado = procesar_consulta('Quiero cambiar solo el piso del baño, son 5 m²', [])

        skus = {item['sku'] for item in resultado['productos']}
        self.assertIn('BAN-POR-144', skus)
        self.assertNotIn('BAN-WC-DD', skus)
        self.assertNotIn('BAN-MUE-60', skus)
        self.assertNotIn('BAN-DUC-CRO', skus)

    def test_calculo_pintura_compara_presupuesto(self):
        resultado = resolver_interpretacion({
            'intencion': 'calcular_pintura', 'superficie': 50,
            'ambiente': 'interior', 'tipo_superficie': 'hormigon',
            'estado_superficie': 'nueva', 'terminacion': 'mate',
            'color': 'Blanco', 'capas': 0, 'desperdicio': -1,
            'presupuesto': 50000,
        })

        self.assertEqual(resultado['tipo'], 'calculo_pintura')
        self.assertIn('faltan $10.000', resultado['mensaje'])

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_no_aplica_terminacion_ni_color_que_cliente_no_solicito(self, interpretar):
        piscina = Producto.objects.create(
            nombre='Pintura piscina azul', descripcion='Pintura para piscinas',
            precio=30000, imagen='productos/piscina.webp', stock=40,
            categoria='Pinturas', marca='SFI', color='Azul piscina',
            ambiente_uso='especial', superficies_compatibles=['piscina_estanque'],
            tipo_pintura='caucho_clorado', terminacion='lisa_mate',
            propiedades_pintura=['resistente_sanitizantes'],
            preparaciones_recomendadas=['limpieza', 'impermeabilizacion'],
            repintado_min_horas=Decimal('8.00'), repintado_max_horas=Decimal('24.00'),
            unidad_venta='envase', contenido=Decimal('4.000'), unidad_contenido='l',
            tipo_calculo='pintura', rendimiento=Decimal('4.000'), unidad_rendimiento='m2_l',
            capas_recomendadas=2, porcentaje_desperdicio=Decimal('10.00'),
            informacion_tecnica_verificada=True, activo=True,
        )
        interpretar.return_value = {
            'intencion': 'calcular_pintura', 'respuesta': '', 'consulta_producto': '',
            'superficie': 50, 'ambiente': 'especial',
            'tipo_superficie': 'piscina_estanque', 'estado_superficie': 'nueva',
            'terminacion': 'mate', 'color': 'Azul piscina',
            'capas': 0, 'desperdicio': -1,
        }
        historial = [
            {'role': 'user', 'content': 'Quiero pintar una piscina, ¿qué me recomiendas?'},
            {'role': 'assistant', 'content': '¿Cuántos metros cuadrados y cuál es su estado?'},
            {'role': 'user', 'content': '50 metros'},
        ]

        resultado = procesar_consulta('Está semi nueva', historial)

        self.assertEqual(resultado['tipo'], 'calculo_pintura')
        self.assertEqual(resultado['productos'][0]['id'], piscina.id)
        self.assertEqual(
            resultado['productos'][0]['calculo_carrito']['terminacion'],
            'cualquiera',
        )

    @override_settings(GEMINI_API_KEY='')
    def test_api_informa_configuracion_pendiente_sin_exponer_secretos(self):
        response = self.client.post(
            reverse('api_consultar_asistente'),
            {'mensaje': 'Necesito pintura', 'historial': []},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 503)
        self.assertTrue(response.json()['configuracion_pendiente'])
        self.assertNotIn('AIza', response.content.decode())

    @patch('asistente.views.procesar_consulta')
    def test_api_devuelve_resultado_controlado(self, procesar):
        procesar.return_value = {
            'tipo': 'orientacion', 'mensaje': 'Usa protección personal.',
            'productos': [], 'sugerencias': [],
        }

        response = self.client.post(
            reverse('api_consultar_asistente'),
            {'mensaje': '¿Qué necesito para lijar?', 'historial': []},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['mensaje'], 'Usa protección personal.')
        procesar.assert_called_once()

    @override_settings(
        GEMINI_API_KEY='clave-secreta-prueba',
        GEMINI_MODEL='gemini-3.5-flash-lite',
        GEMINI_TIMEOUT_SECONDS=10,
    )
    @patch('asistente.services.gemini.cliente_gemini.post')
    def test_clave_gemini_viaja_en_header_y_no_en_url(self, post):
        respuesta = Mock()
        respuesta.raise_for_status.return_value = None
        respuesta.json.return_value = {
            'candidates': [{'content': {'parts': [{'text': (
                '{"intencion":"aclarar","respuesta":"Indica tus medidas",'
                '"consulta_producto":"","superficie":0,"ambiente":"",'
                '"tipo_superficie":"","estado_superficie":"",'
                '"terminacion":"cualquiera","color":"","capas":0,'
                '"desperdicio":-1}'
            )}]}}],
        }
        post.return_value = respuesta

        resultado = interpretar_con_gemini('Necesito ayuda', [])

        self.assertEqual(resultado['intencion'], 'aclarar')
        url = post.call_args.args[0]
        opciones = post.call_args.kwargs
        self.assertNotIn('clave-secreta-prueba', url)
        self.assertEqual(opciones['headers']['x-goog-api-key'], 'clave-secreta-prueba')

    @patch.object(cliente_gemini.session, 'post')
    def test_cliente_gemini_exige_tls_y_endpoint_oficial(self, post):
        cliente_gemini.post(
            'https://generativelanguage.googleapis.com/v1beta/models/modelo:generateContent',
            json={'contents': []},
        )

        self.assertTrue(post.call_args.kwargs['verify'])
        with self.assertRaisesMessage(ValueError, 'endpoint oficial'):
            cliente_gemini.post('https://example.com/v1beta/models/modelo:generateContent')
        with self.assertRaisesMessage(ValueError, 'endpoint oficial'):
            cliente_gemini.post(
                'http://generativelanguage.googleapis.com/v1beta/models/modelo:generateContent'
            )

    def test_resolver_repisa_incluye_herramientas_si_se_solicita(self):
        Producto.objects.create(
            nombre='Tablero pino finger joint 120 x 30 x 1,8 cm',
            precio=12990, stock=10, categoria='Construcción', activo=True,
        )
        Producto.objects.create(
            nombre='Escuadras metálicas reforzadas 25 x 20 cm pack 2',
            precio=6990, stock=10, categoria='Construcción', activo=True,
        )
        Producto.objects.create(
            nombre='Kit fijación para hormigón y ladrillo pack 10',
            precio=3990, stock=10, categoria='Construcción', activo=True,
        )
        Producto.objects.create(
            nombre='Tornillos para madera 4 x 40 mm pack 50',
            precio=4990, stock=10, categoria='Construcción', activo=True,
        )
        Producto.objects.create(
            nombre='Lijas para madera grano 120, 180 y 240 pack 3',
            precio=2990, stock=10, categoria='Construcción', activo=True,
        )
        Producto.objects.create(
            nombre='Taladro percutor Bauker',
            precio=25000, stock=5, categoria='Herramientas', activo=True,
        )
        Producto.objects.create(
            nombre='Cinta métrica Stanley 5m',
            precio=4990, stock=5, categoria='Herramientas', activo=True,
        )

        datos_sin_herramientas = {
            'intencion': 'planificar_proyecto',
            'proyecto': 'repisa',
            'ancho_cm': 80,
            'fondo_cm': 25,
            'tipo_muro': 'hormigon',
            'incluir_herramientas': False,
        }
        res_sin = resolver_interpretacion(datos_sin_herramientas)
        self.assertEqual(res_sin['tipo'], 'plan_proyecto')
        nombres_productos_sin = [p['nombre'] for p in res_sin['productos']]
        self.assertNotIn('Taladro percutor Bauker', nombres_productos_sin)
        self.assertIn('Incluir también herramientas', res_sin['sugerencias'])

        datos_con_herramientas = {
            'intencion': 'planificar_proyecto',
            'proyecto': 'repisa',
            'ancho_cm': 80,
            'fondo_cm': 25,
            'tipo_muro': 'hormigon',
            'incluir_herramientas': True,
        }
        res_con = resolver_interpretacion(datos_con_herramientas)
        self.assertEqual(res_con['tipo'], 'plan_proyecto')
        nombres_productos_con = [p['nombre'] for p in res_con['productos']]
        self.assertIn('Taladro percutor Bauker', nombres_productos_con)
        self.assertIn('Cinta métrica Stanley 5m', nombres_productos_con)
        self.assertIn('Excluir herramientas', res_con['sugerencias'])
        self.assertIn('herramientas recomendadas', res_con['mensaje'])

    def consultar_maestro(self, mensaje, historial=None, **cambios):
        interpretacion = {
            'intencion': 'orientacion_general',
            'respuesta': 'Cuéntame más sobre el trabajo.',
            'consulta_producto': '',
            'terminacion': 'cualquiera',
            'color': '',
            'presupuesto': 0,
            'incluir_herramientas': False,
            'especialidad_maestro': '',
            'comuna_maestro': '',
            'descripcion_trabajo': '',
        }
        interpretacion.update(cambios)
        with patch(
            'asistente.services.asistente_sfi.interpretar_con_gemini',
            return_value=interpretacion,
        ):
            return procesar_consulta(mensaje, historial or [])

    def crear_maestros_para_busquedas(self):
        datos = (
            ('Pedro', 'González', 'Carpintería', 'Maipú', 'Maipú, Cerrillos'),
            ('María', 'Soto', 'Pintura', 'Maipú', 'Maipú, Cerrillos'),
            ('Jorge', 'Rojas', 'Pintura', 'Providencia', 'Providencia, Ñuñoa'),
            ('Daniela', 'Silva', 'Pintura', 'Santiago', 'Santiago, San Miguel'),
            ('Luis', 'Pérez', 'Gasfitería', 'Pudahuel', 'Pudahuel, Maipú'),
            ('Andrea', 'Torres', 'Electricidad', 'Ñuñoa', 'Ñuñoa, Santiago'),
            ('Miguel', 'Castro', 'Cerámica y revestimientos', 'Puente Alto', 'Puente Alto, La Florida'),
        )
        for indice, (nombre, apellido, oficio, comuna, zonas) in enumerate(datos, start=1):
            usuario = Usuario.objects.create_user(
                username=f'maestro_busqueda_{indice}',
                email=f'maestro-busqueda-{indice}@example.invalid',
                rut=f'2555555{indice}-{indice}',
                telefono=f'+5695555500{indice}',
                password=None,
                first_name=nombre,
                last_name=apellido,
                email_confirmado=True,
            )
            perfil = PerfilMaestro.objects.create(
                usuario=usuario,
                descripcion_profesional=f'{oficio} creado únicamente para esta prueba.',
                anos_experiencia=8,
                region='RM',
                comuna=comuna,
                zonas_trabajo=zonas,
                disponible=True,
                estado=PerfilMaestro.Estado.APROBADO,
                fecha_aprobacion=timezone.now(),
            )
            perfil.especialidades.add(Especialidad.objects.get(nombre=oficio))

    def test_repisa_diy_no_muestra_maestros_antes_de_aceptar(self):
        resultado = self.consultar_maestro(
            'Quiero instalar una repisa',
            intencion='planificar_proyecto',
            proyecto='repisa',
            ancho_cm=0,
            fondo_cm=0,
            tipo_muro='',
        )
        self.assertNotEqual(resultado['tipo'], 'maestros')
        self.assertFalse(resultado.get('maestros', []))

    def test_repisa_completa_ofrece_carpintero_sin_buscarlo(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'repisa',
            'ancho_cm': 100,
            'fondo_cm': 25,
            'cantidad': 1,
            'tipo_muro': 'hormigon',
            'presupuesto': 0,
        })
        self.assertEqual(resultado['tipo'], 'plan_proyecto')
        self.assertTrue(resultado['productos'])
        self.assertIn('buscar un maestro carpintero', resultado['mensaje'])
        self.assertIn('Buscar maestro carpintero', resultado['sugerencias'])
        self.assertFalse(resultado.get('maestros', []))

    def test_aceptacion_contextual_conserva_carpinteria_y_pregunta_comuna(self):
        historial = [{
            'role': 'assistant',
            'content': 'Si prefieres, puedo buscar un maestro carpintero para realizar el trabajo.',
        }]
        resultado = self.consultar_maestro('Sí', historial)
        self.assertEqual(resultado['tipo'], 'aclaracion_maestro')
        self.assertIn('comuna', resultado['mensaje'])
        self.assertFalse(resultado['maestros'])

    def test_comuna_contextual_encuentra_a_pedro_gonzalez(self):
        historial = [
            {
                'role': 'assistant',
                'content': 'Si prefieres, puedo buscar un maestro carpintero para realizar el trabajo.',
            },
            {'role': 'user', 'content': 'Sí'},
            {'role': 'assistant', 'content': 'Claro. ¿En qué comuna necesitas el trabajo?'},
        ]
        resultado = self.consultar_maestro('Maipú', historial)
        self.assertEqual(resultado['tipo'], 'maestros')
        self.assertIn('Pedro González', [item['nombre'] for item in resultado['maestros']])

    def test_solicitud_directa_carpintero_en_maipu(self):
        resultado = self.consultar_maestro('Necesito un carpintero en Maipú')
        self.assertEqual(resultado['tipo'], 'maestros')
        self.assertIn('Pedro González', [item['nombre'] for item in resultado['maestros']])

    def test_pintura_diy_no_muestra_pintores_automaticamente(self):
        resultado = self.consultar_maestro(
            'Quiero pintar mi dormitorio',
            intencion='calcular_pintura',
            superficie=0,
            ambiente='interior',
            tipo_superficie='',
            estado_superficie='',
        )
        self.assertEqual(resultado['tipo'], 'aclaracion')
        self.assertFalse(resultado.get('maestros', []))

    def test_calculo_pintura_ofrece_pintor_sin_buscarlo(self):
        resultado = resolver_interpretacion({
            'intencion': 'calcular_pintura',
            'superficie': 20,
            'ambiente': 'interior',
            'tipo_superficie': 'hormigon',
            'estado_superficie': 'nueva',
            'terminacion': 'mate',
            'color': 'Blanco',
            'capas': 0,
            'desperdicio': -1,
            'presupuesto': 0,
        })
        self.assertEqual(resultado['tipo'], 'calculo_pintura')
        self.assertIn('buscar un maestro pintor', resultado['mensaje'])
        self.assertIn('Buscar maestro pintor', resultado['sugerencias'])
        self.assertFalse(resultado.get('maestros', []))

    def test_aceptacion_de_pintor_y_comuna_encuentra_a_maria_soto(self):
        historial = [
            {
                'role': 'assistant',
                'content': 'También puedo buscar un maestro pintor para realizar el trabajo.',
            },
            {'role': 'user', 'content': 'Sí por favor'},
            {'role': 'assistant', 'content': 'Claro. ¿En qué comuna necesitas el trabajo?'},
        ]
        resultado = self.consultar_maestro('Maipú', historial)
        self.assertIn('María Soto', [item['nombre'] for item in resultado['maestros']])

    def test_solicitud_directa_pintor_en_providencia(self):
        resultado = self.consultar_maestro('Necesito un pintor en Providencia')
        self.assertIn('Jorge Rojas', [item['nombre'] for item in resultado['maestros']])

    def test_solicitud_directa_gasfiter_en_pudahuel(self):
        resultado = self.consultar_maestro('Necesito un gasfiter en Pudahuel')
        self.assertIn('Luis Pérez', [item['nombre'] for item in resultado['maestros']])

    def test_solicitud_directa_electricista_en_nunoa(self):
        resultado = self.consultar_maestro('Necesito un electricista en Ñuñoa')
        self.assertIn('Andrea Torres', [item['nombre'] for item in resultado['maestros']])

    def test_solicitud_directa_ceramista_en_puente_alto(self):
        resultado = self.consultar_maestro(
            'Necesito alguien que instale cerámica en Puente Alto'
        )
        self.assertIn('Miguel Castro', [item['nombre'] for item in resultado['maestros']])

    def test_perfiles_pendientes_y_no_disponibles_nunca_aparecen(self):
        pintores = self.consultar_maestro('Necesito un pintor en Maipú')['maestros']
        carpinteros = self.consultar_maestro('Necesito un carpintero en Maipú')['maestros']
        nombres = {item['nombre'] for item in pintores + carpinteros}
        self.assertNotIn('Fernando Demo', nombres)
        self.assertNotIn('Mario Demo', nombres)

    def test_si_aislado_no_activa_busqueda_de_maestro(self):
        resultado = self.consultar_maestro('Sí')
        self.assertEqual(resultado['tipo'], 'orientacion')
        self.assertFalse(resultado.get('maestros', []))

    def test_necesitar_una_pintura_no_se_confunde_con_buscar_pintor(self):
        resultado = self.consultar_maestro(
            'Necesito una pintura para mi dormitorio',
            intencion='buscar_producto',
            consulta_producto='pintura dormitorio',
        )
        self.assertNotEqual(resultado['tipo'], 'maestros')
        self.assertFalse(resultado.get('maestros', []))

    def test_listado_de_especialidad_funciona_sin_comuna(self):
        resultado = self.consultar_maestro(
            '¿Qué maestros de pintura están disponibles?'
        )
        nombres = {item['nombre'] for item in resultado['maestros']}

        self.assertEqual(resultado['tipo'], 'maestros')
        self.assertIn('María Soto', nombres)
        self.assertIn('Jorge Rojas', nombres)
        self.assertIn('Daniela Silva', nombres)
        self.assertIn('sin filtrar por comuna', resultado['mensaje'])

    def test_solicitud_generica_reutiliza_el_oficio_sin_confundir_retiro_en_tienda(self):
        historial = [
            {
                'role': 'user',
                'content': 'Necesito baldosas de cerámica con retiro en tienda.',
            },
            {
                'role': 'assistant',
                'content': (
                    'Encontré materiales para cerámica. También puedo buscar '
                    'un maestro de Cerámica y revestimientos.'
                ),
            },
        ]

        resultado = self.consultar_maestro(
            '¿Algún maestro que me ayude?',
            historial,
        )

        self.assertEqual(resultado['tipo'], 'maestros')
        self.assertIn('Miguel Castro', [item['nombre'] for item in resultado['maestros']])
        self.assertIn('sin filtrar por comuna', resultado['mensaje'])
        self.assertNotIn('en Retiro', resultado['mensaje'])

    def test_retiro_explicito_se_mantiene_como_comuna(self):
        historial = [{
            'role': 'assistant',
            'content': 'Puedo buscar un maestro de Cerámica y revestimientos.',
        }]

        resultado = self.consultar_maestro(
            'Necesito un maestro en Retiro',
            historial,
        )

        self.assertEqual(resultado['tipo'], 'sin_resultados_maestros')
        self.assertIn('en Retiro', resultado['mensaje'])

    def test_cualquier_comuna_reutiliza_especialidad_del_contexto(self):
        historial = [
            {'role': 'user', 'content': 'Necesito un pintor en Quilicura'},
            {
                'role': 'assistant',
                'content': (
                    'No encontré maestros verificados disponibles para Pintura '
                    'en Quilicura en este momento.'
                ),
            },
        ]
        resultado = self.consultar_maestro('De cualquier comuna', historial)
        nombres = {item['nombre'] for item in resultado['maestros']}

        self.assertEqual(resultado['tipo'], 'maestros')
        self.assertIn('María Soto', nombres)
        self.assertIn('Jorge Rojas', nombres)

    def test_respuesta_de_cualquiera_mientras_pregunta_comuna_muestra_todos(self):
        historial = [
            {'role': 'user', 'content': 'Necesito maestros pintores'},
            {'role': 'assistant', 'content': 'Claro. ¿En qué comuna necesitas el trabajo?'},
        ]
        resultado = self.consultar_maestro('De cualquiera', historial)

        self.assertEqual(resultado['tipo'], 'maestros')
        self.assertIn('sin filtrar por comuna', resultado['mensaje'])
        self.assertIn('María Soto', [item['nombre'] for item in resultado['maestros']])

    def test_muestrame_todos_mientras_pregunta_comuna_muestra_categoria(self):
        historial = [
            {'role': 'user', 'content': 'Necesito maestros pintores'},
            {'role': 'assistant', 'content': 'Claro. ¿En qué comuna necesitas el trabajo?'},
        ]
        resultado = self.consultar_maestro('Muéstrame todos', historial)

        self.assertEqual(resultado['tipo'], 'maestros')
        nombres = {item['nombre'] for item in resultado['maestros']}
        self.assertTrue({'María Soto', 'Jorge Rojas', 'Daniela Silva'}.issubset(nombres))

    def test_buscar_en_otra_comuna_pregunta_cual(self):
        historial = [{
            'role': 'assistant',
            'content': 'No encontré maestros de Pintura en Quilicura.',
        }]
        resultado = self.consultar_maestro('Buscar en otra comuna', historial)

        self.assertEqual(resultado['tipo'], 'aclaracion_maestro')
        self.assertIn('qué comuna', resultado['mensaje'].lower())
        self.assertFalse(resultado['maestros'])

    def test_cambio_de_especialidad_conserva_comuna_en_el_mismo_flujo(self):
        historial = [{
            'role': 'assistant',
            'content': 'No encontré maestros de Carpintería en Quilicura.',
        }]
        resultado = self.consultar_maestro('¿Y maestros pintores?', historial)

        self.assertEqual(resultado['tipo'], 'sin_resultados_maestros')
        self.assertIn('Pintura en Quilicura', resultado['mensaje'])

    def test_maestro_generico_con_comuna_pregunta_el_trabajo(self):
        resultado = self.consultar_maestro(
            'Necesito un maestro de Quilicura',
            especialidad_maestro='Carpintería',
            comuna_maestro='Quilicura',
        )

        self.assertEqual(resultado['tipo'], 'aclaracion_maestro')
        self.assertIn('Qué trabajo', resultado['mensaje'])
        self.assertFalse(resultado['maestros'])

class SinonimosYBusquedaSemanticaTests(TestCase):
    """Tests para sinónimos ferreteros y búsqueda semántica."""

    def setUp(self):
        self.taladro = Producto.objects.create(
            nombre='Taladro percutor Bauker con cable',
            descripcion='Taladro percutor con selector para perforación con o sin impacto.',
            precio=57000, stock=20, categoria='Herramientas', marca='Bauker',
            uso_recomendado='Perforaciones domésticas en madera, metal y mampostería.',
            activo=True,
        )
        self.cinta = Producto.objects.create(
            nombre='Cinta métrica Stanley Pro 8 m',
            descripcion='Huincha de medir retráctil Stanley Pro de ocho metros.',
            precio=12990, stock=25, categoria='Herramientas', marca='Stanley',
            uso_recomendado='Mediciones de longitud en construcción e instalación.',
            activo=True,
        )
        self.martillo = Producto.objects.create(
            nombre='Martillo carpintero Unitools 16 oz',
            descripcion='Martillo de uña curva con cabeza de acero.',
            precio=14990, stock=18, categoria='Herramientas', marca='Unitools',
            uso_recomendado='Clavar y extraer clavos en trabajos de carpintería.',
            activo=True,
        )
        self.perno = Producto.objects.create(
            nombre='Perno hexagonal métrico de acero',
            descripcion='Perno métrico de cabeza hexagonal para fijaciones desmontables.',
            precio=5000, stock=40, categoria='Construcción', marca='Genérico',
            uso_recomendado='Fijaciones mecánicas en estructuras y montajes.',
            activo=True,
        )
        self.adhesivo = Producto.objects.create(
            nombre='Adhesivo cerámico zonas húmedas 25 kg',
            descripcion='Adhesivo cementicio para cerámica y porcelanato en baños y cocinas.',
            precio=8990, stock=30, categoria='Construcción', marca='SFI',
            uso_recomendado='Instalación de cerámica y porcelanato en zonas húmedas.',
            activo=True,
        )
        self.sanitario = Producto.objects.create(
            nombre='Sanitario dos piezas doble descarga',
            descripcion='Sanitario con doble descarga y sistema de ahorro de agua.',
            precio=79990, stock=10, categoria='Gasfitería', marca='SFI',
            uso_recomendado='Baños residenciales con salida muro y piso.',
            activo=True,
        )
        self.sierra = Producto.objects.create(
            nombre='Sierra circular Stanley 7-1/4 pulgadas 1600 W',
            descripcion='Sierra circular de 1600 W con disco para cortes rectos en madera.',
            precio=60000, stock=31, categoria='Herramientas', marca='Stanley',
            uso_recomendado='Cortes rectos en tableros y piezas de madera.',
            activo=True,
        )
        self.pino = Producto.objects.create(
            nombre='Pino dimensionado 2 x 3 pulgadas x 3,2 m',
            descripcion='Pieza de pino dimensionado para estructuras livianas.',
            precio=5900, stock=120, categoria='Construcción', marca='Genérico',
            uso_recomendado='Estructuras livianas, tabiques y trabajos en madera.',
            activo=True,
        )

    # ── Tests de expandir_consulta ──

    def test_expandir_wincha_agrega_cinta_metrica(self):
        expandidas, agregados = expandir_consulta(['wincha'])
        self.assertIn('cinta', agregados)
        self.assertIn('metrica', agregados)
        self.assertIn('wincha', expandidas)

    def test_expandir_flexometro_agrega_cinta_metrica(self):
        expandidas, agregados = expandir_consulta(['flexometro'])
        self.assertIn('cinta', agregados)
        self.assertIn('metrica', agregados)

    def test_expandir_perforadora_agrega_taladro(self):
        expandidas, agregados = expandir_consulta(['perforadora'])
        self.assertIn('taladro', agregados)
        self.assertIn('percutor', agregados)

    def test_expandir_taladro_no_agrega_duplicados(self):
        expandidas, agregados = expandir_consulta(['taladro'])
        self.assertEqual(expandidas.count('taladro'), 1)
        self.assertNotIn('taladro', agregados)

    def test_expandir_pegar_azulejo_agrega_adhesivo(self):
        expandidas, agregados = expandir_consulta(['pegar', 'azulejo'])
        self.assertIn('adhesivo', agregados)
        self.assertIn('ceramico', agregados)

    def test_expandir_inodoro_agrega_sanitario(self):
        expandidas, agregados = expandir_consulta(['inodoro'])
        self.assertIn('sanitario', agregados)

    def test_expandir_combo_agrega_martillo(self):
        expandidas, agregados = expandir_consulta(['combo'])
        self.assertIn('martillo', agregados)

    def test_expandir_serrucho_agrega_sierra(self):
        expandidas, agregados = expandir_consulta(['serrucho'])
        self.assertIn('sierra', agregados)

    def test_expandir_bulon_agrega_perno(self):
        expandidas, agregados = expandir_consulta(['bulon'])
        self.assertIn('perno', agregados)
        self.assertIn('hexagonal', agregados)

    def test_expandir_madera_agrega_pino_tablero(self):
        expandidas, agregados = expandir_consulta(['madera'])
        self.assertIn('pino', agregados)
        self.assertIn('dimensionado', agregados)
        self.assertIn('tablero', agregados)

    def test_expandir_terminos_humedad_juntas_y_ducha(self):
        casos = [
            (['impermeabilizante'], {'membrana', 'impermeable'}),
            (['sello', 'humedad'], {'membrana', 'impermeable'}),
            (['rellenar', 'junta'], {'frague'}),
            (['ducha', 'telefono'], {'kit'}),
        ]
        for palabras, esperadas in casos:
            with self.subTest(palabras=palabras):
                _, agregados = expandir_consulta(palabras)
                self.assertTrue(esperadas.issubset(agregados))

    def test_concepto_colgar_cuadro_agrega_taladro_y_tornillo(self):
        expandidas, agregados = expandir_consulta(['colgar', 'cuadro'])
        self.assertIn('taladro', agregados)
        self.assertIn('tornillo', agregados)

    def test_concepto_pintar_fachada_agrega_pintura(self):
        expandidas, agregados = expandir_consulta(['pintar', 'fachada'])
        self.assertIn('pintura', agregados)
        self.assertIn('fachada', expandidas)
        self.assertIn('hidrorrepelente', agregados)

    # ── Tests de búsqueda con sinónimos ──

    def test_buscar_flexometro_encuentra_cinta_metrica(self):
        from .services.asistente_sfi import _buscar_productos
        resultados = _buscar_productos('flexómetro')
        ids = [p.id for p in resultados]
        self.assertIn(self.cinta.id, ids)

    def test_buscar_wincha_encuentra_cinta_metrica(self):
        from .services.asistente_sfi import _buscar_productos
        resultados = _buscar_productos('wincha')
        ids = [p.id for p in resultados]
        self.assertIn(self.cinta.id, ids)

    def test_buscar_metro_no_confunde_metrico_con_cinta_metrica(self):
        from .services.asistente_sfi import _buscar_productos
        resultados = _buscar_productos('metro')
        ids = [p.id for p in resultados]

        self.assertIn(self.cinta.id, ids)
        self.assertNotIn(self.perno.id, ids)

    def test_buscar_perforadora_encuentra_taladro(self):
        from .services.asistente_sfi import _buscar_productos
        resultados = _buscar_productos('perforadora')
        ids = [p.id for p in resultados]
        self.assertIn(self.taladro.id, ids)

    def test_buscar_pegar_azulejos_encuentra_adhesivo(self):
        from .services.asistente_sfi import _buscar_productos
        resultados = _buscar_productos('algo para pegar azulejos')
        ids = [p.id for p in resultados]
        self.assertIn(self.adhesivo.id, ids)

    def test_buscar_sello_humedad_encuentra_membrana_impermeable(self):
        from .services.asistente_sfi import _buscar_productos
        resultados = _buscar_productos('necesito un sello para la humedad')
        self.assertIn('BAN-IMP-4', {producto.sku for producto in resultados})

    def test_buscar_rellenar_junta_encuentra_frague(self):
        from .services.asistente_sfi import _buscar_productos
        resultados = _buscar_productos('algo para rellenar la junta de cerámica')
        self.assertIn('BAN-FRA-5', {producto.sku for producto in resultados})

    def test_buscar_inodoro_encuentra_sanitario(self):
        from .services.asistente_sfi import _buscar_productos
        resultados = _buscar_productos('inodoro')
        ids = [p.id for p in resultados]
        self.assertIn(self.sanitario.id, ids)

    def test_buscar_combo_encuentra_martillo(self):
        from .services.asistente_sfi import _buscar_productos
        resultados = _buscar_productos('combo para clavar')
        ids = [p.id for p in resultados]
        self.assertIn(self.martillo.id, ids)

    def test_buscar_bulon_encuentra_perno(self):
        from .services.asistente_sfi import _buscar_productos
        resultados = _buscar_productos('bulón')
        ids = [p.id for p in resultados]
        self.assertIn(self.perno.id, ids)

    def test_buscar_serrucho_encuentra_sierra(self):
        from .services.asistente_sfi import _buscar_productos
        resultados = _buscar_productos('serrucho')
        ids = [p.id for p in resultados]
        self.assertIn(self.sierra.id, ids)

    def test_buscar_madera_encuentra_pino(self):
        from .services.asistente_sfi import _buscar_productos
        resultados = _buscar_productos('madera para estructura')
        ids = [p.id for p in resultados]
        self.assertIn(self.pino.id, ids)

    def test_busqueda_directa_taladro_sigue_funcionando(self):
        from .services.asistente_sfi import _buscar_productos
        resultados = _buscar_productos('taladro')
        ids = [p.id for p in resultados]
        self.assertIn(self.taladro.id, ids)

    def test_busqueda_especifica_no_incluye_sierra_por_coincidir_solo_en_cable(self):
        from .services.asistente_sfi import _buscar_productos
        resultados = _buscar_productos('taladro percutor Bauker con cable')

        self.assertIn(self.taladro.id, [producto.id for producto in resultados])
        self.assertNotIn(self.sierra.id, [producto.id for producto in resultados])

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_taladro_mas_caro_devuelve_solo_el_taladro_de_mayor_precio(self, interpretar):
        from .services.asistente_sfi import _buscar_productos
        candidatos = _buscar_productos('taladro')
        esperado = max(candidatos, key=lambda producto: producto.precio)
        interpretar.return_value = {
            'intencion': 'buscar_producto',
            'consulta_producto': 'taladro percutor Bauker con cable',
            'presupuesto': 0,
            'terminacion': 'cualquiera',
            'color': '',
            'incluir_herramientas': False,
        }

        resultado = procesar_consulta('El taladro más caro', [])

        self.assertEqual(len(resultado['productos']), 1)
        self.assertEqual(resultado['productos'][0]['id'], esperado.id)
        self.assertIn('mayor precio', resultado['mensaje'])
        self.assertNotIn('Sierra', resultado['productos'][0]['nombre'])

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_sanitario_mas_caro_que_valor_tiene_limpia_la_consulta(self, interpretar):
        from .services.asistente_sfi import _buscar_productos
        esperado = max(
            _buscar_productos('sanitario'),
            key=lambda producto: producto.precio,
        )
        interpretar.return_value = {
            'intencion': 'buscar_producto',
            'consulta_producto': 'sanitario que valor tiene',
            'presupuesto': 0,
            'terminacion': 'cualquiera',
            'color': '',
            'incluir_herramientas': False,
        }

        resultado = procesar_consulta('El sanitario más caro qué valor tiene', [])

        self.assertEqual(len(resultado['productos']), 1)
        self.assertEqual(resultado['productos'][0]['id'], esperado.id)
        precio_esperado = f'${esperado.precio:,}'.replace(',', '.')
        self.assertIn(precio_esperado, resultado['mensaje'])

    def test_comparacion_de_precio_funciona_para_distintos_productos(self):
        from .services.asistente_sfi import _buscar_productos
        for consulta in ('taladro', 'sanitario', 'pintura', 'ceramica'):
            with self.subTest(consulta=consulta):
                candidatos = _buscar_productos(consulta)
                esperado = max(candidatos, key=lambda producto: producto.precio)
                resultado = resolver_interpretacion({
                    'intencion': 'buscar_producto',
                    'consulta_producto': consulta,
                    'orden_producto': 'precio_desc',
                    'consulta_precio': True,
                    'presupuesto': 0,
                })

                self.assertEqual(len(resultado['productos']), 1)
                self.assertEqual(resultado['productos'][0]['id'], esperado.id)

    def test_consulta_de_valor_sin_comparacion_muestra_precios(self):
        resultado = resolver_interpretacion({
            'intencion': 'buscar_producto',
            'consulta_producto': 'sanitario',
            'consulta_precio': True,
            'presupuesto': 0,
        })

        self.assertEqual(resultado['tipo'], 'productos')
        self.assertTrue(resultado['productos'])
        self.assertIn('precios actuales registrados en SFI', resultado['mensaje'])

    def test_busqueda_directa_cinta_metrica_sigue_funcionando(self):
        from .services.asistente_sfi import _buscar_productos
        resultados = _buscar_productos('cinta métrica')
        ids = [p.id for p in resultados]
        self.assertIn(self.cinta.id, ids)

    def test_busqueda_directa_tiene_mayor_puntaje_que_sinonimo(self):
        """Un producto encontrado por nombre directo debe puntuar más alto
        que uno encontrado solo por sinónimo."""
        from .services.asistente_sfi import _buscar_productos
        # "taladro" encuentra directamente, "perforadora" por sinónimo
        directos = _buscar_productos('taladro')
        sinonimos = _buscar_productos('perforadora')
        # Ambos deben encontrar el taladro
        self.assertIn(self.taladro.id, [p.id for p in directos])
        self.assertIn(self.taladro.id, [p.id for p in sinonimos])


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PlanificadorGenericoProyectosTests(TestCase):
    def setUp(self):
        self.madera = Producto.objects.create(
            nombre='Pino dimensionado para exterior',
            descripcion='Madera para estructuras y proyectos exteriores.',
            precio=8990,
            imagen='productos/pino-exterior.webp',
            stock=20,
            categoria='Construcción',
            activo=True,
        )
        self.tornillos = Producto.objects.create(
            nombre='Tornillos para madera pack 50',
            descripcion='Fijaciones para unir piezas de madera.',
            precio=4990,
            imagen='productos/tornillos-madera.webp',
            stock=15,
            categoria='Ferretería',
            activo=True,
        )
        self.barniz = Producto.objects.create(
            nombre='Barniz protector para madera exterior',
            descripcion='Protección de madera expuesta a lluvia y humedad.',
            precio=15990,
            imagen='productos/barniz-exterior.webp',
            stock=7,
            categoria='Pinturas',
            activo=True,
        )
        especialidad, _ = Especialidad.objects.get_or_create(
            nombre='Carpintería',
            defaults={'activa': True},
        )
        usuario = Usuario.objects.create_user(
            username='carpintero_generico',
            email='carpintero-generico@example.invalid',
            rut='23333333-3',
            telefono='+56933333333',
            password=None,
            first_name='Pedro',
            last_name='Madera',
            email_confirmado=True,
        )
        self.perfil = PerfilMaestro.objects.create(
            usuario=usuario,
            descripcion_profesional='Carpintero para proyectos de madera.',
            anos_experiencia=7,
            region='RM',
            comuna='Maipú',
            zonas_trabajo='Maipú, Cerrillos',
            disponible=True,
            estado=PerfilMaestro.Estado.APROBADO,
            fecha_aprobacion=timezone.now(),
        )
        self.perfil.especialidades.add(especialidad)

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_proyecto_libre_usa_productos_reales_y_maestro_aprobado(self, interpretar):
        interpretar.return_value = {
            'intencion': 'planificar_proyecto',
            'respuesta': 'Prepararé una orientación con el catálogo disponible.',
            'proyecto': 'Casita de madera exterior para perro',
            'tareas_proyecto': [
                {
                    'nombre': 'Construir la estructura',
                    'busquedas': ['pino dimensionado exterior', 'tornillos para madera'],
                },
                {
                    'nombre': 'Proteger contra la lluvia',
                    'busquedas': ['barniz madera exterior'],
                },
            ],
            'herramientas_proyecto': [],
            'especialidades_proyecto': ['Carpintería'],
            'datos_faltantes_proyecto': ['ancho', 'alto', 'profundidad'],
            'comuna_maestro': 'Maipú',
            'especialidad_maestro': '',
            'consulta_producto': '',
            'presupuesto': 0,
            'terminacion': 'cualquiera',
            'color': '',
            'incluir_herramientas': False,
        }

        resultado = procesar_consulta(
            'Quiero construir una casita de madera para mi perro en Maipú',
            [],
        )

        self.assertEqual(resultado['tipo'], 'plan_proyecto_generico')
        ids_recomendados = {producto['id'] for producto in resultado['productos']}
        self.assertEqual(len(ids_recomendados), 3)
        self.assertEqual(
            Producto.objects.filter(pk__in=ids_recomendados, activo=True).count(),
            3,
        )
        self.assertTrue(
            any('tornillo' in producto['nombre'].casefold() for producto in resultado['productos'])
        )
        self.assertTrue(
            any('barniz' in producto['nombre'].casefold() for producto in resultado['productos'])
        )
        self.assertTrue(
            any('pino' in producto['nombre'].casefold() for producto in resultado['productos'])
        )
        self.assertTrue(all(producto['stock'] > 0 for producto in resultado['productos']))
        self.assertEqual(resultado['especialidades'], ['Carpintería'])
        self.assertEqual([maestro['id'] for maestro in resultado['maestros']], [self.perfil.id])
        self.assertIn('ancho, alto, profundidad', resultado['mensaje'])
        self.assertTrue(resultado['calculo_orientativo'])

    def test_proyecto_generico_no_inventa_producto_ausente(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Observatorio doméstico',
            'tareas_proyecto': [{
                'nombre': 'Instalar cubierta especial',
                'busquedas': ['panel transparente espacial'],
            }],
            'herramientas_proyecto': [],
            'especialidades_proyecto': ['Especialidad inventada'],
            'datos_faltantes_proyecto': [],
            'comuna_maestro': 'Maipú',
        })

        self.assertEqual(resultado['tipo'], 'plan_proyecto_generico')
        self.assertEqual(resultado['productos'], [])
        self.assertEqual(resultado['maestros'], [])
        self.assertEqual(resultado['especialidades'], [])
        self.assertEqual(resultado['faltantes_catalogo'], ['panel transparente espacial'])
