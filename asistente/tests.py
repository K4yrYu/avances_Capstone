from decimal import Decimal
import base64
from unittest.mock import Mock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from productos.models import Producto
from .services import procesar_consulta, resolver_interpretacion
from .services.gemini import interpretar_con_gemini


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
    @patch('asistente.services.gemini.requests.post')
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
