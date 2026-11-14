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
from .serializers import ConsultaAsistenteSerializer
from .services.cliente_gemini import cliente_gemini
from .services.gemini import GeminiNoDisponible, _instrucciones, interpretar_con_gemini
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
        self.assertContains(pagina, 'id="read-conversation"')
        self.assertContains(pagina, 'aria-label="Leer conversación completa"')
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
        self.assertIn('falta disponibilidad', resultado['mensaje'])

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

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_cambiar_lavamanos_usa_flujo_sanitario_y_no_recomienda_candado(self, interpretar):
        candado = Producto.objects.create(
            nombre='Candado de bronce 40 mm con llaves',
            descripcion='Candado con dos llaves para seguridad.',
            precio=7790, imagen='productos/candado-test.webp', stock=20,
            categoria='Ferretería', marca='SFI', sku='TEST-CANDADO-LAVAMANOS',
        )
        interpretar.return_value = {
            'intencion': 'planificar_proyecto',
            'proyecto': 'Cambio de lavamanos',
            'tareas_proyecto': [{
                'nombre': 'Desmontaje de lavamanos antiguo',
                'busquedas': ['llaves'],
            }],
            'herramientas_proyecto': ['destornillador'],
            'especialidades_proyecto': ['Gasfitería'],
            'datos_faltantes_proyecto': [],
            'alcance_bano': '', 'superficie': 0, 'superficie_muros': 0,
            'incluir_sanitario': False, 'incluir_lavamanos': False,
            'incluir_ducha': False, 'presupuesto': 0,
            'terminacion': 'cualquiera', 'color': '',
            'incluir_herramientas': False,
        }

        resultado = procesar_consulta('Quiero cambiar mi lavamanos', [])

        ids = {item['id'] for item in resultado['productos']}
        skus = {item['sku'] for item in resultado['productos']}
        self.assertEqual(resultado['tipo'], 'plan_proyecto')
        self.assertNotIn(candado.pk, ids)
        self.assertIn('BAN-MUE-60', skus)
        self.assertIn('BAN-GRI-LV', skus)
        self.assertIn('BAN-KIT-LV', skus)
        self.assertNotIn('BAN-WC-DD', skus)
        self.assertNotIn('BAN-DUC-CRO', skus)
        self.assertIn('con un presupuesto estimado de $', resultado['mensaje'])
        self.assertNotIn('stock registrado', resultado['mensaje'])
        self.assertIn('en nuestro catálogo', resultado['mensaje'])
        self.assertIn('La estimación no incluye mano de obra', resultado['mensaje'])

        resultado_con_total = procesar_consulta(
            '¿Cuánto cuesta todo para cambiar mi lavamanos?', []
        )
        self.assertIn('con un presupuesto estimado de $', resultado_con_total['mensaje'])

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

    def test_mencion_previa_de_maestros_no_convierte_producto_en_profesional(self):
        pintura_roja = Producto.objects.create(
            nombre='Pintura látex roja interior',
            descripcion='Pintura roja para muros interiores',
            precio=22990,
            stock=6,
            categoria='Pinturas',
            marca='SFI',
            color='Rojo',
            activo=True,
        )
        historial = [
            {'role': 'user', 'content': 'Hola, necesito una ducha'},
            {
                'role': 'assistant',
                'content': (
                    'Encontré productos para la ducha. Para las conexiones conviene '
                    'un gasfíter y para revestimientos un maestro ceramista.'
                ),
            },
        ]

        resultado = self.consultar_maestro(
            'Necesito pintura roja',
            historial,
            intencion='buscar_maestro',
            respuesta='Puedo buscar profesionales de Pintura.',
            especialidad_maestro='Pintura',
        )

        self.assertEqual(resultado['tipo'], 'productos')
        self.assertFalse(resultado.get('maestros', []))
        self.assertIn(pintura_roja.id, [item['id'] for item in resultado['productos']])

    def test_consulta_de_producto_cierra_un_flujo_anterior_de_maestros(self):
        pintura_roja = Producto.objects.create(
            nombre='Esmalte rojo para metal',
            descripcion='Pintura roja de terminación brillante',
            precio=18990,
            stock=4,
            categoria='Pinturas',
            marca='SFI',
            color='Rojo',
            activo=True,
        )
        historial = [
            {'role': 'user', 'content': 'Necesito un maestro carpintero en Quilicura'},
            {
                'role': 'assistant',
                'content': 'No encontré maestros de Carpintería en Quilicura.',
            },
        ]

        resultado = self.consultar_maestro(
            'Necesito pintura roja',
            historial,
            intencion='buscar_maestro',
            especialidad_maestro='Pintura',
        )

        self.assertEqual(resultado['tipo'], 'productos')
        self.assertFalse(resultado.get('maestros', []))
        self.assertIn(pintura_roja.id, [item['id'] for item in resultado['productos']])

    def test_listado_de_especialidad_funciona_sin_comuna(self):
        resultado = self.consultar_maestro(
            '¿Qué maestros de pintura están disponibles?'
        )
        nombres = {item['nombre'] for item in resultado['maestros']}

        self.assertEqual(resultado['tipo'], 'maestros')
        self.assertIn('María Soto', nombres)
        self.assertIn('Jorge Rojas', nombres)
        self.assertIn('Daniela Silva', nombres)
        self.assertIn('maestros pintores disponibles', resultado['mensaje'])

    def test_muestrame_maestros_carpinteros_conserva_la_especialidad(self):
        historial = [{
            'role': 'assistant',
            'content': (
                'Para este proyecto, la especialidad principal es Techumbre. '
                'También puede intervenir un especialista en Carpintería.'
            ),
        }]

        resultado = self.consultar_maestro(
            'Muéstrame los maestros carpinteros',
            historial,
        )

        self.assertEqual(resultado['tipo'], 'maestros')
        self.assertIn('Pedro González', [item['nombre'] for item in resultado['maestros']])
        self.assertIn('carpintero disponible', resultado['mensaje'])

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

        self.assertEqual(resultado['tipo'], 'aclaracion_maestro')
        self.assertIn('buscar por comuna', resultado['mensaje'].lower())
        self.assertFalse(resultado['maestros'])

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
        self.assertIn('maestros pintores disponibles', resultado['mensaje'])
        self.assertIn('María Soto', [item['nombre'] for item in resultado['maestros']])

    def test_elegir_busqueda_por_comuna_pregunta_la_ubicacion(self):
        historial = [
            {'role': 'user', 'content': 'Necesito un gasfíter'},
            {
                'role': 'assistant',
                'content': (
                    'Puedo buscar profesionales de Gasfitería. '
                    '¿Prefieres buscar por comuna o ver todos los disponibles?'
                ),
            },
        ]

        resultado = self.consultar_maestro('Buscar por comuna', historial)

        self.assertEqual(resultado['tipo'], 'aclaracion_maestro')
        self.assertIn('qué comuna', resultado['mensaje'].lower())
        self.assertEqual(resultado['sugerencias'], ['Maipú', 'Santiago', 'Providencia'])

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

    def test_corrige_error_tipografico_solo_cuando_es_inequivoco(self):
        from .services.sinonimos_ferreteros import corregir_terminos

        self.assertEqual(corregir_terminos(['flesometro']), ['flexometro'])
        self.assertEqual(corregir_terminos(['pituto']), ['pituto'])

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

    def test_buscar_sanitario_no_mezcla_kit_de_lavamanos(self):
        from .services.asistente_sfi import _buscar_productos
        kit_lavamanos = Producto.objects.create(
            nombre='Kit conexión lavamanos con sifón y desagüe',
            descripcion='Kit para completar la instalación de un lavamanos.',
            precio=15990,
            stock=5,
            categoria='Gasfitería',
            marca='SFI',
            activo=True,
        )

        resultados = _buscar_productos(
            'Sanitario dos piezas doble descarga con kit de instalación'
        )
        ids = [producto.id for producto in resultados]

        self.assertIn(self.sanitario.id, ids)
        self.assertNotIn(kit_lavamanos.id, ids)

    def test_buscar_pintura_roja_excluye_otros_colores_y_aclara_respuesta(self):
        from .services.asistente_sfi import _buscar_productos
        pintura_roja = Producto.objects.create(
            nombre='Látex interior rojo colonial',
            descripcion='Pintura para muros interiores.',
            precio=22990,
            stock=5,
            categoria='Pinturas',
            marca='SFI',
            color='Rojo Colonial',
            activo=True,
        )
        pintura_blanca = Producto.objects.create(
            nombre='Látex interior blanco invierno',
            descripcion='Pintura para muros interiores.',
            precio=21990,
            stock=5,
            categoria='Pinturas',
            marca='SFI',
            color='Blanco Invierno',
            activo=True,
        )

        resultados = _buscar_productos('quiero pintura roja')
        ids = [producto.id for producto in resultados]
        respuesta = resolver_interpretacion({
            'intencion': 'buscar_producto',
            'consulta_producto': 'pintura roja',
            'presupuesto': 0,
        })

        self.assertIn(pintura_roja.id, ids)
        self.assertNotIn(pintura_blanca.id, ids)
        self.assertIn('pinturas disponibles en color rojo', respuesta['mensaje'])

    def test_buscar_pinturas_para_piscina_excluye_pinturas_genericas(self):
        pintura_piscina = Producto.objects.create(
            nombre='Pintura para piscina azul',
            descripcion='Revestimiento de caucho clorado para piscinas.',
            precio=44990,
            stock=5,
            categoria='Pinturas',
            marca='SFI',
            color='Azul piscina',
            ambiente_uso='especial',
            superficies_compatibles=['piscina_estanque'],
            tipo_pintura='caucho_clorado',
            activo=True,
        )
        pintura_interior = Producto.objects.create(
            nombre='Látex blanco interior',
            descripcion='Pintura para dormitorios y salas de estar.',
            precio=18990,
            stock=8,
            categoria='Pinturas',
            marca='SFI',
            color='Blanco',
            ambiente_uso='interior',
            superficies_compatibles=['hormigon', 'yeso_carton'],
            tipo_pintura='latex',
            activo=True,
        )

        resultado = resolver_interpretacion({
            'intencion': 'buscar_producto',
            'consulta_producto': 'muéstrame las pinturas para piscinas',
            'presupuesto': 0,
        })
        ids = [producto['id'] for producto in resultado['productos']]

        self.assertIn(pintura_piscina.id, ids)
        self.assertNotIn(pintura_interior.id, ids)
        self.assertIn('para piscina', resultado['mensaje'])

    def test_buscar_combo_no_sustituye_por_martillo_carpintero(self):
        from .services.asistente_sfi import _buscar_productos
        resultados = _buscar_productos('combo para clavar')
        ids = [p.id for p in resultados]
        self.assertNotIn(self.martillo.id, ids)

    def test_buscar_mazo_no_inventa_un_producto_relacionado(self):
        resultado = resolver_interpretacion({
            'intencion': 'buscar_producto',
            'consulta_producto': 'mazo',
            'presupuesto': 0,
        })

        self.assertEqual(resultado['tipo'], 'sin_resultados')
        self.assertFalse(resultado['productos'])
        self.assertIn('No encontré mazos activos', resultado['mensaje'])

    def test_buscar_bulon_encuentra_perno(self):
        from .services.asistente_sfi import _buscar_productos
        resultados = _buscar_productos('bulón')
        ids = [p.id for p in resultados]
        self.assertIn(self.perno.id, ids)

    def test_buscar_serrucho_no_sustituye_por_sierra_circular(self):
        from .services.asistente_sfi import _buscar_productos
        resultados = _buscar_productos('serrucho')
        ids = [p.id for p in resultados]
        self.assertNotIn(self.sierra.id, ids)

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

    def test_buscar_error_tipografico_encuentra_producto_real(self):
        from .services.asistente_sfi import _buscar_productos
        resultados = _buscar_productos('taladroo Baukr')

        self.assertIn(self.taladro.id, [producto.id for producto in resultados])

    def test_flexometro_con_error_no_muestra_perno_metrico(self):
        from .services.asistente_sfi import _buscar_productos
        resultados = _buscar_productos('flesometro')

        ids = [producto.id for producto in resultados]
        self.assertIn(self.cinta.id, ids)
        self.assertNotIn(self.perno.id, ids)

    def test_busqueda_kit_ducha_no_muestra_productos_de_bano_irrelevantes(self):
        kit = Producto.objects.create(
            nombre='Kit ducha cromado', descripcion='Conjunto para ducha',
            precio=24990, imagen='productos/kit-ducha.webp', stock=8,
            categoria='Baño', marca='SFI', sku='BAN-DUC-TEST',
        )
        sanitario = Producto.objects.create(
            nombre='Sanitario dos piezas', descripcion='Artefacto para baño',
            precio=89990, imagen='productos/sanitario.webp', stock=5,
            categoria='Baño', marca='SFI', sku='BAN-SAN-TEST',
        )

        resultado = resolver_interpretacion({
            'intencion': 'buscar_producto', 'consulta_producto': 'kit de ducha',
            'presupuesto': 0,
        })

        ids = [producto['id'] for producto in resultado['productos']]
        self.assertIn(kit.pk, ids)
        self.assertNotIn(sanitario.pk, ids)

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_comparacion_contextual_se_limita_a_productos_mostrados(self, interpretar):
        alternativa = Producto.objects.create(
            nombre='Taladro profesional premium', descripcion='Herramienta de alto valor',
            precio=99990, imagen='productos/taladro-premium.webp', stock=4,
            categoria='Herramientas', marca='SFI', sku='HER-TAL-PREMIUM',
        )
        interpretar.return_value = {
            'intencion': 'buscar_producto', 'consulta_producto': '',
            'presupuesto': 0, 'terminacion': 'cualquiera', 'color': '',
            'incluir_herramientas': False,
        }

        resultado = procesar_consulta(
            '¿Cuál es el más barato de esos?', [],
            [alternativa.pk, self.taladro.pk],
        )

        self.assertEqual(len(resultado['productos']), 1)
        self.assertEqual(resultado['productos'][0]['id'], self.taladro.pk)

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_referencia_ambigua_pide_posicion_del_producto(self, interpretar):
        interpretar.return_value = {
            'intencion': 'buscar_producto', 'consulta_producto': '',
            'presupuesto': 0, 'terminacion': 'cualquiera', 'color': '',
            'incluir_herramientas': False,
        }

        resultado = procesar_consulta(
            '¿Cuánto cuesta ese?', [], [self.taladro.pk, self.pino.pk],
        )

        self.assertEqual(resultado['tipo'], 'aclaracion')
        self.assertIn('cuál de los productos', resultado['mensaje'])

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

    def test_busqueda_por_marca_y_presupuesto_no_rompe_el_producto(self):
        from .services.asistente_sfi import _buscar_productos
        resultados = _buscar_productos('taladro Bauker bajo 60 lucas')

        self.assertEqual([producto.id for producto in resultados], [self.taladro.id])

    def test_presupuesto_coloqial_se_extrae_sin_confiar_en_gemini(self):
        from .services.asistente_sfi import _presupuesto_desde_texto

        self.assertEqual(_presupuesto_desde_texto('Taladro Bosch bajo 30 lucas'), 30000)

    def test_busqueda_por_medida_no_mezcla_otro_formato(self):
        cinta_corta = Producto.objects.create(
            nombre='Cinta métrica Stanley Pro 5 m',
            descripcion='Huincha retráctil de cinco metros.',
            precio=9990, stock=12, categoria='Herramientas', marca='Stanley',
            activo=True,
        )
        from .services.asistente_sfi import _buscar_productos
        resultados = _buscar_productos('cinta métrica 8 m')

        ids = [producto.id for producto in resultados]
        self.assertIn(self.cinta.id, ids)
        self.assertNotIn(cinta_corta.id, ids)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PlanificadorGenericoProyectosTests(TestCase):
    def test_instrucciones_exigen_lenguaje_natural_y_prudente_para_todos(self):
        instrucciones = _instrucciones()

        self.assertIn('cualquier proyecto del cliente', instrucciones)
        self.assertIn('español de Chile natural', instrucciones)
        self.assertIn('No afirmes que un producto evita', instrucciones)
        self.assertIn('Distingue materiales, herramientas y complementos', instrucciones)
        self.assertIn('asesor de proyectos', instrucciones)
        self.assertIn('propuesta_directa', instrucciones)
        self.assertIn('antes que preguntar', instrucciones)
        self.assertIn('La ausencia de un producto limita solamente', instrucciones)
        self.assertIn('No rechaces, cierres ni declares', instrucciones)

    def test_preguntas_de_puerta_explican_como_medir_el_vano(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Cambio de puerta',
            'tareas_proyecto': [{
                'nombre': 'Puerta y marco',
                'busquedas': ['puerta interior MDF'],
            }],
            'datos_faltantes_proyecto': [
                'La puerta es interior o exterior',
                'Cuáles son las medidas del vano (alto y ancho)',
            ],
        })

        self.assertEqual(resultado['tipo'], 'aclaracion_proyecto')
        self.assertIn('80 × 200 cm', resultado['mensaje'])
        self.assertIn('usa la medida menor', resultado['mensaje'])
        self.assertIn('solo la hoja o también el marco', resultado['mensaje'])
        self.assertNotIn('3 × 4 metros', resultado['mensaje'])

    def test_preguntas_de_mueble_usan_tres_dimensiones_en_centimetros(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Construcción de mueble para cocina',
            'tareas_proyecto': [{
                'nombre': 'Fabricación',
                'busquedas': ['plancha melamina blanca 18 mm'],
            }],
            'datos_faltantes_proyecto': ['Medidas disponibles para el mueble'],
        })

        self.assertIn('ancho × alto × fondo', resultado['mensaje'])
        self.assertIn('120 × 80 × 35 cm', resultado['mensaje'])
        self.assertNotIn('3 × 4 metros', resultado['mensaje'])

    def test_historial_acepta_respuesta_guiada_mayor_a_700_caracteres(self):
        serializer = ConsultaAsistenteSerializer(data={
            'mensaje': '3 x 4 y hormigón',
            'historial': [{
                'role': 'assistant',
                'content': 'Cuestionario guiado. ' + ('Detalle técnico. ' * 80),
            }],
        })

        self.assertTrue(serializer.is_valid(), serializer.errors)

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

    def test_preguntas_de_piso_guian_al_cliente_si_desconoce_los_datos(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Cambio de piso flotante',
            'tareas_proyecto': [{
                'nombre': 'Instalación de piso',
                'busquedas': ['piso laminado 8 mm'],
            }],
            'datos_faltantes_proyecto': [
                'Qué tipo de piso deseas instalar',
                'Cuál es el material de la superficie actual',
                'Cuál es el estado actual del piso',
            ],
        })

        self.assertEqual(resultado['tipo'], 'aclaracion_proyecto')
        self.assertEqual(resultado['productos'], [])
        self.assertIn('1. TIPO DE PISO', resultado['mensaje'])
        self.assertIn('2. BASE ACTUAL', resultado['mensaje'])
        self.assertIn('3. ESTADO DE LA BASE', resultado['mensaje'])
        self.assertIn('No lo sé: indica en qué habitación', resultado['mensaje'])
        self.assertIn('Hormigón: superficie gris', resultado['mensaje'])
        self.assertIn('Bueno: está firme, seca y nivelada', resultado['mensaje'])

    def test_preguntas_genericas_explican_como_responder_o_decir_no_se(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Construir una terraza exterior',
            'tareas_proyecto': [{
                'nombre': 'Revestimiento',
                'busquedas': ['baldosa exterior antideslizante'],
            }],
            'datos_faltantes_proyecto': [
                'Ancho y largo de la terraza',
                'Material de la base actual',
                'Estado de la superficie',
                'Exposición a lluvia o sol',
            ],
        })

        self.assertEqual(resultado['tipo'], 'aclaracion_proyecto')
        self.assertEqual(resultado['productos'], [])
        self.assertIn('3 × 4 metros', resultado['mensaje'])
        self.assertIn('hormigón, madera/OSB, metal, cerámica', resultado['mensaje'])
        self.assertIn('Bueno: firme, seco, nivelado', resultado['mensaje'])
        self.assertIn('lluvia o sol directo', resultado['mensaje'])
        self.assertGreaterEqual(resultado['mensaje'].count('No lo sé'), 4)

    def test_proyecto_estandar_entrega_materiales_sin_exigir_medidas(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Construcción de quincho estándar con cubierta de policarbonato',
            '_proyecto_estandar': True,
            'tareas_proyecto': [
                {'nombre': 'Albañilería', 'busquedas': ['ladrillo fiscal'], 'usos_materiales': [
                    {'busqueda': 'ladrillo fiscal', 'uso': 'Construir los elementos de albañilería del quincho.'},
                ]},
                {'nombre': 'Unión', 'busquedas': ['mortero pega ladrillos'], 'usos_materiales': [
                    {'busqueda': 'mortero pega ladrillos', 'uso': 'Unir los ladrillos de la albañilería.'},
                ]},
                {'nombre': 'Cubierta', 'busquedas': ['policarbonato alveolar 6 mm'], 'usos_materiales': [
                    {'busqueda': 'policarbonato alveolar 6 mm', 'uso': 'Formar la cubierta superior del quincho.'},
                ]},
            ],
            'datos_faltantes_proyecto': [
                'Ancho y fondo del quincho',
                'Material de la estructura',
            ],
        })

        self.assertEqual(resultado['tipo'], 'plan_proyecto_generico')
        self.assertTrue(resultado['productos'])
        self.assertIn('PROPUESTA ESTÁNDAR PARA TU PROYECTO', resultado['mensaje'])
        self.assertIn('PRODUCTOS POR ETAPA', resultado['mensaje'])
        self.assertIn('Construir los elementos de albañilería', resultado['mensaje'])
        self.assertIn('Son una estim', resultado['mensaje'])
        self.assertNotIn('ANTES DE RECOMENDAR PRODUCTOS', resultado['mensaje'])
        self.assertTrue(all(
            producto['recomendacion_orientativa']
            for producto in resultado['productos']
        ))
        self.assertTrue(all(
            producto.get('uso_en_proyecto')
            for producto in resultado['productos']
        ))

    def test_gemini_puede_orientar_con_propuesta_estandar_sin_bloquearse(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'modo_orientacion': 'propuesta_estandar',
            'proyecto': 'Cobertizo de madera orientativo',
            'tareas_proyecto': [{
                'nombre': 'Estructura base',
                'busquedas': ['pino dimensionado para exterior'],
                'usos_materiales': [
                    'Se utiliza como referencia para formar la estructura de madera.',
                ],
                'bases_calculo': ['referencial'],
            }],
            'datos_faltantes_proyecto': ['medidas definitivas del cobertizo'],
            'herramientas_proyecto': [],
            'especialidades_proyecto': [],
        })

        self.assertEqual(resultado['tipo'], 'plan_proyecto_generico')
        self.assertEqual(resultado['modo_orientacion'], 'propuesta_estandar')
        self.assertTrue(resultado['productos'])
        self.assertIn('PROPUESTA EST', resultado['mensaje'])

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_pregunta_por_que_conserva_productos_y_no_regenera_plan(self, interpretar):
        resultado = procesar_consulta(
            '¿Por qué estos materiales y no otros?',
            [{
                'role': 'assistant',
                'content': 'Preparé una propuesta estándar para tu cobertizo.',
            }],
            [self.madera.id, self.tornillos.id],
        )

        interpretar.assert_not_called()
        self.assertEqual(resultado['tipo'], 'explicacion_proyecto')
        self.assertEqual(resultado['productos'], [])
        self.assertIn(self.madera.nombre, resultado['mensaje'])
        self.assertIn(self.tornillos.nombre, resultado['mensaje'])
        self.assertIn('No son las únicas alternativas', resultado['mensaje'])

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_comparacion_indica_si_no_existe_producto_mas_barato(self, interpretar):
        exclusivo = Producto.objects.create(
            nombre='Conector estructural exclusivo modelo ZXQ',
            descripcion='Conector específico para una prueba de compatibilidad.',
            precio=18990,
            stock=8,
            categoria='Ferretería',
            activo=True,
        )

        resultado = procesar_consulta(
            'Muéstrame alternativas más económicas',
            [],
            [exclusivo.id],
        )

        interpretar.assert_not_called()
        self.assertEqual(resultado['tipo'], 'comparacion_economica')
        self.assertEqual(resultado['productos'], [])
        self.assertIn(
            'no encontré una alternativa compatible más barata',
            resultado['mensaje'],
        )

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_comparacion_muestra_alternativa_real_mas_barata(self, interpretar):
        economico = Producto.objects.create(
            nombre='Taladro percutor 500 W básico',
            descripcion='Taladro con percusión.',
            precio=19990,
            stock=8,
            categoria='Herramientas',
            activo=True,
        )
        costoso = Producto.objects.create(
            nombre='Taladro percutor 500 W premium',
            descripcion='Taladro con percusión.',
            precio=39990,
            stock=8,
            categoria='Herramientas',
            activo=True,
        )

        resultado = procesar_consulta(
            '¿Hay uno más barato?',
            [],
            [costoso.id],
        )

        interpretar.assert_not_called()
        self.assertEqual(resultado['tipo'], 'comparacion_economica')
        self.assertEqual(resultado['productos'][0]['id'], economico.id)
        self.assertIn('$20.000', resultado['mensaje'])

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_boton_ver_alternativas_no_reconstruye_proyecto(self, interpretar):
        resultado = procesar_consulta(
            'Ver alternativas de productos',
            [],
            [self.madera.id, self.tornillos.id],
        )

        interpretar.assert_not_called()
        self.assertEqual(resultado['tipo'], 'seguimiento_proyecto')
        self.assertEqual(resultado['productos'], [])
        self.assertIn('sin modificar el resto del proyecto', resultado['mensaje'])

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_boton_ajustar_no_reconstruye_proyecto(self, interpretar):
        resultado = procesar_consulta(
            'Ajustar el proyecto',
            [],
            [self.madera.id, self.tornillos.id],
        )

        interpretar.assert_not_called()
        self.assertEqual(resultado['tipo'], 'seguimiento_proyecto')
        self.assertEqual(resultado['productos'], [])
        self.assertIn('Mantendré todo lo demás', resultado['mensaje'])
        self.assertIn('Quiero cambiar las medidas', resultado['sugerencias'])

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_pregunta_tipo_maestro_usa_proyecto_y_no_tarjeta_ambigua(self, interpretar):
        cubierta = Producto.objects.create(
            nombre='Plancha zinc acanalado para techumbre',
            descripcion='Cubierta para techo.',
            precio=15990,
            stock=12,
            categoria='Construcción',
            activo=True,
        )

        resultado = procesar_consulta(
            '¿Qué tipo de maestro necesito para este proyecto?',
            [],
            [self.madera.id, cubierta.id],
        )

        interpretar.assert_not_called()
        self.assertEqual(resultado['tipo'], 'seguimiento_proyecto')
        self.assertIn('especialidad principal es Techumbre', resultado['mensaje'])
        self.assertIn('Carpintería', resultado['mensaje'])
        self.assertNotIn('A cuál de los productos', resultado['mensaje'])
        self.assertIn('Buscar maestro de Techumbre', resultado['sugerencias'])

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_frases_naturales_sobre_maestro_conservan_el_proyecto(self, interpretar):
        cubierta = Producto.objects.create(
            nombre='Plancha zinc para cobertizo',
            descripcion='Cubierta para una estructura exterior de madera.',
            precio=15990,
            stock=12,
            categoria='Construcción',
            activo=True,
        )
        historial = [{
            'role': 'assistant',
            'content': '¿A cuál de los productos mostrados te refieres?',
        }]

        for consulta in (
            '¿Qué maestro realiza este trabajo?',
            'Neceisto un maestro para este trabajo',
            '¿Qué profesional me recomiendas para esta obra?',
            'Necesito alguien que haga este proyecto',
            'Busco alguien para esta pega',
        ):
            with self.subTest(consulta=consulta):
                resultado = procesar_consulta(
                    consulta,
                    historial,
                    [self.madera.id, cubierta.id],
                )

                self.assertEqual(resultado['tipo'], 'seguimiento_proyecto')
                self.assertIn('especialidad principal es Techumbre', resultado['mensaje'])
                self.assertIn('Carpintería', resultado['mensaje'])
                self.assertNotIn('A cuál de los productos', resultado['mensaje'])

        interpretar.assert_not_called()

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_quincho_informa_todas_las_especialidades_relevantes(self, interpretar):
        ladrillo = Producto.objects.create(
            nombre='Ladrillo refractario para quincho prueba',
            descripcion='Material para zona de fuego y albañilería.',
            precio=1890,
            stock=100,
            categoria='Construcción',
            activo=True,
        )
        teja = Producto.objects.create(
            nombre='Teja para cubierta de quincho prueba',
            descripcion='Cubierta para techumbre.',
            precio=34990,
            stock=20,
            categoria='Construcción',
            activo=True,
        )
        pino = Producto.objects.create(
            nombre='Pino estructural para quincho prueba',
            descripcion='Madera para pilares y vigas.',
            precio=8990,
            stock=30,
            categoria='Construcción',
            activo=True,
        )

        resultado = procesar_consulta(
            '¿Qué maestros necesito para este trabajo?',
            [],
            [ladrillo.id, teja.id, pino.id],
        )

        interpretar.assert_not_called()
        self.assertEqual(resultado['tipo'], 'seguimiento_proyecto')
        self.assertIn('especialidad principal es Albañilería', resultado['mensaje'])
        self.assertIn('Techumbre', resultado['mensaje'])
        self.assertIn('Carpintería', resultado['mensaje'])
        self.assertIn('Buscar maestro de Albañilería', resultado['sugerencias'])

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_pedir_herramientas_usa_el_proyecto_y_no_pregunta_por_tarjeta(self, interpretar):
        policarbonato = Producto.objects.create(
            nombre='Policarbonato alveolar 6 mm prueba',
            descripcion='Cubierta liviana para techumbre.',
            precio=32990,
            stock=12,
            categoria='Construcción',
            activo=True,
        )
        cinta = Producto.objects.create(
            nombre='Cinta métrica 8 m prueba',
            descripcion='Herramienta de medición.',
            precio=12990,
            stock=8,
            categoria='Herramientas',
            activo=True,
        )
        taladro = Producto.objects.create(
            nombre='Taladro percutor con selector prueba',
            descripcion='Permite perforar con o sin impacto.',
            precio=29990,
            stock=6,
            categoria='Herramientas',
            activo=True,
        )
        sierra = Producto.objects.create(
            nombre='Sierra circular solo para madera prueba',
            descripcion='Cortes en madera.',
            precio=60000,
            stock=5,
            categoria='Herramientas',
            activo=True,
        )

        for consulta in ('¿Qué herramientas son necesarias?', '¿Con qué hago esta pega?'):
            with self.subTest(consulta=consulta):
                resultado = procesar_consulta(
                    consulta,
                    [{'role': 'assistant', 'content': '¿A cuál producto te refieres?'}],
                    [policarbonato.id],
                )

                self.assertEqual(resultado['tipo'], 'seguimiento_herramientas')
                ids = {producto['id'] for producto in resultado['productos']}
                self.assertEqual(ids, {cinta.id, taladro.id})
                self.assertNotIn(sierra.id, ids)
                self.assertNotIn('A cuál de los productos', resultado['mensaje'])
                self.assertIn('COSTO OPCIONAL', resultado['mensaje'])

        interpretar.assert_not_called()

    def test_seguimiento_de_herramientas_generico_devuelve_solo_herramientas(self):
        herramienta = Producto.objects.create(
            nombre='Taladro para proyecto de cobertizo',
            descripcion='Herramienta para perforar y atornillar.',
            precio=24990,
            stock=7,
            categoria='Herramientas',
            activo=True,
        )
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Construcción de cobertizo',
            'modo_orientacion': 'propuesta_directa',
            '_consulta_solo_herramientas': True,
            'incluir_herramientas': True,
            'tareas_proyecto': [{
                'nombre': 'Estructura',
                'busquedas': ['pino dimensionado para exterior'],
            }],
            'herramientas_proyecto': ['taladro proyecto cobertizo'],
            'datos_faltantes_proyecto': [],
            'especialidades_proyecto': [],
        })

        self.assertEqual(resultado['tipo'], 'seguimiento_herramientas')
        self.assertEqual([item['id'] for item in resultado['productos']], [herramienta.id])
        self.assertNotIn(self.madera.nombre, resultado['mensaje'])
        self.assertIn('No modifiqué los materiales', resultado['mensaje'])

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_boton_ajustar_pide_el_cambio_sin_reconstruir(self, interpretar):
        resultado = procesar_consulta(
            'Ajustar el proyecto',
            [],
            [self.madera.id],
        )

        interpretar.assert_not_called()
        self.assertEqual(resultado['tipo'], 'seguimiento_proyecto')
        self.assertIn('Mantendré todo lo demás', resultado['mensaje'])
        self.assertIn('Quiero cambiar las medidas', resultado['sugerencias'])

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_quincho_estandar_activa_propuesta_sin_cuestionario(self, interpretar):
        interpretar.return_value = {
            'intencion': 'planificar_proyecto',
            'proyecto': 'Quincho estándar',
            'tareas_proyecto': [{
                'nombre': 'Estructura base',
                'busquedas': ['pino dimensionado para exterior'],
            }],
            'datos_faltantes_proyecto': ['Ancho y fondo del quincho'],
        }

        resultado = procesar_consulta('Quiero hacer un quincho estándar', [])

        self.assertEqual(resultado['tipo'], 'plan_proyecto_generico')
        self.assertTrue(resultado['productos'])
        self.assertIn('PROPUESTA ESTÁNDAR PARA TU PROYECTO', resultado['mensaje'])
        self.assertNotIn('ANTES DE RECOMENDAR PRODUCTOS', resultado['mensaje'])

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_no_reemplaza_tejas_solicitadas_por_zinc(self, interpretar):
        interpretar.return_value = {
            'intencion': 'planificar_proyecto',
            'proyecto': 'Construcción de techo estándar de madera',
            'tareas_proyecto': [{
                'nombre': 'Cubierta',
                'busquedas': ['plancha zinc acanalado'],
                'usos_materiales': ['Cubrir la estructura del techo.'],
                'bases_calculo': ['superficie_cubierta'],
            }],
            'datos_faltantes_proyecto': [],
        }

        resultado = procesar_consulta(
            'Quiero hacer un techo estándar de 4 x 6 metros, estructura de madera y tejas',
            [],
        )

        self.assertEqual(resultado['tipo'], 'plan_proyecto_generico')
        self.assertTrue(resultado['productos'])
        self.assertTrue(any(
            'teja' in producto['nombre'].casefold()
            for producto in resultado['productos']
        ))
        self.assertFalse(any(
            'zinc' in producto['nombre'].casefold()
            for producto in resultado['productos']
        ))

    def test_proyecto_muestra_mas_de_seis_materiales_planificados(self):
        nombres = [
            'Material exclusivo alfa', 'Material exclusivo beta',
            'Material exclusivo gamma', 'Material exclusivo delta',
            'Material exclusivo epsilon', 'Material exclusivo zeta',
            'Material exclusivo theta',
        ]
        for nombre in nombres:
            Producto.objects.create(
                nombre=nombre,
                descripcion='Material destinado exclusivamente a una etapa de prueba.',
                precio=1000,
                stock=10,
                categoria='Construcción',
                activo=True,
            )

        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Proyecto estándar completo',
            '_proyecto_estandar': True,
            'tareas_proyecto': [
                {'nombre': 'Etapa 1', 'busquedas': nombres[:3]},
                {'nombre': 'Etapa 2', 'busquedas': nombres[3:6]},
                {'nombre': 'Etapa 3', 'busquedas': nombres[6:]},
            ],
            'datos_faltantes_proyecto': [],
        })

        self.assertEqual(len(resultado['productos']), 7)

    def test_quincho_completo_admite_mas_de_ocho_materiales_con_usos_claros(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Quincho estándar completo',
            '_proyecto_estandar': True,
            'tareas_proyecto': [
                {'nombre': 'Preparación del radier', 'busquedas': [
                    'base estabilizada para radier saco 25 kg',
                    'polietileno construcción 200 micras 4 x 25 m',
                    'malla ACMA C-92 2,60 x 5 m',
                ], 'usos_materiales': [
                    {'busqueda': 'base estabilizada para radier saco 25 kg', 'uso': 'Preparar la base compactada del radier.'},
                    {'busqueda': 'polietileno construcción 200 micras 4 x 25 m', 'uso': 'Separar el radier del terreno preparado.'},
                    {'busqueda': 'malla ACMA C-92 2,60 x 5 m', 'uso': 'Reforzar el radier antes del hormigonado.'},
                ]},
                {'nombre': 'Albañilería y zona de fuego', 'busquedas': [
                    'hormigón predosificado H20 saco 25 kg',
                    'mortero pega ladrillos saco 25 kg',
                    'ladrillo refractario 23 x 11 x 3 cm',
                ], 'usos_materiales': [
                    {'busqueda': 'hormigón predosificado H20 saco 25 kg', 'uso': 'Formar el radier del quincho.'},
                    {'busqueda': 'mortero pega ladrillos saco 25 kg', 'uso': 'Unir los ladrillos de albañilería.'},
                    {'busqueda': 'ladrillo refractario 23 x 11 x 3 cm', 'uso': 'Revestir la zona interior expuesta al fuego.'},
                ]},
                {'nombre': 'Estructura metálica', 'busquedas': [
                    'mortero refractario balde 5 kg',
                    'perfil tubular acero 80 x 80 x 3 mm x 6 m',
                    'perfil costanera acero 100 x 50 x 2 mm x 6 m',
                ], 'usos_materiales': [
                    {'busqueda': 'mortero refractario balde 5 kg', 'uso': 'Unir los ladrillos refractarios.'},
                    {'busqueda': 'perfil tubular acero 80 x 80 x 3 mm x 6 m', 'uso': 'Formar los pilares de la estructura.'},
                    {'busqueda': 'perfil costanera acero 100 x 50 x 2 mm x 6 m', 'uso': 'Formar los apoyos donde se fija la cubierta.'},
                ]},
                {'nombre': 'Uniones y revestimiento', 'busquedas': [
                    'electrodo soldadura E6013 2,5 mm caja 1 kg',
                    'perno anclaje expansión M12 x 120 mm pack 4',
                    'plancha fibrocemento exterior 8 mm 1,20 x 2,40 m',
                ], 'usos_materiales': [
                    {'busqueda': 'electrodo soldadura E6013 2,5 mm caja 1 kg', 'uso': 'Realizar las uniones soldadas de la estructura.'},
                    {'busqueda': 'perno anclaje expansión M12 x 120 mm pack 4', 'uso': 'Anclar la estructura a la base.'},
                    {'busqueda': 'plancha fibrocemento exterior 8 mm 1,20 x 2,40 m', 'uso': 'Cerrar superficies exteriores compatibles.'},
                ]},
            ],
            'datos_faltantes_proyecto': [],
        })

        self.assertGreaterEqual(len(resultado['productos']), 12)
        mensaje = resultado['mensaje'].casefold()
        self.assertIn('reforzar el radier', mensaje)
        self.assertIn('zona interior expuesta al fuego', mensaje)
        self.assertIn('apoyos donde se fija la cubierta', mensaje)

    def test_quincho_calcula_cada_material_con_su_superficie_correcta(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Quincho estándar de 4 x 6 metros',
            '_proyecto_estandar': True,
            'ancho_cm': 400,
            'fondo_cm': 600,
            'tareas_proyecto': [{
                'nombre': 'Radier y cubierta',
                'busquedas': [
                    'malla ACMA C-92 2,60 x 5 m',
                    'polietileno construcción 200 micras 4 x 25 m',
                    'plancha zinc acanalado 0,35 mm x 3 m',
                ],
                'usos_materiales': [
                    'Reforzar el radier.',
                    'Separar el radier del terreno.',
                    'Formar la cubierta del quincho.',
                ],
                'bases_calculo': [
                    'superficie_piso',
                    'superficie_piso',
                    'superficie_cubierta',
                ],
            }],
            'datos_faltantes_proyecto': [],
        })

        calculados = {
            producto['nombre']: producto
            for producto in resultado['productos']
            if producto.get('cantidad_requerida')
        }
        self.assertEqual(len(calculados), 3)
        self.assertTrue(all(
            producto['medida_base'] == '24 m²'
            for producto in calculados.values()
        ))
        self.assertIn('superficie piso', resultado['mensaje'])
        self.assertIn('superficie cubierta', resultado['mensaje'])

    def test_bases_de_calculo_tambien_aplican_a_otros_proyectos(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Terraza exterior estándar de 3 x 5 metros',
            '_proyecto_estandar': True,
            'ancho_cm': 300,
            'fondo_cm': 500,
            'tareas_proyecto': [{
                'nombre': 'Terminación del piso',
                'busquedas': ['baldosa exterior antideslizante 40 x 40 cm caja 1,44 m²'],
                'usos_materiales': ['Terminar la superficie transitable de la terraza.'],
                'bases_calculo': ['superficie_piso'],
            }],
            'datos_faltantes_proyecto': [],
        })

        producto = resultado['productos'][0]
        self.assertEqual(producto['medida_base'], '15 m²')
        self.assertGreater(producto['cantidad_requerida'], 1)
        self.assertIn('Terraza exterior', resultado['mensaje'])

    def test_techumbre_pide_datos_criticos_antes_de_sugerir_materiales(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Cambio de techo de policarbonato',
            'ancho_cm': 0,
            'fondo_cm': 0,
            'material_estructura': '',
            'estado_estructura': '',
            'tipo_cubierta': 'policarbonato',
            'datos_faltantes_proyecto': [],
            'tareas_proyecto': [],
        })

        self.assertEqual(resultado['tipo'], 'aclaracion_proyecto')
        self.assertEqual(resultado['productos'], [])
        mensaje = resultado['mensaje'].casefold()
        self.assertIn('largo y ancho', mensaje)
        self.assertIn('material y estado de la estructura', mensaje)
        self.assertIn('formato y espesor', mensaje)
        self.assertNotIn('\n4.', mensaje)
        self.assertIn('3 × 4 m', resultado['sugerencias'][0])
        self.assertIn('estructura', resultado['sugerencias'][0])
        self.assertFalse(any(
            'maestro' in sugerencia.casefold()
            for sugerencia in resultado['sugerencias']
        ))

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_techumbre_no_repite_material_ni_confunde_metros_con_herramientas(
        self,
        interpretar,
    ):
        interpretar.return_value = {
            'intencion': 'planificar_proyecto',
            'proyecto': 'Cambio de techo de policarbonato',
            'ancho_cm': 300,
            'fondo_cm': 200,
            'material_estructura': 'hormigon',
            'estado_estructura': '',
            'tipo_cubierta': 'policarbonato',
            'incluir_herramientas': True,
            'datos_faltantes_proyecto': [],
            'tareas_proyecto': [],
            'herramientas_proyecto': ['sierra circular'],
            'especialidades_proyecto': [],
        }

        resultado = procesar_consulta(
            'Quiero cambiar mi techo de policarbonato; es de 3 x 2 metros en hormigón.',
            [],
        )

        self.assertEqual(resultado['tipo'], 'aclaracion_proyecto')
        self.assertIn('ESTADO DE LA ESTRUCTURA', resultado['mensaje'])
        self.assertNotIn('MATERIAL DE LA ESTRUCTURA', resultado['mensaje'])
        self.assertNotIn('sierra', resultado['mensaje'].casefold())

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_techumbre_no_acepta_cubierta_inventada_por_gemini(self, interpretar):
        interpretar.return_value = {
            'intencion': 'planificar_proyecto',
            'proyecto': 'Cambio de techumbre',
            'ancho_cm': 300,
            'fondo_cm': 400,
            'material_estructura': 'madera',
            'estado_estructura': 'reutilizable',
            'tipo_cubierta': 'zinc',
            'material_principal_proyecto': 'zinc',
            'datos_faltantes_proyecto': [],
            'tareas_proyecto': [],
            'herramientas_proyecto': [],
            'especialidades_proyecto': [],
        }

        resultado = procesar_consulta(
            'Quiero cambiar mi techo; mide 3 x 4 m y la estructura de madera está firme.',
            [],
        )

        self.assertEqual(resultado['tipo'], 'aclaracion_proyecto')
        self.assertEqual(resultado['productos'], [])
        self.assertIn(
            'material, formato y espesor de la cubierta',
            resultado['mensaje'].casefold(),
        )
        self.assertIn('zinc, policarbonato, tejas', resultado['mensaje'])
        self.assertNotIn('Plancha zinc', resultado['mensaje'])

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_seguimiento_de_herramientas_no_repite_plan_completo(self, interpretar):
        Producto.objects.create(
            nombre='Cinta métrica profesional 8 m',
            descripcion='Herramienta para medir longitudes.',
            precio=12990,
            stock=10,
            categoria='Herramientas',
            activo=True,
        )
        Producto.objects.create(
            nombre='Taladro percutor profesional',
            descripcion='Herramienta para perforar y atornillar.',
            precio=20000,
            stock=10,
            categoria='Herramientas',
            activo=True,
        )
        interpretar.return_value = {
            'intencion': 'planificar_proyecto',
            'proyecto': 'Cambio de techo de zinc',
            'ancho_cm': 300,
            'fondo_cm': 400,
            'material_estructura': 'madera',
            'estado_estructura': 'reutilizable',
            'tipo_cubierta': 'zinc',
            'incluir_herramientas': True,
            'datos_faltantes_proyecto': [],
            'tareas_proyecto': [],
            'herramientas_proyecto': ['cinta métrica', 'taladro percutor'],
            'especialidades_proyecto': [],
        }
        historial = [{
            'role': 'user',
            'content': (
                'Quiero cambiar mi techo de zinc; mide 3 x 4 m y la estructura '
                'de madera está firme.'
            ),
        }]

        resultado = procesar_consulta(
            '¿Y qué herramientas se usan?',
            historial,
        )

        self.assertEqual(resultado['tipo'], 'plan_proyecto_generico')
        self.assertIn('HERRAMIENTAS PARA TU TECHUMBRE', resultado['mensaje'])
        self.assertIn('COSTO OPCIONAL DE HERRAMIENTAS', resultado['mensaje'])
        self.assertNotIn('PROYECTO\nAnalicé', resultado['mensaje'])
        self.assertTrue(resultado['productos'])
        self.assertTrue(all(
            'herramienta' in producto['rol'].casefold()
            for producto in resultado['productos']
        ))

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_techumbre_recomienda_cubierta_si_usuario_delega_eleccion(self, interpretar):
        interpretar.return_value = {
            'intencion': 'planificar_proyecto',
            'respuesta': 'Revisaré una alternativa compatible.',
            'proyecto': 'Instalación de techo de policarbonato',
            'ancho_cm': 0,
            'fondo_cm': 0,
            'material_estructura': '',
            'estado_estructura': '',
            'tipo_cubierta': 'policarbonato',
            'datos_faltantes_proyecto': ['formato y espesor del policarbonato'],
            'tareas_proyecto': [],
            'herramientas_proyecto': [],
            'especialidades_proyecto': [],
        }
        historial = [
            {'role': 'user', 'content': 'Quiero un techo de policarbonato'},
            {
                'role': 'assistant',
                'content': 'Indica largo y ancho, material y estado de la estructura.',
            },
        ]

        resultado = procesar_consulta(
            '2x3 madera, el ambiente está en buena forma; lo demás recomiéndamelo tú',
            historial,
        )

        self.assertEqual(resultado['tipo'], 'plan_proyecto_generico')
        self.assertEqual(resultado['superficie_m2'], 6)
        self.assertIn('Como pediste una recomendación', resultado['mensaje'])
        self.assertIn('Policarbonato alveolar 6 mm', resultado['mensaje'])
        self.assertTrue(any(
            'policarbonato alveolar 6 mm' in item['nombre'].casefold()
            for item in resultado['productos']
        ))

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_techumbre_entiende_hormigon_bueno_y_eleccion_delegada(self, interpretar):
        interpretar.return_value = {
            'intencion': 'planificar_proyecto',
            'proyecto': 'Cambio de techo de policarbonato',
            'ancho_cm': 0,
            'fondo_cm': 0,
            'alto_cm': 0,
            'material_estructura': '',
            'estado_estructura': 'nueva',
            'tipo_cubierta': 'policarbonato',
            'datos_faltantes_proyecto': [
                'altura de la estructura nueva',
                'formato y espesor del policarbonato',
            ],
            'tareas_proyecto': [],
            'herramientas_proyecto': [],
            'especialidades_proyecto': [],
        }
        historial = [{
            'role': 'assistant',
            'content': 'Indica medidas, material y estado de la estructura, y cubierta.',
        }]

        resultado = procesar_consulta(
            '3x4 hormigón bueno, no lo sé, elige tú',
            historial,
        )

        self.assertEqual(resultado['tipo'], 'plan_proyecto_generico')
        self.assertEqual(resultado['superficie_m2'], 12)
        self.assertNotIn('ALTURA DE LA ESTRUCTURA NUEVA', resultado['mensaje'])
        self.assertIn('Como pediste una recomendación', resultado['mensaje'])

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_respuesta_sobre_estado_continua_proyecto_y_no_selecciona_tarjeta(self, interpretar):
        piso = Producto.objects.filter(nombre__icontains='Piso laminado 8 mm').first()
        interpretar.return_value = {
            'intencion': 'buscar_producto',
            'respuesta': 'El piso está en buen estado.',
            'consulta_producto': 'el piso',
            'proyecto': 'Cambio de piso flotante',
            'superficie': 30,
            'tareas_proyecto': [{
                'nombre': 'Instalación de piso',
                'busquedas': ['piso laminado 8 mm'],
            }, {
                'nombre': 'Demolición',
                'busquedas': ['herramientas demolición'],
            }],
            'herramientas_proyecto': ['herramientas demolición'],
            'especialidades_proyecto': [],
            'datos_faltantes_proyecto': [
                'estado del piso actual',
                '¿Qué material es la base actual del piso?',
            ],
        }
        historial = [
            {'role': 'user', 'content': 'Quiero cambiar mi piso flotante, mide 3 x 10 m'},
            {
                'role': 'assistant',
                'content': (
                    'Analicé “Cambio de piso flotante”. Para calcular cantidades '
                    'exactas todavía necesito: estado del piso actual.'
                ),
            },
        ]

        resultado = procesar_consulta(
            'El piso está en perfecto estado',
            historial,
            [piso.id],
        )

        self.assertEqual(resultado['tipo'], 'aclaracion_proyecto')
        self.assertIn('PROYECTO\n', resultado['mensaje'])
        self.assertIn('ANTES DE RECOMENDAR PRODUCTOS\n', resultado['mensaje'])
        self.assertIn('RESPONDE TODO EN UN MENSAJE\n', resultado['mensaje'])
        self.assertNotIn('A cuál de los productos', resultado['mensaje'])
        self.assertIn('hormigón, madera/OSB o cerámica', resultado['mensaje'])
        self.assertNotIn('demolición', resultado['mensaje'].casefold())
        self.assertEqual(resultado['productos'], [])

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_pedir_recomendacion_no_reinicia_cuestionario_pendiente(self, interpretar):
        historial = [{
            'role': 'assistant',
            'content': (
                'PROYECTO\nCambio de piso flotante\n\n'
                'ANTES DE RECOMENDAR PRODUCTOS\n'
                'Necesito estos datos:\n'
                '• Qué tipo de piso deseas instalar\n'
                '• Cuál es el material de la superficie actual\n'
                '• Cuál es el estado actual del piso\n\n'
                'RESPONDE TODO EN UN MENSAJE'
            ),
        }]

        resultado = procesar_consulta(
            '¿Qué piso me recomiendas?',
            historial,
            [1, 2, 3],
        )

        interpretar.assert_not_called()
        self.assertEqual(resultado['tipo'], 'aclaracion_proyecto')
        self.assertEqual(resultado['productos'], [])
        self.assertIn('yo elegiré la opción más conveniente', resultado['mensaje'])
        self.assertNotIn('Qué tipo de piso', resultado['mensaje'])
        self.assertIn('material de la superficie actual', resultado['mensaje'])
        self.assertIn('estado actual del piso', resultado['mensaje'])

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_elegir_formato_de_policarbonato_avanza_sin_sugerencias_de_piso(
        self,
        interpretar,
    ):
        interpretar.return_value = {
            'intencion': 'planificar_proyecto',
            'proyecto': 'Cambio de techo de policarbonato',
            'ancho_cm': 300,
            'fondo_cm': 400,
            'material_estructura': 'hormigon',
            'estado_estructura': 'reutilizable',
            'tipo_cubierta': 'policarbonato',
            'datos_faltantes_proyecto': ['formato y espesor del policarbonato'],
            'tareas_proyecto': [],
            'herramientas_proyecto': [],
            'especialidades_proyecto': [],
        }
        historial = [{
            'role': 'assistant',
            'content': (
                'PROYECTO\nCambio de techo de policarbonato\n\n'
                'ANTES DE RECOMENDAR PRODUCTOS\n'
                '1. FORMATO Y ESPESOR DEL POLICARBONATO\n'
                '• Indica tu preferencia si ya la conoces.\n'
                '• No lo sé: escribe “elige tú”.'
            ),
        }]

        resultado = procesar_consulta(
            'Elige tú una cubierta compatible',
            historial,
        )

        interpretar.assert_called_once()
        self.assertEqual(resultado['tipo'], 'plan_proyecto_generico')
        self.assertNotIn('SIGAMOS CON TU PROYECTO', resultado['mensaje'])
        self.assertFalse(any(
            'base es de' in sugerencia.casefold()
            for sugerencia in resultado.get('sugerencias', [])
        ))

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_estado_y_eleccion_en_un_mensaje_completan_el_cuestionario(self, interpretar):
        interpretar.return_value = {
            'intencion': 'planificar_proyecto',
            'proyecto': 'Cambio de techo de policarbonato',
            'ancho_cm': 300,
            'fondo_cm': 200,
            'material_estructura': 'hormigon',
            'estado_estructura': '',
            'tipo_cubierta': 'policarbonato',
            'datos_faltantes_proyecto': ['estado de la estructura', 'formato del policarbonato'],
            'tareas_proyecto': [],
            'herramientas_proyecto': [],
            'especialidades_proyecto': [],
            'incluir_herramientas': False,
        }
        historial = [{
            'role': 'assistant',
            'content': (
                'PROYECTO\nCambio de techo de policarbonato\n\n'
                'ANTES DE RECOMENDAR PRODUCTOS\n'
                '1. ESTADO DE LA ESTRUCTURA DE APOYO\n'
                '2. FORMATO Y ESPESOR DEL POLICARBONATO\n\n'
                'RESPONDE TODO EN UN MENSAJE'
            ),
        }]

        resultado = procesar_consulta('Bueno, elige tú', historial)

        interpretar.assert_called_once()
        self.assertNotEqual(resultado['tipo'], 'aclaracion_proyecto')
        self.assertNotIn('SIGAMOS CON TU PROYECTO', resultado['mensaje'])

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_este_proyecto_no_se_confunde_con_una_tarjeta(self, interpretar):
        producto = Producto.objects.create(
            nombre='Plancha de cubierta de prueba',
            descripcion='Material para un proyecto de techumbre.',
            precio=15990,
            stock=10,
            categoria='Construcción',
            activo=True,
        )
        interpretar.return_value = {
            'intencion': 'orientacion_general',
            'respuesta': 'El costo mostrado para este proyecto es parcial.',
        }

        resultado = procesar_consulta(
            '¿Cuánto cuesta este proyecto?',
            [],
            [producto.id],
        )

        self.assertEqual(resultado['tipo'], 'orientacion')
        self.assertNotIn('A cuál de los productos', resultado['mensaje'])

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_cuanto_sale_todo_recupera_el_total_del_proyecto(self, interpretar):
        producto = Producto.objects.create(
            nombre='Material contextual para total',
            descripcion='Material del proyecto actual.',
            precio=10000,
            stock=10,
            categoria='Construcción',
            activo=True,
        )
        historial = [{
            'role': 'assistant',
            'content': (
                'TOTAL CALCULADO\n$98.970 CLP por 1 material con cantidad verificada.\n'
                'Este es un total parcial: faltan materiales por cuantificar.\n\n'
                'Productos del proyecto.'
            ),
        }]

        resultado = procesar_consulta(
            '¿Cuánto me sale todo?',
            historial,
            [producto.id],
        )

        interpretar.assert_not_called()
        self.assertEqual(resultado['tipo'], 'seguimiento_proyecto')
        self.assertIn('$98.970 CLP', resultado['mensaje'])
        self.assertIn('total parcial', resultado['mensaje'].casefold())

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_techumbre_corrige_intencion_y_usa_solo_catalogo_con_stock(self, interpretar):
        Producto.objects.create(
            nombre='Policarbonato alveolar 6 mm',
            descripcion='Plancha para cubierta', precio=29990, stock=0,
            categoria='Construcción', activo=True,
        )
        tornillo = Producto.objects.create(
            nombre='Tornillo autoperforante metal para techo',
            descripcion='Fijación para estructura metálica', precio=4990, stock=30,
            categoria='Ferretería', activo=True,
        )
        interpretar.return_value = {
            'intencion': 'buscar_producto',
            'respuesta': 'Buscaré una opción.',
            'consulta_producto': 'policarbonato',
            'proyecto': '',
            'ancho_cm': 0,
            'fondo_cm': 0,
            'material_estructura': '',
            'estado_estructura': '',
            'tipo_cubierta': '',
            'tareas_proyecto': [],
            'herramientas_proyecto': [],
            'especialidades_proyecto': [],
            'datos_faltantes_proyecto': [],
        }

        resultado = procesar_consulta(
            'Quiero cambiar un techo de policarbonato alveolar 6 mm de 3 x 5 m; '
            'la estructura metálica está en buen estado.',
            [],
        )

        self.assertEqual(resultado['tipo'], 'plan_proyecto_generico')
        self.assertEqual(resultado['superficie_m2'], 15)
        self.assertIn(tornillo.id, {item['id'] for item in resultado['productos']})
        self.assertTrue(all(item['stock'] > 0 for item in resultado['productos']))
        self.assertTrue(any(
            'policarbonato' in item['nombre'].lower()
            for item in resultado['productos']
        ))

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_techumbre_prioriza_formato_detallado_de_respuesta_posterior(self, interpretar):
        interpretar.return_value = {
            'intencion': 'planificar_proyecto',
            'respuesta': 'Continuaré el proyecto.',
            'proyecto': 'Cambio de techo de policarbonato',
            'ancho_cm': 0,
            'fondo_cm': 0,
            'material_estructura': '',
            'estado_estructura': '',
            'tipo_cubierta': 'policarbonato',
            'tareas_proyecto': [],
            'herramientas_proyecto': [],
            'especialidades_proyecto': [],
            'datos_faltantes_proyecto': ['formato y espesor del policarbonato'],
        }
        historial = [{
            'role': 'user',
            'content': 'Quiero cambiar un techo de policarbonato.',
        }]

        resultado = procesar_consulta(
            'Mide 4 x 2 metros, la estructura es de madera y está en buen estado. '
            'Quiero policarbonato alveolar de 6 mm.',
            historial,
        )

        self.assertNotEqual(resultado['tipo'], 'aclaracion_proyecto')
        self.assertEqual(resultado['superficie_m2'], 8)

    def test_techumbre_calcula_planchas_con_rendimiento_y_margen_verificados(self):
        Producto.objects.filter(sku__startswith='TEST-EXT-TEC-POL').update(stock=0)
        policarbonato = Producto.objects.create(
            nombre='Policarbonato alveolar 6 mm',
            descripcion='Plancha de 2 por 1 metro para cubierta',
            precio=29990,
            stock=10,
            categoria='Construcción',
            activo=True,
            unidad_venta='unidad',
            contenido=Decimal('2.000'),
            unidad_contenido='m2',
            tipo_calculo='superficie',
            rendimiento=Decimal('2.000'),
            unidad_rendimiento='m2_unidad',
            porcentaje_desperdicio=Decimal('10.00'),
            informacion_tecnica_verificada=True,
        )

        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Cambio de techo de policarbonato',
            'ancho_cm': 400,
            'fondo_cm': 200,
            'material_estructura': 'madera',
            'estado_estructura': 'reutilizable',
            'tipo_cubierta': 'policarbonato alveolar 6 mm',
            'material_principal_proyecto': 'plancha de policarbonato',
            'datos_faltantes_proyecto': [],
            'tareas_proyecto': [],
        })

        cubierta = next(
            item for item in resultado['productos'] if item['id'] == policarbonato.id
        )
        self.assertEqual(cubierta['cantidad_requerida'], 5)
        self.assertEqual(cubierta['carrito_cantidad'], 5)
        self.assertEqual(cubierta['subtotal'], 5 * policarbonato.precio)
        self.assertFalse(cubierta['recomendacion_orientativa'])
        self.assertIn('5 unidad(es)', resultado['mensaje'])
        self.assertEqual(resultado['total_calculado'], 5 * policarbonato.precio)
        self.assertIn('TOTAL CALCULADO', resultado['mensaje'])
        self.assertIn('$149.950 CLP', resultado['mensaje'])

    def test_techumbre_zinc_no_confunde_cubierta_con_producto_zincado(self):
        Producto.objects.create(
            nombre='Clavo zincado para madera',
            descripcion='Clavo para fijaciones generales.',
            precio=1990,
            stock=50,
            categoria='Ferretería',
            activo=True,
        )
        plancha = Producto.objects.create(
            nombre='Plancha zinc acanalado 0,35 mm x 3 m prueba',
            descripcion='Cubierta metálica para techumbre.',
            precio=15990,
            stock=40,
            categoria='Construcción',
            activo=True,
            contenido=Decimal('2.550'),
            unidad_contenido='m2',
            tipo_calculo='superficie',
            rendimiento=Decimal('2.550'),
            unidad_rendimiento='m2_unidad',
            porcentaje_desperdicio=Decimal('10.00'),
            informacion_tecnica_verificada=True,
        )

        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Cambio de techumbre',
            'ancho_cm': 300,
            'fondo_cm': 400,
            'material_estructura': 'madera',
            'estado_estructura': 'reutilizable',
            'tipo_cubierta': 'zinc',
            'datos_faltantes_proyecto': [],
            'tareas_proyecto': [],
        })

        cubierta = next(
            producto for producto in resultado['productos']
            if producto['rol'] == 'Cubierta'
        )
        self.assertIn('plancha zinc acanalado', cubierta['nombre'].casefold())
        self.assertNotIn('clavo', cubierta['nombre'].casefold())
        self.assertEqual(cubierta['cantidad_requerida'], 6)
        self.assertEqual(resultado['total_calculado'], 95940)

    def test_techumbre_con_tejas_usa_familia_y_membrana_del_catalogo(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Cambio de techo con tejas',
            'ancho_cm': 300,
            'fondo_cm': 400,
            'material_estructura': 'madera',
            'estado_estructura': 'reutilizable',
            'tipo_cubierta': 'tejas',
            'datos_faltantes_proyecto': [],
            'tareas_proyecto': [],
        })

        nombres = [producto['nombre'].casefold() for producto in resultado['productos']]
        self.assertTrue(any('teja' in nombre for nombre in nombres))
        self.assertTrue(any(
            'membrana impermeable para techumbre' in nombre
            for nombre in nombres
        ))
        self.assertFalse(any(
            faltante in {'teja', 'teja para techo', 'sellador para techumbre exterior'}
            for faltante in resultado['faltantes_catalogo']
        ))

    def test_proyecto_libre_calcula_solo_con_ficha_tecnica_verificada(self):
        baldosa = Producto.objects.create(
            nombre='Baldosa exterior antideslizante terraza',
            descripcion='Revestimiento para terraza exterior',
            precio=18990,
            stock=20,
            categoria='Construcción',
            activo=True,
            contenido=Decimal('2.000'),
            unidad_contenido='m2',
            tipo_calculo='superficie',
            rendimiento=Decimal('2.000'),
            unidad_rendimiento='m2_unidad',
            porcentaje_desperdicio=Decimal('10.00'),
            informacion_tecnica_verificada=True,
        )

        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Instalar baldosas en terraza exterior',
            'superficie': 12,
            'tareas_proyecto': [{
                'nombre': 'Revestir la superficie',
                'busquedas': ['baldosa exterior antideslizante terraza'],
            }],
            'herramientas_proyecto': [],
            'especialidades_proyecto': [],
            'datos_faltantes_proyecto': [],
        })

        item = next(producto for producto in resultado['productos'] if producto['id'] == baldosa.id)
        self.assertEqual(item['cantidad_requerida'], 7)
        self.assertEqual(item['carrito_cantidad'], 7)
        self.assertFalse(item['recomendacion_orientativa'])
        self.assertIn('Cantidades calculadas con fichas verificadas', resultado['mensaje'])

    def test_proyecto_libre_orienta_aunque_falte_material_principal(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Construir cerco con paneles de bambú',
            'material_principal_proyecto': 'panel de bambú',
            'tareas_proyecto': [
                {
                    'nombre': 'Instalar postes',
                    'busquedas': ['pino dimensionado', 'cemento uso general'],
                },
                {
                    'nombre': 'Montar paneles',
                    'busquedas': ['tornillos para madera'],
                },
            ],
            'herramientas_proyecto': [],
            'especialidades_proyecto': ['Carpintería'],
            'datos_faltantes_proyecto': [],
        })

        self.assertEqual(resultado['tipo'], 'plan_proyecto_sin_producto')
        self.assertEqual(resultado['productos'], [])
        self.assertEqual(resultado['faltantes_catalogo'], ['panel de bambú'])
        self.assertIn('Instalar postes', resultado['mensaje'])
        self.assertIn('Montar paneles', resultado['mensaje'])
        self.assertIn('No encontré “panel de bambú” con stock', resultado['mensaje'])
        self.assertIn('Puedes continuar consultando etapas', resultado['mensaje'])

    def test_proyecto_libre_no_declara_faltante_un_material_ya_mostrado(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Construcción de cobertizo',
            'material_principal_proyecto': 'pino dimensionado',
            'tareas_proyecto': [{
                'nombre': 'Estructura de madera',
                'busquedas': ['pino dimensionado exterior'],
            }],
            'herramientas_proyecto': [],
            'especialidades_proyecto': ['Carpintería'],
            'datos_faltantes_proyecto': [
                'ancho del área a cubrir',
                'largo del área a cubrir',
            ],
        })

        ids = [producto['id'] for producto in resultado['productos']]
        self.assertEqual(ids.count(self.madera.id), 1)
        self.assertFalse(any(
            'pino dimensionado' in faltante.casefold()
            for faltante in resultado['faltantes_catalogo']
        ))
        self.assertNotIn('No encontré en el catálogo: pino', resultado['mensaje'])

    def test_proyecto_libre_solo_materiales_excluye_herramientas(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Construir estructura pequeña de madera',
            'material_principal_proyecto': 'pino dimensionado exterior',
            'tareas_proyecto': [{
                'nombre': 'Estructura',
                'busquedas': ['pino dimensionado exterior'],
            }],
            'herramientas_proyecto': ['taladro', 'sierra circular'],
            'incluir_herramientas': False,
            'especialidades_proyecto': [],
            'datos_faltantes_proyecto': [],
        })

        self.assertTrue(resultado['productos'])
        self.assertFalse(any(
            tarea['nombre'] == 'Herramientas recomendadas'
            for tarea in resultado['tareas']
        ))
        self.assertTrue(all(
            producto['rol'] != 'Herramientas recomendadas'
            for producto in resultado['productos']
        ))

    def test_cobertizo_nuevo_pide_altura_antes_de_mostrar_materiales(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Cobertizo de madera con cubierta de policarbonato',
            'ancho_cm': 300,
            'fondo_cm': 400,
            'alto_cm': 0,
            'material_estructura': 'madera',
            'estado_estructura': 'nueva',
            'tipo_cubierta': 'policarbonato alveolar 6 mm',
            'datos_faltantes_proyecto': [],
            'tareas_proyecto': [],
            'herramientas_proyecto': [],
            'incluir_herramientas': False,
        })

        self.assertEqual(resultado['tipo'], 'aclaracion_proyecto')
        self.assertEqual(resultado['productos'], [])
        self.assertIn('altura de la estructura nueva', resultado['mensaje'])
