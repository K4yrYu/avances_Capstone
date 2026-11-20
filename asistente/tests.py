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
from .services.asistente_sfi import (
    _evaluar_alcance_proyecto,
    _resolver_accion_seguimiento,
    _resolver_herramientas_iniciales,
    _resolver_proyecto,
)
from .serializers import ConsultaAsistenteSerializer
from .services.cliente_gemini import cliente_gemini
from .services.gemini import (
    GeminiNoDisponible, _catalogo_compacto, _instrucciones, interpretar_con_gemini,
    _solicitar_gemini_con_reintentos,
)
from .services.sinonimos_ferreteros import expandir_consulta
from .services.planificador_proyectos import (
    _ajustar_proyecto_ceramica,
    _producto_compatible_con_revestimiento_ceramico,
)


class CatalogoGeminiReducidoTests(TestCase):
    def test_catalogo_compacto_envia_solo_candidatos_relevantes(self):
        Producto.objects.create(
            nombre='Membrana impermeable para techumbre prueba',
            descripcion='Reparación de filtraciones y goteras en cubierta.',
            precio=9990,
            stock=12,
            categoria='Construcción',
            activo=True,
        )
        Producto.objects.create(
            nombre='Taladro no relacionado prueba',
            descripcion='Herramienta general.',
            precio=20000,
            stock=12,
            categoria='Herramientas',
            activo=True,
        )

        catalogo = _catalogo_compacto('Quiero reparar una gotera en el techo')

        self.assertLessEqual(len(catalogo), 60)
        nombres = ' '.join(item['nombre'].casefold() for item in catalogo)
        self.assertIn('membrana impermeable', nombres)


class PisoFlotanteTests(TestCase):
    def test_solicita_habitacion_medidas_base_y_estado(self):
        resultado = _resolver_proyecto({
            'proyecto': 'Instalación de piso flotante',
            '_contexto_usuario': 'quiero instalar piso flotante',
        })

        self.assertEqual(resultado['tipo'], 'aclaracion_proyecto')
        self.assertIn('UBICACIÓN DEL PISO', resultado['mensaje'])
        self.assertIn('SUPERFICIE', resultado['mensaje'])
        self.assertIn('BASE ACTUAL', resultado['mensaje'])
        self.assertIn('ESTADO DE LA BASE', resultado['mensaje'])

    def test_ofrece_alternativas_por_precio_y_color_en_living(self):
        resultado = _resolver_proyecto({
            'proyecto': 'Instalación de piso flotante',
            '_contexto_usuario': (
                'es para el living de 4 x 5 metros sobre radier firme seco y nivelado'
            ),
            'ancho_cm': 400,
            'fondo_cm': 500,
        })

        self.assertEqual(resultado['tipo'], 'propuesta_piso_flotante')
        alternativas = [
            item for item in resultado['productos'] if item.get('es_alternativa')
        ]
        self.assertGreaterEqual(len(alternativas), 3)
        self.assertTrue(all(item['cantidad_requerida'] > 0 for item in alternativas))
        self.assertTrue(all(item.get('detalle_material') for item in alternativas))
        self.assertEqual(
            [item['rol'] for item in alternativas],
            [f'Alternativa {numero} de piso flotante' for numero in range(1, len(alternativas) + 1)],
        )
        self.assertIn('no deben sumarse entre sí', resultado['mensaje'])
        self.assertIn('no es un presupuesto definitivo', resultado['mensaje'].casefold())
        self.assertIn('profesional calificado', resultado['mensaje'].casefold())
        self.assertIn('de living, sobre', resultado['mensaje'])
        self.assertNotIn('de living y comedor, sobre', resultado['mensaje'])

    def test_separa_complementos_de_las_alternativas(self):
        resultado = _resolver_proyecto({
            'proyecto': 'Instalación de piso flotante',
            '_contexto_usuario': (
                'es para el living de 3 x 6 metros sobre radier firme seco y nivelado'
            ),
        })

        alternativas = [item for item in resultado['productos'] if item.get('es_alternativa')]
        complementos = [item for item in resultado['productos'] if item.get('es_opcional')]

        self.assertTrue(alternativas)
        self.assertTrue(complementos)
        self.assertTrue(all(not item.get('incluido_en_total', True) for item in complementos))
        self.assertIn('estimación separada', resultado['mensaje'])

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_comparacion_economica_usa_subtotales_y_excluye_complementos(self, interpretar):
        propuesta = _resolver_proyecto({
            'proyecto': 'Instalación de piso flotante',
            '_contexto_usuario': (
                'es para el living de 3 x 6 metros sobre radier firme seco y nivelado'
            ),
        })
        estimacion = [{
            clave: item[clave]
            for clave in (
                'id', 'carrito_cantidad', 'cantidad_requerida', 'rol',
                'detalle_material', 'es_opcional', 'es_alternativa',
                'incluido_en_total',
            )
            if clave in item
        } for item in propuesta['productos']]

        resultado = procesar_consulta(
            '¿Hay alternativas más económicas?',
            [],
            [item['id'] for item in propuesta['productos']],
            'auto',
            estimacion,
        )

        interpretar.assert_not_called()
        self.assertEqual(resultado['tipo'], 'comparacion_economica')
        self.assertEqual(len(resultado['productos']), 3)
        self.assertEqual(
            [item['sku'] for item in resultado['productos']],
            ['SFI-PFL-ESSEN-296', 'SFI-PFL-BONN-300', 'SFI-PFL-MISTY-238'],
        )
        self.assertEqual(resultado['productos'][0]['carrito_cantidad'], 7)
        self.assertTrue(all(item['carrito_cantidad'] > 1 for item in resultado['productos']))
        self.assertEqual(
            [item['subtotal'] for item in resultado['productos']],
            sorted(item['subtotal'] for item in resultado['productos']),
        )
        self.assertNotIn('Manta niveladora', resultado['mensaje'])
        self.assertNotIn('Barrera de vapor', resultado['mensaje'])
        self.assertIn('subtotal necesario', resultado['mensaje'])

    def test_reconoce_dimensiones_con_m2_y_pide_solo_nivelacion_pendiente(self):
        resultado = _resolver_proyecto({
            'proyecto': 'Instalación de piso flotante',
            '_contexto_usuario': (
                'es para el living, de 3 x 6 m2, con base de radier firme y seca'
            ),
        })

        self.assertEqual(resultado['tipo'], 'aclaracion_proyecto')
        self.assertIn('superficie: 18 m²', resultado['mensaje'])
        self.assertIn('Solo falta confirmar si está nivelada.', resultado['mensaje'])
        self.assertNotIn('Indica largo × ancho', resultado['mensaje'])

    def test_cocina_solo_muestra_piso_con_resistencia_al_agua_documentada(self):
        resultado = _resolver_proyecto({
            'proyecto': 'Instalación de piso flotante',
            '_contexto_usuario': (
                'es para la cocina de 3 x 4 metros sobre hormigon firme seco y nivelado'
            ),
            'ancho_cm': 300,
            'fondo_cm': 400,
        })

        self.assertEqual(resultado['tipo'], 'propuesta_piso_flotante')
        alternativas = [
            item for item in resultado['productos'] if item.get('es_alternativa')
        ]
        self.assertTrue(alternativas)
        for item in alternativas:
            producto = Producto.objects.get(pk=item['id'])
            self.assertTrue(producto.especificaciones.get('resistencia_agua_horas'))

    def test_no_recomienda_laminado_convencional_en_bano(self):
        resultado = _resolver_proyecto({
            'proyecto': 'Instalación de piso flotante',
            '_contexto_usuario': (
                'es para el baño de 2 x 3 metros sobre radier firme seco y nivelado'
            ),
            'ancho_cm': 200,
            'fondo_cm': 300,
        })

        self.assertEqual(resultado['tipo'], 'proyecto_no_recomendado')
        self.assertEqual(resultado['productos'], [])
        self.assertIn('no recomiendo un laminado convencional', resultado['mensaje'].casefold())


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
        self.assertContains(pagina, 'Hola, soy el asistente SFI.')
        self.assertContains(pagina, 'necesitas para tu proyecto.')
        self.assertNotContains(
            pagina,
            'calcular o encontrar productos',
        )
        self.assertContains(pagina, 'id="apply-paint-mask"')
        self.assertContains(pagina, 'data-open-visualizer')
        self.assertContains(pagina, 'Pintar 50 m&sup2;')
        self.assertContains(pagina, 'data-query-mode="producto"')
        self.assertContains(pagina, 'data-query-mode="herramienta"')
        self.assertContains(pagina, 'data-query-mode="proyecto_reparacion"')
        self.assertContains(pagina, 'data-query-mode="problema_cotidiano"')
        self.assertNotContains(pagina, 'data-suggestion="Quiero renovar mi baño"')
        self.assertNotContains(pagina, reverse('mi_historial_compras'))
        self.assertContains(pagina, 'Compra protegida con Webpay')
        self.assertContains(inicio, reverse('asistente_sfi'))

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_respuesta_nuevo_completa_estado_de_superficie_pendiente(self, interpretar):
        interpretar.return_value = {
            'intencion': 'calcular_pintura',
            'superficie': 10,
            'ambiente': 'interior',
            'tipo_superficie': 'hormigon',
            'estado_superficie': '',
            'terminacion': 'cualquiera',
            'color': '',
            'capas': 0,
            'desperdicio': -1,
            'presupuesto': 0,
        }
        historial = [{
            'role': 'assistant',
            'content': 'Necesito saber el estado actual de la superficie del muro.',
        }]

        resultado = procesar_consulta('NUEVO', historial)

        self.assertEqual(resultado['tipo'], 'calculo_pintura')
        self.assertTrue(resultado['productos'])

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
        self.assertIn('¿Para qué sirve?', resultado['sugerencias'])
        self.assertIn('¿Cómo se utiliza?', resultado['sugerencias'])

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

    def test_bano_solo_piso_sin_material_pide_especificarlo(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'cambiar piso de baño',
            'alcance_bano': 'piso',
            'superficie': 5,
            'superficie_muros': 0,
            'incluir_sanitario': False,
            'incluir_lavamanos': False,
            'incluir_ducha': False,
            'presupuesto': 0,
        })

        self.assertEqual(resultado['tipo'], 'aclaracion_proyecto')
        self.assertIn('tipo de piso', resultado['mensaje'].casefold())
        self.assertFalse(resultado['productos'])

    def test_bano_piso_ceramico_usa_estructura_estandar(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'cambiar piso de cerámica del baño',
            '_contexto_usuario': (
                'quiero cambiar el piso de cerámica del baño; son 5 m²; '
                'la base es de hormigón firme, seca y nivelada'
            ),
            'alcance_bano': 'piso',
            'superficie': 5,
            'superficie_muros': 0,
            'presupuesto': 0,
            'tareas_proyecto': [],
            'datos_faltantes_proyecto': [],
        })

        self.assertEqual(resultado['tipo'], 'plan_proyecto_generico')
        self.assertTrue(resultado['mensaje'].startswith(
            'PROPUESTA ESTÁNDAR PARA TU PROYECTO'
        ))
        self.assertIn('consulta con un profesional', resultado['mensaje'].casefold())
        nombres = ' '.join(
            producto['nombre'].casefold() for producto in resultado['productos']
        )
        self.assertIn('cerámica', nombres)
        self.assertNotIn('porcelanato piso baño', nombres)

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

        self.assertEqual(resultado['tipo'], 'aclaracion_proyecto')
        self.assertIn('tipo de piso', resultado['mensaje'].casefold())
        self.assertFalse(resultado['productos'])

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
        procesar.assert_called_once_with(
            '¿Qué necesito para lijar?', [], [], 'auto',
        )

    def test_api_oculta_error_de_validacion_y_lo_registra(self):
        with self.assertLogs('asistente.views', level='WARNING') as registros:
            response = self.client.post(
                reverse('api_consultar_asistente'),
                {
                    'mensaje': '¿Para qué sirve?',
                    'historial': [{
                        'role': 'assistant',
                        'content': 'x' * 4001,
                    }],
                },
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()['detail'],
            'El asistente no está disponible en este momento.',
        )
        self.assertNotIn('4000', response.content.decode())
        self.assertTrue(any('4000' in registro for registro in registros.output))

    @patch('asistente.views.procesar_consulta', side_effect=RuntimeError('detalle interno'))
    def test_api_oculta_excepcion_inesperada_y_la_registra(self, _procesar):
        with self.assertLogs('asistente.views', level='ERROR') as registros:
            response = self.client.post(
                reverse('api_consultar_asistente'),
                {'mensaje': 'Necesito orientación', 'historial': []},
                content_type='application/json',
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json()['detail'],
            'El asistente no está disponible en este momento.',
        )
        self.assertNotIn('detalle interno', response.content.decode())
        self.assertTrue(any('detalle interno' in registro for registro in registros.output))

    def test_api_acepta_modo_inicial_sin_bloquear_la_consulta(self):
        serializer = ConsultaAsistenteSerializer(data={
            'mensaje': 'Necesito reparar una filtración',
            'modo_consulta': 'problema_cotidiano',
        })

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data['modo_consulta'],
            'problema_cotidiano',
        )

    def test_consulta_ajena_a_ferreteria_no_genera_un_proyecto(self):
        resultado = procesar_consulta('Quiero hacer una pizza', [])

        self.assertEqual(resultado['tipo'], 'fuera_contexto')
        self.assertEqual(resultado['productos'], [])
        self.assertIn('fuera del ámbito', resultado['mensaje'])
        self.assertIn('ferretería', resultado['mensaje'])

    def test_otra_consulta_ajena_tambien_se_mantiene_fuera_de_contexto(self):
        resultado = procesar_consulta('Escríbeme un poema romántico', [])

        self.assertEqual(resultado['tipo'], 'fuera_contexto')
        self.assertEqual(resultado['productos'], [])

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_problema_cotidiano_ferretero_no_es_bloqueado(self, interpretar):
        interpretar.return_value = {
            'intencion': 'buscar_producto',
            'consulta_producto': 'impermeabilizante para techo',
        }

        resultado = procesar_consulta(
            'Necesito algo para que no entre agua por el techo', [],
        )

        self.assertNotEqual(resultado['tipo'], 'fuera_contexto')

    def test_tarea_cotidiana_de_clavar_recomienda_martillo_real(self):
        martillo = Producto.objects.create(
            nombre='Martillo carpintero de prueba 16 oz',
            descripcion='Martillo para clavar y retirar clavos.',
            precio=8990,
            imagen='productos/martillo-prueba.webp',
            stock=6,
            categoria='Herramientas',
            marca='SFI',
            activo=True,
        )

        resultado = procesar_consulta(
            'Necesito algo para poner los clavos',
            [],
        )

        self.assertEqual(resultado['tipo'], 'productos')
        self.assertEqual(resultado['productos'][0]['id'], martillo.id)
        self.assertIn('martillo', resultado['mensaje'].casefold())

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
        self.assertEqual(opciones['json']['generationConfig']['maxOutputTokens'], 4096)

    @override_settings(
        GEMINI_API_KEY='clave-secreta-prueba',
        GEMINI_MODEL='gemini-3.5-flash-lite',
        GEMINI_TIMEOUT_SECONDS=10,
    )
    @patch('asistente.services.gemini.cliente_gemini.post')
    def test_gemini_reintenta_una_respuesta_json_truncada(self, post):
        truncada = Mock()
        truncada.raise_for_status.return_value = None
        truncada.json.return_value = {
            'candidates': [{
                'finishReason': 'MAX_TOKENS',
                'content': {'parts': [{'text': '{"intencion":"planificar_proyecto"'}]},
            }],
        }
        completa = Mock()
        completa.raise_for_status.return_value = None
        completa.json.return_value = {
            'candidates': [{'content': {'parts': [{'text': (
                '{"intencion":"aclarar","respuesta":"Indica tus medidas"}'
            )}]}}],
        }
        post.side_effect = [truncada, completa]

        resultado = interpretar_con_gemini('Quiero hacer un quincho estándar', [])

        self.assertEqual(resultado['intencion'], 'aclarar')
        self.assertEqual(post.call_count, 2)

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

    def test_cambiar_automatico_del_tablero_se_deriva_a_electricista(self):
        resultado = procesar_consulta(
            'Necesito cambiar el automático del tablero eléctrico', [],
        )

        self.assertEqual(resultado['tipo'], 'orientacion_seguridad')
        self.assertIn('electricista', resultado['mensaje'].casefold())
        self.assertFalse(resultado['productos'])


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

    def test_expandir_enchufe_agrega_tomacorriente(self):
        expandidas, agregados = expandir_consulta(['enchufe'])
        self.assertIn('tomacorriente', agregados)
        self.assertIn('enchufe', expandidas)

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

    def test_buscar_corta_tubos_pvc_encuentra_cortatubo_y_no_sierra(self):
        cortatubo = Producto.objects.create(
            nombre='Cortatubo plástico PPR hasta 42 mm',
            descripcion='Herramienta para cortar tubos plásticos de diámetro compatible.',
            precio=10990, stock=30, categoria='Herramientas', marca='SFI', activo=True,
        )
        from .services.asistente_sfi import _buscar_productos

        resultados = _buscar_productos('con qué herramienta puedo cortar tubos de PVC')
        ids = [producto.id for producto in resultados]

        self.assertIn(cortatubo.id, ids)
        self.assertNotIn(self.sierra.id, ids)

    def test_buscar_picota_no_incluye_macetero_por_sinonimo_jardinera(self):
        picota = Producto.objects.create(
            nombre='Picota jardinera acero 2,5 kg mango fibra',
            descripcion='Herramienta manual para aflojar tierra compactada.',
            precio=18990, stock=24, categoria='Herramientas', marca='SFI', activo=True,
        )
        macetero = Producto.objects.create(
            nombre='Macetero rectangular plÃ¡stico grafito',
            descripcion='Jardinera para plantas y hierbas.',
            precio=6990, stock=50, categoria='Otra', marca='SFI', activo=True,
        )

        from .services.asistente_sfi import _buscar_productos
        resultados = _buscar_productos('picota')

        ids = [producto.id for producto in resultados]
        self.assertIn(picota.id, ids)
        self.assertNotIn(macetero.id, ids)

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
    def test_alcance_rechaza_obras_mayores_sin_buscar_productos(self):
        for proyecto in (
            'Quiero construir una casa completa',
            'Construcción de segundo piso',
            'Demoler un muro soportante',
            'Instalación eléctrica completa de una vivienda',
        ):
            with self.subTest(proyecto=proyecto):
                resultado = _evaluar_alcance_proyecto({
                    'proyecto': proyecto,
                    '_contexto_usuario': proyecto,
                })
                self.assertEqual(resultado['tipo'], 'proyecto_fuera_de_alcance')
                self.assertFalse(resultado['productos'])

    def test_alcance_pide_confirmar_dimensiones_en_kilometros(self):
        resultado = _evaluar_alcance_proyecto({
            'proyecto': 'Radier',
            '_contexto_usuario': 'Quiero un radier de 25 x 25 km',
        })

        self.assertEqual(resultado['tipo'], 'confirmar_unidad_proyecto')
        self.assertIn('metros', resultado['mensaje'].casefold())
        self.assertFalse(resultado['productos'])

    def test_alcance_acepta_una_correccion_posterior_en_metros(self):
        resultado = _evaluar_alcance_proyecto({
            'proyecto': 'Radier',
            '_contexto_usuario': (
                'radier de 25 x 25 km; corrección: las medidas son 5 x 4 metros'
            ),
            'ancho_cm': 500,
            'fondo_cm': 400,
        })

        self.assertIsNone(resultado)

    def test_alcance_aplica_limites_segun_familia_de_proyecto(self):
        casos = (
            ('Radier', {'ancho_cm': 1000, 'fondo_cm': 610}, '60 m²'),
            ('Quincho', {'ancho_cm': 1000, 'fondo_cm': 510}, '50 m²'),
            ('Cambio de techumbre', {'ancho_cm': 1000, 'fondo_cm': 810}, '80 m²'),
            ('Revestimiento de muros', {'superficie_muros': 151}, '150 m²'),
            ('Cerco perimetral', {'ancho_cm': 6100}, '60 m'),
        )
        for proyecto, medidas, limite in casos:
            with self.subTest(proyecto=proyecto):
                resultado = _evaluar_alcance_proyecto({
                    'proyecto': proyecto,
                    '_contexto_usuario': proyecto,
                    **medidas,
                })
                self.assertEqual(resultado['tipo'], 'proyecto_fuera_de_alcance')
                self.assertIn(limite, resultado['mensaje'])

    def test_alcance_no_bloquea_reparacion_menor_en_una_casa(self):
        resultado = _evaluar_alcance_proyecto({
            'proyecto': 'Reparar techo de mi casa',
            '_contexto_usuario': 'Reparar 20 m² del techo de mi casa',
            'ancho_cm': 500,
            'fondo_cm': 400,
        })

        self.assertIsNone(resultado)

    def test_alcance_no_confunde_casa_para_mascota_con_vivienda(self):
        resultado = _evaluar_alcance_proyecto({
            'proyecto': 'Quiero hacer una casa para perro',
            '_contexto_usuario': 'Será una casa para perro de 1 x 1 metros',
            'ancho_cm': 100,
            'fondo_cm': 100,
            'alto_cm': 100,
        })

        self.assertIsNone(resultado)

    def test_alcance_permite_closet_mural_grande_de_5_por_6_metros(self):
        resultado = _evaluar_alcance_proyecto({
            'proyecto': 'Clóset mural a medida',
            '_contexto_usuario': 'Quiero un clóset de 5 x 6 metros',
            'ancho_cm': 500,
            'alto_cm': 600,
            'fondo_cm': 60,
        })

        self.assertIsNone(resultado)

    def test_alcance_mueble_conserva_un_limite_propio(self):
        resultado = _evaluar_alcance_proyecto({
            'proyecto': 'Clóset mural a medida',
            '_contexto_usuario': 'Quiero un clóset de 18 metros de ancho',
            'ancho_cm': 1800,
            'alto_cm': 260,
            'fondo_cm': 60,
        })

        self.assertEqual(resultado['tipo'], 'proyecto_fuera_de_alcance')
        self.assertIn('mobiliario a medida', resultado['mensaje'])
        self.assertIn('15 m', resultado['mensaje'])

    def test_piso_ceramico_estandar_con_ubicacion_avanza_con_supuestos(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Instalación de piso de cerámica para cocina',
            'modo_orientacion': 'propuesta_estandar',
            '_proyecto_estandar': True,
            '_contexto_usuario': 'quiero cerámica en una cocina de 4 x 5 metros',
            'ancho_cm': 400,
            'fondo_cm': 500,
            'tareas_proyecto': [{
                'nombre': 'Piso',
                'busquedas': ['porcelanato piso baño'],
            }],
            'datos_faltantes_proyecto': [],
        })

        self.assertEqual(resultado['tipo'], 'plan_proyecto_generico')
        self.assertIn('PROPUESTA ESTÁNDAR PARA TU PROYECTO', resultado['mensaje'])
        self.assertIn('Material actual de la base', resultado['mensaje'])
        self.assertTrue(resultado['productos'])

    def test_piso_ceramico_estandar_pregunta_ubicacion_antes_de_proponer(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Instalación de piso de cerámica estándar',
            '_proyecto_estandar': True,
            'modo_orientacion': 'propuesta_estandar',
            '_contexto_usuario': 'quiero un piso de cerámica estándar',
            'tareas_proyecto': [{
                'nombre': 'Piso',
                'busquedas': ['cerámica piso interior'],
            }],
            'datos_faltantes_proyecto': [],
        })

        self.assertEqual(resultado['tipo'], 'aclaracion_proyecto')
        self.assertIn('UBICACION DEL PISO', resultado['mensaje'])
        self.assertNotIn('BASE ACTUAL', resultado['mensaje'])
        self.assertFalse(resultado['productos'])

    def test_piso_ceramico_no_estandar_pide_ubicacion_medidas_base_y_estado(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Instalación de piso de cerámica',
            '_contexto_usuario': 'quiero hacer un piso de cerámica',
            'tareas_proyecto': [{
                'nombre': 'Piso',
                'busquedas': ['cerámica piso interior'],
            }],
            'datos_faltantes_proyecto': [],
        })

        self.assertEqual(resultado['tipo'], 'aclaracion_proyecto')
        self.assertIn('UBICACION DEL PISO', resultado['mensaje'])
        self.assertIn('Dimensiones o metros cuadrados', resultado['mensaje'])
        self.assertIn('BASE ACTUAL', resultado['mensaje'])
        self.assertIn('ESTADO DE LA BASE', resultado['mensaje'])
        self.assertFalse(resultado['productos'])

    def test_piso_ceramico_conserva_material_solicitado(self):
        Producto.objects.create(
            sku='CERAMICA-COCINA-TEST',
            nombre='Cerámica piso interior cocina caja 1,50 m²',
            descripcion='Cerámica para piso interior.',
            uso_recomendado='Revestimiento de piso interior.',
            precio=12000, stock=30, categoria='Construcción', activo=True,
        )
        Producto.objects.create(
            sku='PORCELANATO-BANO-TEST',
            nombre='Porcelanato piso baño gris caja 1,44 m²',
            descripcion='Porcelanato para piso de baño.',
            precio=18000, stock=30, categoria='Construcción', activo=True,
        )

        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Instalación de piso de cerámica para cocina',
            '_contexto_usuario': (
                'quiero cerámica en una cocina de 4 x 5 metros; '
                'la base es de hormigón firme, seca y nivelada'
            ),
            'ancho_cm': 400,
            'fondo_cm': 500,
            'tareas_proyecto': [{
                'nombre': 'Revestimiento',
                'busquedas': ['porcelanato piso baño'],
            }],
            'datos_faltantes_proyecto': [],
        })

        nombres = ' '.join(
            producto['nombre'].casefold() for producto in resultado['productos']
        )
        self.assertIn('cerámica piso interior cocina', nombres)
        self.assertNotIn('porcelanato piso baño', nombres)
        self.assertNotIn('guardapolvo', nombres)

    def test_piso_ceramico_recuerda_base_hormigon_y_pregunta_solo_estado(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Instalación de piso de cerámica',
            '_contexto_usuario': (
                'quiero hacer un piso de cerámica; '
                'base hormigón y la base es de 4 x 6 metros, es para cocina'
            ),
            'ancho_cm': 400,
            'fondo_cm': 600,
            'modo_orientacion': 'propuesta_estandar',
            'tareas_proyecto': [],
            'datos_faltantes_proyecto': ['Material y estado actual de la base o piso'],
        })

        self.assertEqual(resultado['tipo'], 'aclaracion_proyecto')
        mensaje = resultado['mensaje'].casefold()
        self.assertIn('estado de la base', mensaje)
        self.assertNotIn('base actual', mensaje)
        self.assertNotIn('superficie en metros cuadrados', mensaje)

    def test_piso_ceramico_acepta_base_es_un_hormigon_y_conserva_medidas_pendientes(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Instalación de piso de cerámica',
            '_contexto_usuario': (
                'quiero hacer un piso de cerámica; la base es un hormigón'
            ),
            'modo_orientacion': 'propuesta_estandar',
            'tareas_proyecto': [],
            'datos_faltantes_proyecto': [],
        })

        self.assertEqual(resultado['tipo'], 'aclaracion_proyecto')
        mensaje = resultado['mensaje'].casefold()
        self.assertIn('dimensiones o metros cuadrados', mensaje)
        self.assertIn('ubicacion del piso', mensaje)
        self.assertIn('estado de la base', mensaje)
        self.assertNotIn('base actual', mensaje)

    def test_piso_ceramico_no_confunde_revestimiento_con_base_actual(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Instalación de piso de cerámica',
            '_contexto_usuario': (
                'quiero piso de cerámica de 4 x 6 metros para cocina; '
                'está firme y nivelada'
            ),
            'ancho_cm': 400,
            'fondo_cm': 600,
            'modo_orientacion': 'propuesta_estandar',
            'tareas_proyecto': [],
            'datos_faltantes_proyecto': [],
        })

        mensaje = resultado['mensaje'].casefold()
        self.assertEqual(resultado['tipo'], 'aclaracion_proyecto')
        self.assertIn('base actual', mensaje)
        self.assertIn('humedad de la base', mensaje)

    def test_piso_ceramico_conserva_respuestas_parciales_del_cuestionario(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Instalación de piso de cerámica',
            '_contexto_usuario': (
                'quiero hacer un piso de cerámica; es para la cocina; '
                'la superficie actual es de hormigón; está firme, seca y '
                'nivelada; el piso mide 4 x 6 metros'
            ),
            'ancho_cm': 400,
            'fondo_cm': 600,
            'modo_orientacion': 'propuesta_estandar',
            'tareas_proyecto': [],
            'datos_faltantes_proyecto': [],
        })

        self.assertNotEqual(resultado['tipo'], 'aclaracion_proyecto')
        self.assertNotIn(
            'ANTES DE RECOMENDAR PRODUCTOS',
            resultado['mensaje'],
        )

    def test_piso_ceramico_pide_ubicacion_si_aun_no_se_indica(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Instalación de piso de cerámica',
            '_contexto_usuario': (
                'piso de cerámica de 4 x 6 metros sobre base de hormigón '
                'firme, seca y nivelada'
            ),
            'ancho_cm': 400,
            'fondo_cm': 600,
            'modo_orientacion': 'propuesta_estandar',
            'tareas_proyecto': [],
            'datos_faltantes_proyecto': [],
        })

        self.assertEqual(resultado['tipo'], 'aclaracion_proyecto')
        self.assertIn('ubicacion del piso', resultado['mensaje'].casefold())
        self.assertIn('Es para la cocina', resultado['sugerencias'])

    def test_ceramica_ambigua_pide_aplicacion_y_habitacion(self):
        datos = {
            'proyecto': 'Quiero instalar cerÃ¡mica',
            '_contexto_usuario': 'quiero instalar cerÃ¡mica',
            'datos_faltantes_proyecto': [],
        }

        _ajustar_proyecto_ceramica(datos, [])

        faltantes = ' '.join(datos['datos_faltantes_proyecto']).casefold()
        self.assertIn('piso o pared', faltantes)
        self.assertIn('habitacion', faltantes)

    def test_piso_ceramico_reconoce_hormigon_descrito_sin_nombre_tecnico(self):
        datos = {
            'proyecto': 'Piso de cerÃ¡mica',
            '_contexto_usuario': (
                'es para la cocina; el piso es de 2 x 3 metros; '
                'la superficie es gris dura y firme, esta seca y nivelada'
            ),
            'ancho_cm': 200,
            'fondo_cm': 300,
            'datos_faltantes_proyecto': [],
        }

        _ajustar_proyecto_ceramica(datos, [])

        faltantes = ' '.join(datos['datos_faltantes_proyecto']).casefold()
        self.assertTrue(datos['_ceramica_material_base'])
        self.assertEqual(
            datos['_ceramica_tipo_base'],
            'base_cementicia_probable',
        )
        self.assertTrue(datos['_ceramica_base_inferida'])
        self.assertNotIn('material actual', faltantes)
        self.assertFalse(datos['_ceramica_base_pendiente'])

    def test_piso_ceramico_distingue_tipos_de_base(self):
        casos = (
            ('sobre un radier firme seco y nivelado', 'hormigon_radier'),
            ('sobre una sobrelosa firme seca y nivelada', 'mortero_sobrelosa'),
            ('sobre ceramica existente firme seca y nivelada', 'ceramica_existente'),
            ('sobre base de madera OSB firme seca y nivelada', 'madera_osb'),
            ('sobre fibrocemento firme seco y nivelado', 'fibrocemento'),
        )
        for descripcion, esperado in casos:
            with self.subTest(descripcion=descripcion):
                datos = {
                    'proyecto': 'Piso de cerÃ¡mica para cocina',
                    '_contexto_usuario': (
                        f'piso de cerÃ¡mica para cocina de 2 x 3 metros {descripcion}'
                    ),
                    'ancho_cm': 200,
                    'fondo_cm': 300,
                    'datos_faltantes_proyecto': [],
                }

                _ajustar_proyecto_ceramica(datos, [])

                self.assertEqual(datos['_ceramica_tipo_base'], esperado)
                self.assertFalse(datos['_ceramica_base_pendiente'])

    def test_busqueda_ceramica_cambia_segun_aplicacion_y_ambiente(self):
        casos = (
            (
                'piso de cerÃ¡mica para baÃ±o sobre hormigÃ³n firme seco y nivelado',
                'ceramica piso bano zona humeda antideslizante',
            ),
            (
                'cerÃ¡mica para pared de cocina sobre hormigÃ³n firme seco y nivelado',
                'ceramica muro cocina',
            ),
        )
        for contexto, busqueda_esperada in casos:
            with self.subTest(contexto=contexto):
                datos = {
                    'proyecto': contexto,
                    '_contexto_usuario': f'{contexto}; mide 4 x 5 metros',
                    'ancho_cm': 400,
                    'fondo_cm': 500,
                    'datos_faltantes_proyecto': [],
                }
                tareas = _ajustar_proyecto_ceramica(datos, [])
                self.assertEqual(
                    tareas[0]['busquedas'][0],
                    busqueda_esperada,
                )

    def test_filtro_ceramica_no_mezcla_piso_bano_con_muro(self):
        piso = Producto.objects.create(
            sku='CER-PISO-BANO-FILTRO',
            nombre='CerÃ¡mica piso baÃ±o antideslizante prueba',
            descripcion='Piso para zona hÃºmeda.',
            uso_recomendado='Piso antideslizante para baÃ±o.',
            especificaciones={
                'AplicaciÃ³n': 'Piso',
                'Ambientes recomendados': ['BaÃ±o'],
                'Antideslizante': True,
            },
            precio=10000, stock=10, categoria='Otra', activo=True,
        )
        muro = Producto.objects.create(
            sku='CER-MURO-BANO-FILTRO',
            nombre='CerÃ¡mica muro baÃ±o prueba',
            descripcion='Revestimiento mural.',
            uso_recomendado='Muro interior de baÃ±o.',
            especificaciones={
                'AplicaciÃ³n': 'Muro',
                'Ambientes recomendados': ['BaÃ±o'],
                'Antideslizante': False,
            },
            precio=10000, stock=10, categoria='Otra', activo=True,
        )
        datos = {
            '_ceramica_aplicacion': 'piso',
            '_ceramica_ambiente': 'bano',
            '_ceramica_requiere_antideslizante': True,
        }

        self.assertTrue(_producto_compatible_con_revestimiento_ceramico(
            piso, datos, 'ceramica piso bano antideslizante',
        ))
        self.assertFalse(_producto_compatible_con_revestimiento_ceramico(
            muro, datos, 'ceramica piso bano antideslizante',
        ))

    def test_herramientas_ceramica_se_relacionan_con_cada_etapa(self):
        herramientas = (
            ('HERR-CER-LLANA', 'Llana dentada acero 10 mm'),
            ('HERR-CER-CORTE', 'Cortadora manual porcelanato 600 mm'),
            ('HERR-CER-NIVEL', 'Nivel de burbuja aluminio 60 cm'),
            ('HERR-CER-MAZO', 'Mazo de goma para cerámica 16 oz'),
            ('HERR-CER-BALDE', 'Balde flexible para mezcla pisos 28 litros'),
            ('HERR-CER-GOMA', 'Llana de goma para fragüe 20 cm'),
            ('HERR-CER-ESPONJA', 'Esponja para limpieza de fragüe'),
            ('HERR-CER-DISCO', 'Disco diamantado continuo porcelanato 115 mm'),
        )
        for sku, nombre in herramientas:
            Producto.objects.create(
                sku=sku, nombre=nombre,
                descripcion='Herramienta para instalación de cerámica.',
                uso_recomendado='Uso específico en colocación de pisos.',
                precio=5000, stock=10, categoria='Herramientas', activo=True,
            )

        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Instalación de piso de cerámica para cocina',
            '_contexto_usuario': (
                'piso cerámico de cocina sobre base de hormigón firme; '
                'qué herramientas necesito'
            ),
            '_consulta_solo_herramientas': True,
            'incluir_herramientas': True,
            'tareas_proyecto': [],
            'datos_faltantes_proyecto': [],
        })

        self.assertEqual(resultado['tipo'], 'seguimiento_herramientas')
        nombres = ' '.join(
            producto['nombre'].casefold() for producto in resultado['productos']
        )
        for esperado in ('llana dentada', 'cortadora manual', 'nivel de burbuja',
                         'mazo de goma', 'balde flexible', 'llana de goma', 'esponja',
                         'disco diamantado'):
            self.assertIn(esperado, nombres)
        self.assertNotIn('taladro percutor', nombres)
        mensaje = resultado['mensaje'].casefold()
        self.assertIn('peinar el adhesivo', mensaje)
        self.assertIn('realizar cortes rectos', mensaje)

    def test_preguntas_guiadas_no_solicitan_fotografias(self):
        from .services.planificador_proyectos import (
            _preguntas_guiadas,
            _sugerencias_respuesta,
        )

        preguntas = _preguntas_guiadas([
            'material y estado de la estructura',
            'resultado esperado',
        ], 'Reparación de estructura')
        sugerencias = _sugerencias_respuesta(
            'Proyecto general',
            ['material de la superficie'],
        )
        contenido = ' '.join([*preguntas, *sugerencias]).casefold()

        self.assertNotIn('foto', contenido)
        self.assertNotIn('adjunt', contenido)

    def test_porton_electrico_estandar_muestra_sistema_y_faltantes(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Instalación de portón exterior eléctrico estándar',
            'modo_orientacion': 'propuesta_estandar',
            '_proyecto_estandar': True,
            'tareas_proyecto': [{
                'nombre': 'Automatización',
                'busquedas': ['motor porton corredera hasta 600 kg'],
            }],
            'herramientas_proyecto': ['soldadora inverter', 'esmeril angular'],
            'datos_faltantes_proyecto': [],
        })

        roles = {producto['rol'] for producto in resultado['productos']}
        nombres = ' '.join(
            producto['nombre'].casefold() for producto in resultado['productos']
        )
        faltantes = ' '.join(resultado['faltantes_catalogo']).casefold()

        self.assertIn('Estructura y anclaje', roles)
        self.assertIn('Automatización y seguridad', roles)
        self.assertIn('Alimentación y protección eléctrica', roles)
        self.assertIn('fotocelda', nombres)
        self.assertIn('conduit', nombres)
        self.assertIn('hoja porton corredera vehicular', faltantes)
        self.assertIn('riel porton corredera', faltantes)
        self.assertIn('rueda porton corredera', faltantes)
        etapas = {tarea['nombre'] for tarea in resultado['tareas']}
        self.assertIn('Herramientas recomendadas', etapas)
        self.assertTrue(all(
            item['etapa'] and item['uso']
            for item in resultado['faltantes_catalogo_detalle']
        ))
        self.assertIn('también se usan para completar', resultado['mensaje'])
        self.assertIn('instalador eléctrico autorizado', resultado['mensaje'])

    def test_pergola_madera_sobre_radier_cubre_estructura_sombra_y_proteccion(self):
        for indice, nombre in enumerate((
            'Perno anclaje expansión M12 x 120 mm pack 4',
            'Pino dimensionado 2 x 4 pulgadas x 3,2 m',
            'Pino dimensionado 2 x 6 pulgadas x 3,20 m',
            'Tornillo estructural para madera 6 x 100 mm pack 50',
            'Escuadra metálica reforzada 50 x 50 mm pack 4',
            'Malla raschel sombra 80% verde rollo 2 x 10 m',
            'Barniz al agua para madera satinado 1 litro',
        ), start=1):
            Producto.objects.create(
                sku=f'PERGOLA-PRUEBA-{indice}', nombre=nombre,
                descripcion='Producto para propuesta de pérgola.', precio=1000 + indice,
                stock=10, categoria='Construcción', activo=True,
            )

        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Construcción de pérgola de madera 3 x 4 metros para dar sombra',
            'tareas_proyecto': [], 'herramientas_proyecto': [],
            'datos_faltantes_proyecto': [],
        })

        roles = {producto['rol'] for producto in resultado['productos']}
        nombres = ' '.join(producto['nombre'].casefold() for producto in resultado['productos'])
        self.assertTrue({
            'Anclaje de pilares', 'Pilares y vigas de madera',
            'Uniones estructurales', 'Sombra y protección',
        }.issubset(roles))
        self.assertIn('malla raschel', nombres)
        self.assertIn('barniz', nombres)

    def test_pergola_desde_cero_agrega_fundaciones_y_no_reporta_madera_faltante(self):
        for indice, nombre in enumerate((
            'Base estabilizada para radier saco 25 kg',
            'Hormigón predosificado H20 saco 25 kg',
            'Clavo corriente 4 pulgadas (1 kg)',
            'Pino dimensionado 2 x 4 pulgadas x 3,2 m',
            'Pino dimensionado 2 x 6 pulgadas x 3,20 m',
        ), start=1):
            Producto.objects.create(
                sku=f'PERGOLA-CERO-{indice}', nombre=nombre,
                descripcion='Material para propuesta de pérgola desde cero.',
                precio=1000 + indice, stock=10, categoria='Construcción', activo=True,
            )

        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Construcción de pérgola estándar',
            'material_principal_proyecto': 'madera dimensionada',
            '_proyecto_estandar': True,
            '_parte_desde_cero': True,
            'tareas_proyecto': [], 'herramientas_proyecto': [],
            'datos_faltantes_proyecto': [],
        })

        roles = {producto['rol'] for producto in resultado['productos']}
        nombres = ' '.join(producto['nombre'].casefold() for producto in resultado['productos'])
        faltantes = ' '.join(resultado['faltantes_catalogo']).casefold()
        self.assertIn('Fundaciones de pilares', roles)
        self.assertIn('Herramientas recomendadas', roles)
        self.assertIn('base estabilizada', nombres)
        self.assertIn('hormigón predosificado', nombres)
        self.assertIn('pino dimensionado', nombres)
        self.assertNotIn('madera dimensionada', faltantes)

    def test_bodega_desde_cero_con_luz_agrega_fundaciones_e_iluminacion(self):
        for indice, nombre in enumerate((
            'Base estabilizada para radier saco 25 kg',
            'Hormigón predosificado H20 saco 25 kg',
            'Polietileno construcción 200 micras 4 x 25 m',
            'Portalámpara E27 sobrepuesto blanco',
            'Ampolleta LED E27 9 W luz neutra',
            'Interruptor simple 10 A 250 V blanco',
            'Cable eléctrico 1,5 mm² rollo 100 m',
            'Conduit PVC eléctrico 20 mm x 3 m',
        ), start=1):
            Producto.objects.create(
                sku=f'BODEGA-LUZ-{indice}', nombre=nombre,
                descripcion='Material para bodega exterior con luz interior.',
                precio=1000 + indice, stock=10, categoria='Construcción', activo=True,
            )

        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Construcción bodega exterior estándar de 3 x 4 metros',
            '_proyecto_estandar': True,
            '_parte_desde_cero': True,
            '_contexto_usuario': 'parto desde cero, suelo de tierra y quiero una luz interior',
            'tareas_proyecto': [], 'herramientas_proyecto': [],
            'datos_faltantes_proyecto': [],
        })

        roles = {producto['rol'] for producto in resultado['productos']}
        nombres = ' '.join(producto['nombre'].casefold() for producto in resultado['productos'])
        self.assertIn('Preparación y fundaciones', roles)
        self.assertIn('Iluminación interior', roles)
        self.assertIn('portalámpara', nombres)
        self.assertIn('ampolleta', nombres)
        self.assertIn('interruptor simple', nombres)

    def test_componente_generico_de_gemini_se_traduce_a_producto_real_catalogo(self):
        Producto.objects.create(
            sku='PINO-EQUIV-PRUEBA',
            nombre='Pino dimensionado 2 x 4 pulgadas x 3,2 m',
            descripcion='Madera estructural para pilares y vigas.',
            precio=8990, stock=12, categoria='Construcción', activo=True,
        )

        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Estructura liviana de madera',
            'tareas_proyecto': [{
                'nombre': 'Estructura',
                'busquedas': ['madera dimensionada'],
                'usos_materiales': ['Formar pilares y vigas principales.'],
            }],
            'herramientas_proyecto': [], 'datos_faltantes_proyecto': [],
        })

        nombres = ' '.join(producto['nombre'].casefold() for producto in resultado['productos'])
        self.assertIn('pino dimensionado', nombres)
        self.assertNotIn('madera dimensionada', ' '.join(resultado['faltantes_catalogo']).casefold())

    def test_zinc_ondulado_de_gemini_encuentra_plancha_zinc_acanalado_del_catalogo(self):
        Producto.objects.create(
            sku='ZINC-EQUIV-PRUEBA',
            nombre='Plancha zinc acanalado 0,35 mm x 3 m',
            descripcion='Cubierta metálica para techumbre.',
            precio=15990, stock=12, categoria='Construcción', activo=True,
        )

        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Cobertizo de madera',
            'tareas_proyecto': [{
                'nombre': 'Cubierta',
                'busquedas': ['plancha de zinc ondulado'],
                'usos_materiales': ['Cubrir la techumbre del cobertizo.'],
            }],
            'herramientas_proyecto': [], 'datos_faltantes_proyecto': [],
        })

        nombres = ' '.join(producto['nombre'].casefold() for producto in resultado['productos'])
        faltantes = ' '.join(resultado['faltantes_catalogo']).casefold()
        self.assertIn('plancha zinc acanalado', nombres)
        self.assertNotIn('zinc ondulado', faltantes)

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

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_consulta_inicial_de_herramientas_para_pintar_no_inicia_calculo(self, interpretar):
        rodillo = Producto.objects.create(
            nombre='Rodillo pintura muros prueba',
            descripcion='Herramienta para aplicar pintura en muros.',
            precio=5990,
            stock=10,
            categoria='Herramientas',
            activo=True,
        )
        brocha = Producto.objects.create(
            nombre='Brocha pintura 2 pulgadas prueba',
            descripcion='Herramienta para recortes y bordes.',
            precio=3990,
            stock=10,
            categoria='Herramientas',
            activo=True,
        )
        interpretar.return_value = {
            'intencion': 'planificar_proyecto',
            'proyecto': 'Pintar una pared',
            'tareas_proyecto': [],
            'herramientas_proyecto': ['rodillo pintura', 'brocha pintura'],
            'incluir_herramientas': True,
            'datos_faltantes_proyecto': [],
        }

        resultado = procesar_consulta(
            'QUE HERAMIENTAS NECESITO PARA PINTAR UNA PARED',
            [],
        )

        interpretar.assert_called_once()
        self.assertEqual(resultado['tipo'], 'seguimiento_herramientas')
        nombres = [producto['nombre'].casefold() for producto in resultado['productos']]
        self.assertTrue(any('rodillo' in nombre for nombre in nombres))
        self.assertTrue(any('brocha' in nombre for nombre in nombres))
        self.assertTrue(all(
            'herramienta' in producto['rol'].casefold()
            for producto in resultado['productos']
        ))
        self.assertNotIn('metros cuadrados', resultado['mensaje'].casefold())

    def test_materiales_y_herramientas_pasan_al_planificador_completo(self):
        from .services.asistente_sfi import (
            _clasificar_seguimiento_natural,
            _normalizar_preferencias_extraidas,
            _resolver_accion_seguimiento,
            _resolver_herramientas_iniciales,
        )

        consulta = (
            'Quiero instalar dos enchufes y una luz en una bodega de 3 x 4 metros. '
            'Necesito conduit PVC de 20 mm. ¿Qué materiales y herramientas necesito?'
        )
        resultado = _resolver_herramientas_iniciales(consulta)

        self.assertIsNone(resultado)
        self.assertEqual(
            _clasificar_seguimiento_natural(consulta, [self.madera.pk]),
            '',
        )
        self.assertIsNone(
            _resolver_accion_seguimiento(consulta, [self.madera.pk])
        )
        datos = _normalizar_preferencias_extraidas(
            {'intencion': 'planificar_proyecto', 'incluir_herramientas': True},
            consulta,
            [],
        )
        self.assertFalse(datos['_consulta_solo_herramientas'])
        self.assertTrue(datos['incluir_herramientas'])

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_herramientas_para_retirar_tierra_se_interpretan_por_proyecto(self, interpretar):
        interpretar.return_value = {
            'intencion': 'planificar_proyecto',
            'proyecto': 'Retiro manual de tierra en patio',
            'tareas_proyecto': [],
            # Gemini puede devolver una descripciÃ³n amplia; el backend la
            # traduce al conjunto de herramientas de tierra del catÃ¡logo.
            'herramientas_proyecto': ['herramientas manuales'],
            'incluir_herramientas': True,
            'datos_faltantes_proyecto': [],
        }

        resultado = procesar_consulta(
            'Quiero sacar tierra de mi patio, ¿qué herramientas necesito?',
            [],
        )

        interpretar.assert_called_once()
        self.assertEqual(resultado['tipo'], 'seguimiento_herramientas')
        nombres = ' '.join(
            producto['nombre'].casefold() for producto in resultado['productos']
        )
        self.assertIn('pala punta', nombres)
        self.assertIn('picota jardinera', nombres)
        self.assertIn('carretilla acero', nombres)
        self.assertNotIn('taladro', nombres)
        self.assertNotIn('cinta metrica', nombres)


    def test_cliente_gemini_reintenta_errores_temporales(self):
        adaptador = cliente_gemini.session.get_adapter(
            'https://generativelanguage.googleapis.com/'
        )

        self.assertEqual(adaptador.max_retries.total, 0)
        self.assertIn(503, adaptador.max_retries.status_forcelist)
        self.assertIn('POST', adaptador.max_retries.allowed_methods)

    @patch('asistente.services.gemini.time.sleep')
    @patch('asistente.services.gemini.cliente_gemini.post')
    def test_gemini_reintenta_con_espera_progresiva(self, post, dormir):
        temporal = Mock(status_code=503)
        exitosa = Mock(status_code=200)
        post.side_effect = [temporal, exitosa]

        respuesta = _solicitar_gemini_con_reintentos(
            'https://generativelanguage.googleapis.com/v1beta/models/prueba:generateContent',
            headers={'x-goog-api-key': 'clave'}, payload={}, timeout=45,
        )

        self.assertIs(respuesta, exitosa)
        self.assertEqual(post.call_count, 2)
        dormir.assert_called_once_with(2)

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_filtracion_desconocida_en_lavaplatos_pide_diagnostico(self, interpretar):
        resultado = procesar_consulta(
            'Se me rompió el lavaplatos. Está filtrando agua por debajo y no sé qué pieza falla. '
            '¿Qué materiales o herramientas podría necesitar?',
            [],
        )

        interpretar.assert_not_called()
        self.assertEqual(resultado['tipo'], 'seguimiento_proyecto')
        self.assertEqual(resultado['productos'], [])
        self.assertIn('PRIMERO IDENTIFIQUEMOS', resultado['mensaje'])
        self.assertIn('Sifón o tubo de desagüe', resultado['mensaje'])
        self.assertNotIn('martillo', resultado['mensaje'].casefold())

    def test_filtracion_identificada_en_sifon_continua_al_planificador(self):
        from .services.asistente_sfi import _resolver_diagnostico_filtracion_inicial

        resultado = _resolver_diagnostico_filtracion_inicial(
            'La fuga viene del sifón o desagüe del lavaplatos.'
        )

        self.assertIsNone(resultado)

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_respuesta_llave_conserva_contexto_de_filtracion(self, interpretar):
        interpretar.return_value = {
            'intencion': 'orientacion',
            'respuesta': 'Revisaremos la llave y sus conexiones.',
        }
        historial = [{
            'role': 'assistant',
            'content': (
                'PRIMERO IDENTIFIQUEMOS LA FILTRACIÓN\n'
                'Indícame cuál de estas opciones coincide: sifón, flexible, llave o borde.'
            ),
        }]

        procesar_consulta('llave', historial)

        mensaje_enviado = interpretar.call_args.args[0]
        self.assertIn('CONTINÚA EL PROYECTO', mensaje_enviado)
        self.assertIn('Respuesta breve del cliente: llave', mensaje_enviado)

    def test_respuesta_breve_sin_guia_no_inventa_contexto(self):
        from .services.asistente_sfi import _mensaje_para_continuar_guia

        self.assertEqual(
            _mensaje_para_continuar_guia(
                'llave',
                [{'role': 'assistant', 'content': '¿En qué puedo ayudarte?'}],
            ),
            'llave',
        )

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_campana_para_quincho_es_busqueda_de_producto(self, interpretar):
        resultado = procesar_consulta('CAMPANA PARA QUINCHO ?', [])

        interpretar.assert_not_called()
        self.assertIn(resultado['tipo'], {'busqueda', 'sin_resultados'})
        self.assertNotIn('ANTES DE RECOMENDAR PRODUCTOS', resultado['mensaje'])
        self.assertNotIn('dimensiones', resultado['mensaje'].casefold())

    def test_pregunta_generica_de_materiales_no_se_reduce_a_producto(self):
        from .services.asistente_sfi import _resolver_producto_breve

        self.assertIsNone(
            _resolver_producto_breve('¿Qué materiales necesito para un quincho?')
        )

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

    def test_mueble_estandar_entrega_referencia_sin_cuestionario(self):
        Producto.objects.create(
            nombre='Plancha melamina blanca 18 mm 1,83 x 2,50 m',
            descripcion='Tablero para fabricar muebles de interior.',
            uso_recomendado='Cuerpo y divisiones de muebles.',
            precio=39990,
            stock=12,
            categoria='Maderas y tableros',
            activo=True,
        )
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Fabricar mueble de melamina estándar',
            '_proyecto_estandar': True,
            'tareas_proyecto': [{
                'nombre': 'Fabricación',
                'busquedas': ['plancha melamina blanca 18 mm'],
            }],
            'datos_faltantes_proyecto': [
                'Tipo y uso del mueble',
                'Dimensiones del espacio disponible',
            ],
        })

        self.assertEqual(resultado['tipo'], 'plan_proyecto_generico')
        self.assertTrue(resultado['productos'])
        self.assertIn('PROPUESTA ESTÁNDAR PARA TU PROYECTO', resultado['mensaje'])
        self.assertIn('SUPUESTOS DE LA PROPUESTA ESTÁNDAR', resultado['mensaje'])
        self.assertIn('Tipo y uso del mueble', resultado['mensaje'])
        self.assertNotIn('ANTES DE RECOMENDAR PRODUCTOS', resultado['mensaje'])

    def test_estandar_no_se_confunde_con_referencia_esta(self):
        from .services.asistente_sfi import _aplicar_contexto_productos

        datos = {
            'intencion': 'planificar_proyecto',
            'proyecto': 'Fabricar mueble de melamina estándar',
        }
        resultado = _aplicar_contexto_productos(
            datos,
            'Quiero un mueble de melamina estándar',
            [self.madera.pk, self.tornillos.pk],
        )

        self.assertEqual(resultado['intencion'], 'planificar_proyecto')
        self.assertNotIn('_contexto_ambiguo', resultado)

    def test_mueble_estandar_con_tipo_y_tres_medidas_puede_avanzar(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Escritorio estándar de melamina',
            '_proyecto_estandar': True,
            'ancho_cm': 120,
            'alto_cm': 75,
            'fondo_cm': 60,
            'tareas_proyecto': [{
                'nombre': 'Cuerpo del escritorio',
                'busquedas': ['plancha melamina blanca 18 mm'],
                'usos_materiales': [{
                    'busqueda': 'plancha melamina blanca 18 mm',
                    'uso': 'Formar la cubierta y los apoyos del escritorio.',
                }],
            }],
            'datos_faltantes_proyecto': [],
        })

        self.assertEqual(resultado['tipo'], 'plan_proyecto_generico')
        self.assertTrue(resultado['productos'])
        self.assertNotIn('TIPO Y USO DEL MUEBLE', resultado['mensaje'])

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
    def test_proyecto_libre_incompleto_pide_medidas_antes_de_recomendar(self, interpretar):
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

        self.assertEqual(resultado['tipo'], 'aclaracion_proyecto')
        self.assertEqual(resultado['productos'], [])
        self.assertIn('ancho', resultado['mensaje'].casefold())
        self.assertIn('alto', resultado['mensaje'].casefold())
        self.assertIn('profundidad', resultado['mensaje'].casefold())

    def test_proyecto_libre_completo_usa_catalogo_y_maestro_aprobado(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Casita de madera exterior para perro',
            'ancho_cm': 100,
            'alto_cm': 110,
            'fondo_cm': 120,
            'tareas_proyecto': [
                {'nombre': 'Construir la estructura', 'busquedas': [
                    'pino dimensionado exterior', 'tornillos para madera',
                ]},
                {'nombre': 'Proteger contra la lluvia', 'busquedas': [
                    'barniz madera exterior',
                ]},
            ],
            'herramientas_proyecto': [],
            'especialidades_proyecto': ['Carpintería'],
            'datos_faltantes_proyecto': [],
            'comuna_maestro': 'Maipú',
        })

        self.assertEqual(resultado['tipo'], 'plan_proyecto_generico')
        self.assertEqual(len(resultado['productos']), 3)
        self.assertTrue(all(producto['stock'] > 0 for producto in resultado['productos']))
        self.assertTrue(all(producto.get('uso_en_proyecto') for producto in resultado['productos']))
        self.assertEqual(resultado['especialidades'], ['Carpintería'])
        self.assertEqual([maestro['id'] for maestro in resultado['maestros']], [self.perfil.id])

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
        self.assertTrue(all(
            producto.get('uso_en_proyecto')
            for producto in resultado['productos']
        ))
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
        self.assertGreaterEqual(len(resultado['tareas']), 5)
        self.assertGreaterEqual(
            len(resultado['productos']) + len(resultado['faltantes_catalogo']),
            12,
        )
        self.assertIn('PROPUESTA ESTÁNDAR PARA TU PROYECTO', resultado['mensaje'])
        self.assertNotIn('ANTES DE RECOMENDAR PRODUCTOS', resultado['mensaje'])

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_instalar_campana_en_quincho_no_activa_obra_completa(self, interpretar):
        interpretar.return_value = {
            'intencion': 'planificar_proyecto',
            'modo_orientacion': 'propuesta_estandar',
            'proyecto': 'Instalación de campana para quincho',
            'tareas_proyecto': [{
                'nombre': 'Extracción de humo',
                'busquedas': ['campana humo quincho', 'ducto chimenea quincho'],
            }],
            'datos_faltantes_proyecto': [],
        }

        resultado = procesar_consulta(
            'Quiero instalar una campana para quincho, ¿qué necesito?', [],
        )

        self.assertEqual(resultado['tipo'], 'plan_proyecto_generico')
        self.assertEqual(len(resultado['tareas']), 1)
        self.assertIn('campana humo quincho', resultado['faltantes_catalogo'])
        self.assertNotIn('radier', resultado['mensaje'].casefold())
        self.assertNotIn('ladrillo refractario', resultado['mensaje'].casefold())

    def test_explicacion_incluye_mas_de_ocho_productos_mostrados(self):
        from .services.asistente_sfi import _explicar_productos_mostrados

        productos = [self.madera, self.tornillos, self.barniz]
        for indice in range(6):
            productos.append(Producto.objects.create(
                nombre=f'Material complementario quincho {indice + 1}',
                descripcion=f'Función del material complementario {indice + 1}.',
                precio=1000 + indice,
                stock=5,
                categoria='Construcción',
                activo=True,
            ))

        resultado = _explicar_productos_mostrados(
            '¿Por qué elegiste estos materiales?',
            [],
            [producto.id for producto in productos],
        )

        self.assertEqual(resultado['tipo'], 'explicacion_proyecto')
        for producto in productos:
            self.assertIn(producto.nombre, resultado['mensaje'])

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_pregunta_para_que_sirve_usa_la_ficha_del_producto(self, interpretar):
        interpretar.return_value = {
            'respuesta': (
                'Úsala en reparaciones interiores pequeñas y respeta la preparación '
                'indicada en la ficha antes de aplicar el acabado final.'
            ),
        }
        producto = Producto.objects.create(
            nombre='Pasta de retape de prueba 1 kg',
            descripcion='Producto de prueba para muros interiores.',
            uso_recomendado=(
                'Rellenar grietas, agujeros e imperfecciones pequeñas en muros '
                'interiores antes de lijar y pintar.'
            ),
            precio=4990,
            stock=12,
            categoria='Adhesivos',
            especificaciones={'Uso': 'Interior', 'Aplicación': 'Espátula'},
            activo=True,
        )

        resultado_inicial = procesar_consulta(
            'Pasta de retape de prueba 1 kg para quje sirve?', [],
        )
        resultado_contextual = procesar_consulta(
            'Cual es su funcion?', [], [producto.id],
        )
        resultado_plural = procesar_consulta(
            'Pasta de retape de prueba 1 kg para que sirven?', [],
        )
        resultado_con_errores = procesar_consulta(
            'Pasta de retape de prueba 1 kg pa q sirbe', [],
        )
        resultado_que_es = procesar_consulta(
            'Pasta de retape de prueba 1 kg que es', [],
        )

        for resultado in (
            resultado_inicial, resultado_contextual, resultado_plural,
            resultado_con_errores, resultado_que_es,
        ):
            self.assertEqual(resultado['tipo'], 'uso_producto')
            self.assertIn('PARA QUÉ SIRVE', resultado['mensaje'])
            self.assertIn(producto.nombre, resultado['mensaje'])
            self.assertIn('Rellenar grietas', resultado['mensaje'])
            self.assertIn('USO RECOMENDADO', resultado['mensaje'])
            self.assertIn('FICHA TÉCNICA', resultado['mensaje'])
            self.assertIn('Categoría: Adhesivos', resultado['mensaje'])
            self.assertIn('Aplicación: Espátula', resultado['mensaje'])
            self.assertIn('ORIENTACIÓN DEL ASISTENTE', resultado['mensaje'])
            self.assertEqual(resultado['productos'], [])

        self.assertEqual(interpretar.call_count, 5)

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_producto_especifico_se_explica_en_proyecto_con_mas_de_18_productos(
        self, interpretar,
    ):
        interpretar.return_value = {'respuesta': 'Permite verificar medidas.'}
        productos = [
            Producto.objects.create(
                nombre=f'Material de proyecto {indice}',
                descripcion='Material auxiliar del proyecto.',
                precio=1000 + indice,
                stock=10,
                categoria='Construcción',
                activo=True,
            )
            for indice in range(22)
        ]
        cinta = Producto.objects.create(
            nombre='Cinta métrica Stanley Pro 8 m / 26 pies',
            descripcion='Cinta métrica para medir longitudes.',
            uso_recomendado='Verificar dimensiones y alineación antes de trabajar.',
            precio=12990,
            stock=25,
            categoria='Herramientas',
            activo=True,
        )

        resultado = procesar_consulta(
            'Cinta métrica Stanley Pro 8 m / 26 pies para que sirve?',
            [{'role': 'assistant', 'content': 'Propuesta estándar de proyecto.'}],
            [producto.pk for producto in productos] + [cinta.pk],
        )

        self.assertEqual(resultado['tipo'], 'uso_producto')
        self.assertIn(cinta.nombre, resultado['mensaje'])
        self.assertIn('Verificar dimensiones', resultado['mensaje'])

    def test_serializer_acepta_contexto_de_proyecto_extenso(self):
        serializer = ConsultaAsistenteSerializer(data={
            'mensaje': 'Cinta métrica para que sirve?',
            'productos_contexto': list(range(1, 24)),
            'estimacion_contexto': [
                {'id': indice, 'nombre': f'Producto {indice}'}
                for indice in range(1, 24)
            ],
        })

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(len(serializer.validated_data['productos_contexto']), 23)
        self.assertEqual(len(serializer.validated_data['estimacion_contexto']), 23)

    def test_pregunta_de_uso_prioriza_el_nombre_exacto_sobre_accesorios(self):
        from .services.asistente_sfi import _producto_mencionado_para_uso

        gotero = Producto.objects.create(
            nombre='Gotero regulable prueba pack 10',
            descripcion='Entrega agua de forma localizada.',
            precio=3990,
            stock=20,
            categoria='Jardinería',
            activo=True,
        )
        accesorio = Producto.objects.create(
            nombre='Tee para riego por goteo prueba pack 10',
            descripcion='Conector para ramales de riego.',
            precio=3490,
            stock=20,
            categoria='Jardinería',
            activo=True,
        )

        seleccion = _producto_mencionado_para_uso(
            'Gotero regulable prueba pack 10', [gotero, accesorio],
        )

        self.assertEqual(seleccion, [gotero])

    def test_pregunta_de_uso_policarbonato_prioriza_cubierta_sobre_accesorios(self):
        from .services.asistente_sfi import _producto_mencionado_para_uso

        cubierta = Producto.objects.create(
            nombre='Policarbonato alveolar de prueba 6 mm',
            descripcion='Cubierta liviana para exteriores.',
            precio=32990,
            stock=12,
            categoria='Construcción',
            activo=True,
        )
        perfil = Producto.objects.create(
            nombre='Perfil U para policarbonato de prueba',
            descripcion='Accesorio de terminación.',
            precio=6490,
            stock=12,
            categoria='Construcción',
            activo=True,
        )
        lentes = Producto.objects.create(
            nombre='Lentes de seguridad policarbonato de prueba',
            descripcion='Protección visual.',
            precio=3490,
            stock=12,
            categoria='Herramientas',
            activo=True,
        )

        seleccion = _producto_mencionado_para_uso(
            'policarbonato', [perfil, lentes, cubierta],
        )

        self.assertEqual(seleccion, [cubierta])

    def test_busqueda_respeta_medidas_decimales_con_coma_en_ficha(self):
        from .services.asistente_sfi import _buscar_productos

        producto = Producto.objects.create(
            nombre='Policarbonato ondulado de prueba 0,8 mm 0,90 x 2,80 m',
            descripcion='Cubierta liviana para exteriores.',
            uso_recomendado='Cubiertas livianas con pendiente adecuada.',
            precio=22990,
            stock=10,
            categoria='Construcción',
            activo=True,
        )

        resultados = _buscar_productos(
            'Policarbonato ondulado de prueba 0,8 mm 0,90 x 2,80 m', limite=20,
        )

        self.assertIn(producto, resultados)

    def test_busqueda_por_funcion_encuentra_producto_sin_conocer_su_nombre(self):
        producto = Producto.objects.create(
            nombre='Pasta de retape funcional 1 kg',
            descripcion='Rellena grietas y pequeñas imperfecciones en muros interiores.',
            uso_recomendado='Preparar muros interiores antes de lijar y pintar.',
            precio=4990,
            stock=12,
            categoria='Adhesivos',
            activo=True,
        )

        resultado = procesar_consulta('¿Qué sirve para tapar grietas?', [])

        self.assertEqual(resultado['tipo'], 'productos')
        self.assertIn(producto.id, [item['id'] for item in resultado['productos']])

    def test_chuzo_y_barretin_encuentran_la_barreta_del_catalogo(self):
        from .services.asistente_sfi import _buscar_productos

        barreta = Producto.objects.create(
            nombre='Barreta de acero de prueba 1,2 m',
            descripcion='Palanca manual para remover tierra o piedras.',
            precio=15990,
            stock=10,
            categoria='Herramientas',
            activo=True,
        )

        for consulta in ('chuzo', 'barretin'):
            resultados = _buscar_productos(consulta)
            self.assertIn(barreta, resultados)

    def test_tutor_reconoce_tijera_de_poda_y_no_duplica_palas(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Tutor para plantas',
            'modo_orientacion': 'propuesta_estandar',
            'tareas_proyecto': [
                {
                    'nombre': 'Preparación y soporte',
                    'busquedas': ['tutor bambu 1,2 m pack 10'],
                },
                {
                    'nombre': 'Herramientas',
                    'busquedas': ['pala punta acero mango fibra', 'tijeras de podar'],
                },
                {
                    'nombre': 'Herramientas recomendadas',
                    'busquedas': ['pala punta huevo mango fibra'],
                },
            ],
            'herramientas_proyecto': [],
            'datos_faltantes_proyecto': [],
        })

        nombres = [producto['nombre'].casefold() for producto in resultado['productos']]
        self.assertTrue(any('tijera de poda' in nombre for nombre in nombres))
        self.assertEqual(sum('pala ' in nombre for nombre in nombres), 1)
        self.assertFalse(any(
            'tijeras de podar' in faltante.casefold()
            for faltante in resultado['faltantes_catalogo']
        ))

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_bodega_estandar_completa_etapas_y_declara_faltantes(self, interpretar):
        interpretar.return_value = {
            'intencion': 'planificar_proyecto',
            'proyecto': 'Construcción de bodega exterior estándar',
            'modo_orientacion': 'propuesta_estandar',
            'ancho_cm': 300,
            'fondo_cm': 400,
            'tareas_proyecto': [{
                'nombre': 'Estructura',
                'busquedas': ['pino dimensionado 2 x 4 pulgadas'],
            }],
            'datos_faltantes_proyecto': [],
        }

        resultado = procesar_consulta(
            'Quiero construir una bodega exterior estándar de 3 x 4 metros.',
            [],
        )

        self.assertEqual(resultado['tipo'], 'plan_proyecto_generico')
        self.assertEqual(len(resultado['tareas']), 6)
        self.assertEqual(
            len(resultado['productos']) + len(resultado['faltantes_catalogo']),
            18,
        )
        self.assertIn('Acceso y seguridad', {
            tarea['nombre'] for tarea in resultado['tareas']
        })
        self.assertTrue(all(
            item['uso'] for item in resultado['faltantes_catalogo_detalle']
        ))

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_bodega_desde_cero_respeta_luz_aunque_gemini_entregue_plan_parcial(
        self, interpretar,
    ):
        interpretar.return_value = {
            'intencion': 'planificar_proyecto',
            'proyecto': 'Construcción de bodega con luz interior',
            'ancho_cm': 600,
            'fondo_cm': 400,
            'alto_cm': 500,
            'material_estructura': 'madera',
            'tareas_proyecto': [
                {
                    'nombre': 'Cimientos y radier',
                    'busquedas': ['cemento uso general saco 25 kg'],
                },
                {
                    'nombre': 'Estructura',
                    'busquedas': ['pino dimensionado 2 x 4 pulgadas'],
                },
                {
                    'nombre': 'Muros',
                    'busquedas': ['tablero OSB estructural 9,5 mm'],
                },
                {
                    'nombre': 'Cubierta',
                    'busquedas': ['plancha zinc acanalado 0,35 mm x 3 m'],
                },
                {
                    'nombre': 'Puerta',
                    'busquedas': ['puerta exterior para bodega'],
                },
            ],
            'datos_faltantes_proyecto': [],
        }
        historial = [{
            'role': 'user',
            'content': 'Quiero hacer una bodega con luz interior desde cero',
        }]

        resultado = procesar_consulta(
            'Mide 6 x 4 x 5 metros y la estructura será de madera',
            historial,
        )

        nombres_etapas = {tarea['nombre'] for tarea in resultado['tareas']}
        componentes = ' '.join([
            *(producto['nombre'] for producto in resultado['productos']),
            *resultado['faltantes_catalogo'],
        ]).casefold()
        self.assertIn('Preparación y fundaciones', nombres_etapas)
        self.assertIn('Iluminación interior', nombres_etapas)
        self.assertIn('Evacuación de aguas lluvia', nombres_etapas)
        self.assertIn('portalámpara', componentes)
        self.assertIn('ampolleta', componentes)
        self.assertIn('interruptor', componentes)

    def test_descarta_nombre_de_herramienta_inventado_por_modelo(self):
        from .services.planificador_proyectos import _extraer_tareas

        tareas = _extraer_tareas({
            '_proyecto_integral': True,
            'incluir_herramientas': True,
            'tareas_proyecto': [{
                'nombre': 'Preparación del terreno',
                'busquedas': ['base estabilizada'],
            }],
            'herramientas_proyecto': ['chocalla', 'pala punta', 'nivel de burbuja'],
        })

        herramientas = next(
            tarea for tarea in tareas
            if tarea['nombre'] == 'Herramientas recomendadas'
        )['busquedas']
        self.assertNotIn('chocalla', herramientas)
        self.assertIn('pala punta', herramientas)
        self.assertIn('nivel de burbuja', herramientas)

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_proyecto_estandar_abreviado_solicita_plan_completo_una_vez(self, interpretar):
        interpretar.side_effect = [
            {
                'intencion': 'planificar_proyecto',
                'proyecto': 'Invernadero exterior estándar',
                'modo_orientacion': 'propuesta_estandar',
                'tareas_proyecto': [{
                    'nombre': 'Estructura',
                    'busquedas': ['perfil para invernadero'],
                    'usos_materiales': ['Formar la estructura.'],
                }],
                'datos_faltantes_proyecto': [],
            },
            {
                'intencion': 'planificar_proyecto',
                'proyecto': 'Invernadero exterior estándar',
                'modo_orientacion': 'propuesta_estandar',
                'tareas_proyecto': [
                    {
                        'nombre': f'Etapa {indice + 1}',
                        'busquedas': [
                            f'material invernadero {indice * 3 + desplazamiento + 1}'
                            for desplazamiento in range(3)
                        ],
                        'usos_materiales': [
                            f'Uso específico {indice * 3 + desplazamiento + 1}'
                            for desplazamiento in range(3)
                        ],
                    }
                    for indice in range(5)
                ],
                'datos_faltantes_proyecto': [],
            },
        ]

        resultado = procesar_consulta(
            'Quiero un invernadero exterior estándar.',
            [],
        )

        self.assertEqual(interpretar.call_count, 2)
        self.assertEqual(resultado['tipo'], 'plan_proyecto_generico')
        self.assertEqual(len(resultado['tareas']), 5)
        self.assertEqual(len(resultado['faltantes_catalogo']), 15)
        self.assertTrue(all(
            item['uso'].startswith('Uso específico')
            for item in resultado['faltantes_catalogo_detalle']
        ))

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_pregunta_por_faltantes_explica_uso_sin_reconstruir(self, interpretar):
        historial = [{
            'role': 'assistant',
            'content': (
                'PROPUESTA ESTÁNDAR PARA TU PROYECTO\n\n'
                'PRODUCTOS POR ETAPA\n• Material disponible\n\n'
                'NO DISPONIBLE EN EL CATÁLOGO\n'
                'Estos elementos también se usan para completar el proyecto, pero no están '
                'disponibles actualmente en SFI:\n'
                '• Canaleta de aguas lluvia — Recoge el agua que escurre desde la cubierta.\n'
                '• Bajada PVC — Conduce el agua hasta el punto de descarga.'
            ),
        }]

        resultado = procesar_consulta(
            '¿Falta algún material para completar este proyecto?',
            historial,
            [self.madera.id],
        )

        interpretar.assert_not_called()
        self.assertEqual(resultado['tipo'], 'explicacion_faltantes_proyecto')
        self.assertIn('Canaleta de aguas lluvia', resultado['mensaje'])
        self.assertIn('Recoge el agua', resultado['mensaje'])
        self.assertIn('Bajada PVC', resultado['mensaje'])

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

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_renovacion_no_inventa_estructura_nueva_ni_pide_altura(self, interpretar):
        interpretar.return_value = {
            'intencion': 'planificar_proyecto',
            'proyecto': 'Renovación de techumbre con teja asfáltica',
            'ancho_cm': 300,
            'fondo_cm': 400,
            'material_estructura': 'madera',
            'estado_estructura': 'nueva',
            'tipo_cubierta': 'tejas',
            'datos_faltantes_proyecto': [],
            'tareas_proyecto': [],
        }

        resultado = procesar_consulta(
            'Quiero cambiar mi techo de 3 x 4 metros. La estructura es de madera '
            'y quiero teja asfáltica.',
            [],
        )

        self.assertEqual(resultado['tipo'], 'aclaracion_proyecto')
        mensaje = resultado['mensaje'].casefold()
        self.assertIn('estado de la estructura de apoyo', mensaje)
        self.assertNotIn('altura de la estructura nueva', mensaje)

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_techo_existente_acepta_que_asistente_elija_formato(self, interpretar):
        interpretar.return_value = {
            'intencion': 'planificar_proyecto',
            'proyecto': 'Instalación de techo de policarbonato',
            'ancho_cm': 300,
            'fondo_cm': 400,
            'material_estructura': 'hormigon',
            'estado_estructura': 'nueva',
            'tipo_cubierta': 'policarbonato',
            'datos_faltantes_proyecto': [
                'Altura de la estructura nueva',
                'Formato y espesor del policarbonato',
            ],
            'tareas_proyecto': [],
        }
        historial = [{
            'role': 'user',
            'content': 'Quiero un techo de policarbonato.',
        }]

        resultado = procesar_consulta(
            'Mide 3 x 4 metros, la estructura es de hormigón; el formato dámelo tú.',
            historial,
        )

        self.assertEqual(resultado['tipo'], 'aclaracion_proyecto')
        mensaje = resultado['mensaje'].casefold()
        self.assertIn('estado de la estructura de apoyo', mensaje)
        self.assertNotIn('altura de la estructura nueva', mensaje)
        self.assertNotIn('formato y espesor del policarbonato', mensaje)

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_techo_reconoce_variante_eligue_tu(self, interpretar):
        interpretar.return_value = {
            'intencion': 'planificar_proyecto',
            'proyecto': 'Instalación de techo de policarbonato',
            'ancho_cm': 300,
            'fondo_cm': 400,
            'material_estructura': 'hormigon',
            'estado_estructura': 'reutilizable',
            'tipo_cubierta': 'policarbonato',
            'datos_faltantes_proyecto': ['Formato y espesor del policarbonato'],
            'tareas_proyecto': [],
        }

        resultado = procesar_consulta(
            '3 x 4 metros, hormigón en buen estado, eligue tú.',
            [{'role': 'user', 'content': 'Quiero un techo de policarbonato.'}],
        )

        self.assertNotEqual(resultado['tipo'], 'aclaracion_proyecto')
        self.assertEqual(resultado['superficie_m2'], 12)

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_techo_conserva_eleccion_delegada_en_respuesta_posterior(self, interpretar):
        interpretar.return_value = {
            'intencion': 'planificar_proyecto',
            'proyecto': 'Instalación de techo de policarbonato',
            'ancho_cm': 300,
            'fondo_cm': 400,
            'material_estructura': 'hormigon',
            'estado_estructura': 'reutilizable',
            'tipo_cubierta': 'policarbonato',
            'datos_faltantes_proyecto': ['Formato y espesor del policarbonato'],
            'tareas_proyecto': [],
        }
        historial = [
            {'role': 'user', 'content': 'Quiero un techo de policarbonato.'},
            {
                'role': 'user',
                'content': 'Mide 3 x 4 metros, es de hormigón y el formato dámelo tú.',
            },
            {
                'role': 'assistant',
                'content': 'Antes necesito confirmar el estado de la estructura de apoyo.',
            },
        ]

        resultado = procesar_consulta(
            'La estructura está firme y en buen estado.',
            historial,
        )

        self.assertNotEqual(resultado['tipo'], 'aclaracion_proyecto')
        self.assertEqual(resultado['superficie_m2'], 12)

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_regla_transversal_delega_preferencia_pero_conserva_medidas_criticas(
        self, interpretar,
    ):
        interpretar.return_value = {
            'intencion': 'planificar_proyecto',
            'proyecto': 'Cambio de puerta exterior',
            'modo_orientacion': 'confirmacion_necesaria',
            'material_principal_proyecto': 'puerta exterior',
            'tareas_proyecto': [{
                'nombre': 'Puerta',
                'busquedas': ['puerta exterior'],
                'usos_materiales': ['Cerrar el acceso exterior.'],
                'bases_calculo': ['referencial'],
            }],
            'datos_faltantes_proyecto': [
                'Color y acabado preferido',
                'Medidas de ancho y alto del vano',
            ],
        }

        resultado = procesar_consulta(
            'Quiero cambiar la puerta exterior; el color y acabado elígelos tú.',
            [],
        )

        self.assertEqual(resultado['tipo'], 'aclaracion_proyecto')
        mensaje = resultado['mensaje'].casefold()
        self.assertIn('medidas de ancho y alto del vano', mensaje)
        self.assertNotIn('color y acabado preferido', mensaje)

    def test_techumbre_asfaltica_no_se_sustituye_por_teja_colonial(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Renovación de techumbre con teja asfáltica',
            'ancho_cm': 300,
            'fondo_cm': 400,
            'material_estructura': 'madera',
            'estado_estructura': 'reutilizable',
            'tipo_cubierta': 'teja asfaltica',
            'datos_faltantes_proyecto': [],
            'tareas_proyecto': [],
        })

        cubiertas = [
            producto['nombre'].casefold()
            for producto in resultado['productos']
            if producto['rol'] == 'Cubierta'
        ]
        self.assertTrue(any('asf' in nombre for nombre in cubiertas))
        self.assertFalse(any('colonial' in nombre for nombre in cubiertas))

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
        self.assertIn('ladrillo refractario', mensaje)
        self.assertIn('expuesto directamente al calor', mensaje)
        self.assertIn('sostener la cubierta entre los apoyos', mensaje)

    def test_quincho_estandar_declara_materiales_necesarios_no_disponibles(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Quincho estándar',
            '_proyecto_estandar': True,
            'tareas_proyecto': [{
                'nombre': 'Referencia inicial',
                'busquedas': ['ladrillo fiscal'],
            }],
            'datos_faltantes_proyecto': [],
        })

        faltantes = ' '.join(resultado['faltantes_catalogo']).casefold()
        self.assertIn('parrilla acero inoxidable quincho', faltantes)
        self.assertIn('campana humo quincho', faltantes)
        self.assertIn('ducto chimenea quincho', faltantes)
        self.assertIn('anticorrosivo metal exterior', faltantes)
        self.assertIn('NO DISPONIBLE EN EL CATÁLOGO', resultado['mensaje'])
        self.assertTrue(all(
            detalle.get('uso')
            for detalle in resultado['faltantes_catalogo_detalle']
        ))
        nombres_disponibles = ' '.join(
            producto['nombre'] for producto in resultado['productos']
        ).casefold()
        self.assertIn('extintor abc de polvo químico seco 6 kg', nombres_disponibles)
        self.assertNotIn('parrilla acero inoxidable quincho', nombres_disponibles)
        self.assertIn('solo una estimación orientativa', resultado['mensaje'])
        self.assertTrue(
            resultado['mensaje'].endswith('consulta con un profesional calificado.')
        )

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

        self.assertEqual(resultado['tipo'], 'seguimiento_herramientas')
        self.assertIn('HERRAMIENTAS PARA REALIZAR EL TRABAJO', resultado['mensaje'])
        self.assertIn('COSTO OPCIONAL', resultado['mensaje'])
        self.assertNotIn('PROYECTO\nAnalicé', resultado['mensaje'])
        self.assertTrue(resultado['productos'])
        self.assertTrue(all(
            'herramienta' in producto['rol'].casefold()
            for producto in resultado['productos']
        ))

    def test_pasta_muro_recomienda_espatula_y_lija_no_rodillo(self):
        pasta = Producto.objects.create(
            nombre='Pasta muro interior 15 kg',
            descripcion='Pasta para alisar y reparar muros interiores.',
            precio=14990,
            stock=20,
            categoria='Adhesivos',
            activo=True,
        )
        Producto.objects.create(
            nombre='Espátula acero flexible 100 mm',
            descripcion='Espátula para aplicar pasta muro.',
            precio=3490,
            stock=20,
            categoria='Herramientas',
            activo=True,
        )
        Producto.objects.create(
            nombre='Lija madera y muro grano 120 pack 10',
            descripcion='Lija para terminación de muros.',
            precio=5990,
            stock=20,
            categoria='Ferretería',
            activo=True,
        )
        Producto.objects.create(
            nombre='Rodillo pintura muros 23 cm',
            descripcion='Rodillo para pintar muros.',
            precio=6990,
            stock=20,
            categoria='Herramientas',
            activo=True,
        )

        seguimiento = _resolver_accion_seguimiento(
            '¿Qué herramienta utiliza?', [pasta.pk],
        )
        inicial = _resolver_herramientas_iniciales(
            '¿Qué herramienta se usa para pasta muro?',
        )

        for resultado in (seguimiento, inicial):
            nombres = ' '.join(item['nombre'].casefold() for item in resultado['productos'])
            self.assertIn('espátula', nombres)
            self.assertIn('lija', nombres)
            self.assertNotIn('rodillo', nombres)

    def test_instalacion_gas_cocina_no_mezcla_productos_sanitarios(self):
        for nombre, categoria in (
            ('Tubo cobre rígido para gas 1/2 pulgada x 3 m', 'Gasfitería'),
            ('Codo cobre para gas 1/2 pulgada', 'Gasfitería'),
            ('Unión cobre para gas 1/2 pulgada', 'Gasfitería'),
            ('Válvula corte gas bronce 1/2 pulgada', 'Gasfitería'),
            ('Sanitario dos piezas doble descarga con kit de instalación', 'Gasfitería'),
        ):
            Producto.objects.create(
                nombre=nombre,
                descripcion='Producto de prueba.',
                precio=2990,
                stock=20,
                categoria=categoria,
                activo=True,
            )

        resultado = _resolver_proyecto({
            'proyecto': 'Instalación de gas estándar para cocina',
            '_proyecto_estandar': True,
            'modo_orientacion': 'propuesta_estandar',
            'tareas_proyecto': [],
            'herramientas_proyecto': [],
            'especialidades_proyecto': [],
        })

        nombres = ' '.join(item['nombre'].casefold() for item in resultado['productos'])
        self.assertIn('tubo cobre', nombres)
        self.assertIn('codo cobre', nombres)
        self.assertIn('unión cobre', nombres)
        self.assertIn('válvula corte gas', nombres)
        self.assertNotIn('sanitario', nombres)

    def test_luz_exterior_con_sensor_prioriza_luminaria_y_no_asume_automatico(self):
        for nombre, categoria in (
            ('Aplique LED exterior IP65 12 W', 'Iluminación'),
            ('Sensor movimiento exterior 180 grados', 'Electricidad'),
            ('Conduit PVC eléctrico 20 mm x 3 m', 'Electricidad'),
            ('Cable eléctrico 1,5 mm² rollo 100 m', 'Electricidad'),
            ('Caja estanca eléctrica 100 x 100 mm', 'Electricidad'),
            ('Kit fijación para hormigón y ladrillo pack 10', 'Ferretería'),
            ('Taladro percutor de prueba', 'Herramientas'),
            ('Alicate universal aislado de prueba', 'Herramientas'),
            ('Interruptor automático 16 A curva C', 'Electricidad'),
            ('Enchufe exterior estanco 16 A con tapa', 'Electricidad'),
        ):
            Producto.objects.create(
                nombre=nombre,
                descripcion='Producto de prueba.',
                precio=5990,
                stock=20,
                categoria=categoria,
                activo=True,
            )

        resultado = _resolver_proyecto({
            'proyecto': 'Instalación de luz exterior con sensor de movimiento',
            'tareas_proyecto': [],
            'herramientas_proyecto': [],
            'especialidades_proyecto': [],
        })

        nombres = ' '.join(item['nombre'].casefold() for item in resultado['productos'])
        self.assertIn('aplique led exterior', nombres)
        self.assertIn('sensor movimiento exterior', nombres)
        self.assertIn('conduit pvc', nombres)
        self.assertIn('caja estanca', nombres)
        self.assertNotIn('interruptor automático', nombres)
        self.assertNotIn('enchufe exterior', nombres)
        self.assertIn('electricista autorizado', resultado['mensaje'])

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
        self.assertIn('BASE ACTUAL', resultado['mensaje'])
        self.assertIn('Hormigón:', resultado['mensaje'])
        self.assertIn('Madera/OSB:', resultado['mensaje'])
        self.assertIn('Cerámica:', resultado['mensaje'])
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

        self.assertEqual(resultado['tipo'], 'seguimiento_proyecto')
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
        self.assertIn('alveolar 6 mm', cubierta['nombre'].casefold())
        self.assertIn('5 unidad(es)', resultado['mensaje'])
        self.assertEqual(resultado['total_calculado'], 5 * policarbonato.precio)
        self.assertIn('TOTAL CALCULADO', resultado['mensaje'])
        self.assertIn('$149.950 CLP', resultado['mensaje'])
        bloques = resultado['mensaje'].split('\n\n')
        self.assertTrue(bloques[0].startswith((
            'PROPUESTA ESTÁNDAR PARA TU PROYECTO',
            'PROYECTO',
        )))
        self.assertTrue(bloques[1].startswith('DATOS CONSIDERADOS'))
        self.assertEqual(resultado['mensaje'].count('Cantidad calculada:'), 0)
        self.assertTrue(
            resultado['mensaje'].endswith('consulta con un profesional calificado.')
        )

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
        self.assertIn('Estas cantidades usan las fichas verificadas', resultado['mensaje'])

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

        self.assertEqual(resultado['tipo'], 'plan_proyecto_generico')
        self.assertTrue(resultado['productos'])
        self.assertIn('panel de bambú', resultado['faltantes_catalogo'])
        detalle = next(
            item for item in resultado['faltantes_catalogo_detalle']
            if item['nombre'] == 'panel de bambú'
        )
        self.assertEqual(detalle['etapa'], 'Material principal')
        self.assertIn('Se utiliza en la etapa', detalle['uso'])
        self.assertIn('también se usan para completar el proyecto', resultado['mensaje'])

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
            '_proyecto_estandar': True,
            'datos_faltantes_proyecto': [
                'ancho del área a cubrir',
                'largo del área a cubrir',
            ],
        })

        pinos = [
            producto for producto in resultado['productos']
            if 'pino dimensionado' in producto['nombre'].casefold()
        ]
        self.assertEqual(len(pinos), 1)
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
        self.assertIn(
            '¿Qué herramientas necesito para este proyecto?',
            resultado['sugerencias'],
        )
        self.assertIn(
            'Ajustar medidas o materiales del proyecto',
            resultado['sugerencias'],
        )

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
        self.assertIn('altura de la estructura nueva', resultado['mensaje'].casefold())

    def test_agregar_herramienta_conserva_estimacion_y_no_duplica(self):
        tablero = Producto.objects.create(
            nombre='Tablero comedor prueba', descripcion='Madera para mesa.',
            precio=29990, stock=10, categoria='Maderas', activo=True,
        )
        brocha = Producto.objects.create(
            nombre='Brocha multipropósito 2 pulgadas prueba',
            descripcion='Aplicación de barniz.', precio=3990, stock=20,
            categoria='Herramientas', activo=True,
        )
        contexto = [{
            'id': tablero.pk,
            'carrito_cantidad': 2,
            'cantidad_requerida': 2,
            'rol': 'Estructura principal',
            'detalle_material': 'Dos tableros para la cubierta.',
            'es_opcional': False,
            'incluido_en_total': True,
        }]

        resultado = procesar_consulta(
            'Agrégame una brocha a la lista, eso faltó',
            [],
            [tablero.pk],
            'auto',
            contexto,
        )

        self.assertEqual(resultado['tipo'], 'seguimiento_estimacion')
        self.assertEqual(resultado['productos'][0]['id'], tablero.pk)
        self.assertIn('brocha', resultado['productos'][1]['nombre'].casefold())
        self.assertEqual(resultado['productos'][0]['carrito_cantidad'], 2)
        self.assertEqual(resultado['productos'][1]['rol'], 'Herramienta opcional')
        self.assertTrue(resultado['productos'][1]['es_opcional'])
        self.assertFalse(resultado['productos'][1]['incluido_en_total'])

        brocha_agregada_id = resultado['productos'][1]['id']

        repetido = procesar_consulta(
            'Añade la brocha a la estimación',
            [],
            [tablero.pk, brocha_agregada_id],
            'auto',
            [*contexto, {'id': brocha_agregada_id, 'carrito_cantidad': 1}],
        )
        self.assertEqual(len(repetido['productos']), 2)
        self.assertIn('ya se encuentra incluido', repetido['mensaje'])

    def test_herramientas_de_madera_con_barniz_incluyen_brocha(self):
        madera = Producto.objects.create(
            nombre='Pino mesa prueba', descripcion='Madera dimensionada.',
            precio=4990, stock=20, categoria='Maderas', activo=True,
        )
        barniz = Producto.objects.create(
            nombre='Barniz madera prueba', descripcion='Terminación protectora.',
            precio=8990, stock=20, categoria='Pinturas', activo=True,
        )
        for nombre in (
            'Cinta métrica herramienta prueba',
            'Taladro percutor herramienta prueba',
            'Sierra circular herramienta prueba',
            'Brocha pintura herramienta prueba',
        ):
            Producto.objects.create(
                nombre=nombre, descripcion='Herramienta de prueba.',
                precio=5990, stock=10, categoria='Herramientas', activo=True,
            )

        from .services.asistente_sfi import _resolver_accion_seguimiento
        resultado = _resolver_accion_seguimiento(
            '¿Qué herramientas necesito para este proyecto?',
            [madera.pk, barniz.pk],
        )

        nombres = [item['nombre'].casefold() for item in resultado['productos']]
        self.assertTrue(any('brocha' in nombre for nombre in nombres))
        self.assertTrue(any('sierra' in nombre for nombre in nombres))
        self.assertTrue(all(
            item.get('detalle_material')
            for item in resultado['productos']
        ))
        self.assertIn('Aplicar barniz o pintura', resultado['mensaje'])

    def test_pegamento_generico_no_se_convierte_en_adhesivo_ceramico(self):
        from .services.sinonimos_ferreteros import expandir_consulta

        palabras, _ = expandir_consulta(['pegamento'])

        self.assertIn('adhesivo', palabras)
        self.assertNotIn('ceramico', palabras)

    def test_busqueda_cotidiana_distingue_adhesivo_para_calzado(self):
        from .services.asistente_sfi import _buscar_productos

        calzado = Producto.objects.create(
            nombre='Adhesivo transparente prueba para calzado 9 g',
            descripcion='Gel flexible para reparar zapatos y zapatillas.',
            uso_recomendado='Punteras, bordes, talones y suelas de calzado.',
            precio=5990,
            stock=10,
            categoria='Adhesivos',
            especificaciones={
                'familia_adhesivo': 'adhesivo flexible para calzado',
                'materiales_compatibles': ['cuero', 'tela'],
            },
            activo=True,
        )
        Producto.objects.create(
            nombre='Adhesivo cerámico prueba saco 25 kg',
            descripcion='Para revestimientos cerámicos.',
            precio=8990,
            stock=10,
            categoria='Adhesivos',
            activo=True,
        )

        resultados = _buscar_productos('necesito pegar una zapatilla')

        self.assertTrue(resultados)
        self.assertEqual(resultados[0].pk, calzado.pk)

    @patch('asistente.services.asistente_sfi.interpretar_con_gemini')
    def test_ficha_adhesivo_explica_compatibilidad_aplicacion_y_cantidad(self, interpretar):
        from .services.asistente_sfi import _respuesta_uso_producto

        interpretar.return_value = {'respuesta': ''}
        producto = Producto.objects.create(
            nombre='Adhesivo instantáneo prueba 2 ml',
            descripcion='Adhesivo para reparaciones pequeñas.',
            uso_recomendado='Unir piezas pequeñas con encaje correcto.',
            precio=3990,
            stock=10,
            categoria='Adhesivos',
            especificaciones={
                'familia_adhesivo': 'cianoacrilato instantáneo',
                'materiales_compatibles': ['cerámica', 'metal'],
                'no_compatible': ['polietileno'],
                'preparacion': 'Limpiar y secar',
                'aplicacion_recomendada': 'Aplicar una gota',
                'cantidad_orientativa': 'Depende del tamaño de la reparación',
            },
            activo=True,
        )

        resultado = _respuesta_uso_producto([producto])

        self.assertIn('COMPATIBILIDAD Y APLICACIÓN', resultado['mensaje'])
        self.assertIn('Materiales compatibles: cerámica, metal', resultado['mensaje'])
        self.assertIn('No usar sobre: polietileno', resultado['mensaje'])
        self.assertIn('Aplicación: Aplicar una gota', resultado['mensaje'])
        self.assertIn('Cantidad orientativa:', resultado['mensaje'])

    def test_reparar_mesa_pide_material_y_tipo_de_dano_antes_de_buscar(self):
        resultado = procesar_consulta(
            'algo pegamento para arreglar la mesa',
            [{'role': 'assistant', 'content': '¿Qué producto necesitas buscar?'}],
        )

        self.assertEqual(resultado['tipo'], 'aclaracion')
        self.assertEqual(resultado['productos'], [])
        self.assertIn('material del mueble', resultado['mensaje'])
        self.assertIn('qué parte está dañada', resultado['mensaje'])

    def test_reparar_mesa_no_confunde_pata_con_estado_del_dano(self):
        resultado = procesar_consulta(
            'Una de las patas y es de madera',
            [{
                'role': 'assistant',
                'content': (
                    'ANTES DE RECOMENDAR UN ADHESIVO: indica el material, '
                    'la parte dañada y su estado.'
                ),
            }],
        )

        self.assertEqual(resultado['tipo'], 'aclaracion')
        self.assertEqual(resultado['productos'], [])
        self.assertIn('suelta, despegada, quebrada', resultado['mensaje'])

    def test_adhesivo_madera_tambien_aclara_puertas_y_otras_piezas(self):
        resultado = procesar_consulta(
            'Necesito pegamento para reparar una puerta de madera',
            [],
        )

        self.assertEqual(resultado['tipo'], 'aclaracion')
        self.assertEqual(resultado['productos'], [])
        self.assertIn('suelta, despegada, quebrada', resultado['mensaje'])
        self.assertIn('tipo de daño', resultado['mensaje'])

    def test_adhesivo_para_mesa_sin_verbo_tambien_pide_aclaracion(self):
        resultado = procesar_consulta('Necesito un adhesivo para mi mesa', [])

        self.assertEqual(resultado['tipo'], 'aclaracion')
        self.assertEqual(resultado['productos'], [])
        self.assertIn('material de la pieza u objeto', resultado['mensaje'])
        self.assertIn('qué parte está dañada', resultado['mensaje'])

    def test_reparacion_madera_con_adhesivo_incluye_sargento_y_presentacion(self):
        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Reparar pata de mesa de madera despegada con adhesivo',
            '_proyecto_estandar': True,
            'tareas_proyecto': [{
                'nombre': 'Unión de madera',
                'busquedas': ['adhesivo para madera interior envase 1 kg'],
                'usos_materiales': [{
                    'busqueda': 'adhesivo para madera interior envase 1 kg',
                    'uso': 'Volver a unir la pata despegada.',
                }],
            }],
            'datos_faltantes_proyecto': [],
        })

        adhesivo = next(
            item for item in resultado['productos']
            if item['categoria'] == 'Adhesivos'
        )
        self.assertFalse(adhesivo['cantidad_pendiente'])
        self.assertEqual(adhesivo['carrito_cantidad'], 1)
        self.assertIn('Presentación sugerida: 1 envase', adhesivo['presentacion_sugerida'])
        self.assertTrue(any(
            'sargento' in item['nombre'].lower()
            for item in resultado['productos']
        ))

    def test_seguimiento_despegada_conserva_mesa_y_no_deriva_a_ceramica(self):
        historial = [
            {
                'role': 'user',
                'content': 'Necesito un ashedivo para arreglar mi mesa',
            },
            {
                'role': 'assistant',
                'content': 'ANTES DE RECOMENDAR UN ADHESIVO: indica material y daño.',
            },
            {
                'role': 'user',
                'content': 'Una de las patas y es de madera',
            },
            {
                'role': 'assistant',
                'content': 'ANTES DE RECOMENDAR UN ADHESIVO: indica si está despegada.',
            },
        ]

        resultado = procesar_consulta('Despegada', historial)

        self.assertEqual(resultado['tipo'], 'plan_proyecto_generico')
        self.assertIn('Reparación de pata de mesa', resultado['mensaje'])
        self.assertNotIn('cerámica', resultado['mensaje'].lower())
        self.assertNotIn('metros cuadrados', resultado['mensaje'].lower())
        self.assertTrue(any(
            producto['categoria'] == 'Adhesivos'
            for producto in resultado['productos']
        ))
        self.assertTrue(any(
            'sargento' in producto['nombre'].lower()
            for producto in resultado['productos']
        ))

    def test_busqueda_adhesivo_separa_resultados_principales_de_complementos(self):
        adhesivo = Producto.objects.create(
            nombre='Cola fría madera prueba 500 g',
            descripcion='Adhesivo para uniones de madera.',
            precio=4990,
            stock=20,
            categoria='Adhesivos',
            activo=True,
        )
        tornillo = Producto.objects.create(
            nombre='Tornillo madera complemento prueba pack 20',
            descripcion='Fijación mecánica para madera.',
            precio=2990,
            stock=20,
            categoria='Ferretería',
            activo=True,
        )

        resultado = resolver_interpretacion({
            'intencion': 'buscar_producto',
            'consulta_producto': 'pegamento para madera prueba',
        })

        por_id = {item['id']: item for item in resultado['productos']}
        self.assertEqual(por_id[adhesivo.pk]['rol'], 'Resultado principal · adhesivo')
        self.assertEqual(
            por_id[tornillo.pk]['rol'],
            'También podría servirte · complemento',
        )
        self.assertIn('no son adhesivos equivalentes', resultado['mensaje'])

    def test_proyecto_generico_lista_materiales_y_explica_su_uso(self):
        Producto.objects.create(
            nombre='Adhesivo madera explicativo prueba',
            descripcion='Adhesivo para reparar uniones de madera.',
            uso_recomendado='Unir nuevamente las piezas de madera de la mesa.',
            precio=5990,
            stock=10,
            categoria='Adhesivos',
            activo=True,
        )

        resultado = resolver_interpretacion({
            'intencion': 'planificar_proyecto',
            'proyecto': 'Reparación de pata de mesa de madera',
            'tareas_proyecto': [{
                'nombre': 'Unión y pegado',
                'busquedas': ['adhesivo madera explicativo prueba'],
                'usos_materiales': [{
                    'busqueda': 'adhesivo madera explicativo prueba',
                    'uso': 'Unir nuevamente la pata con la estructura de la mesa.',
                }],
            }],
            'datos_faltantes_proyecto': [],
        })

        self.assertEqual(resultado['tipo'], 'plan_proyecto_generico')
        self.assertIn('MATERIALES Y PARA QUÉ SE USAN', resultado['mensaje'])
        self.assertIn('Unión y pegado', resultado['mensaje'])
        self.assertIn('Adhesivo madera explicativo prueba', resultado['mensaje'])
        self.assertIn(
            'Unir nuevamente la pata con la estructura de la mesa.',
            resultado['mensaje'],
        )

    def test_pregunta_por_varios_materiales_explica_sin_rehacer_propuesta(self):
        adhesivo = Producto.objects.create(
            nombre='Adhesivo madera seguimiento prueba',
            descripcion='Une piezas de madera limpias y ajustadas.',
            uso_recomendado='Pegar nuevamente una unión de madera.',
            precio=4990,
            stock=12,
            categoria='Adhesivos',
            activo=True,
        )
        lija = Producto.objects.create(
            nombre='Lija madera seguimiento prueba grano 120',
            descripcion='Prepara superficies de madera.',
            uso_recomendado='Retirar residuos sueltos antes del encolado.',
            precio=1990,
            stock=20,
            categoria='Herramientas',
            activo=True,
        )

        resultado = procesar_consulta(
            '¿Para qué sirven el adhesivo y la lija?',
            [],
            [adhesivo.pk, lija.pk],
        )

        self.assertEqual(resultado['tipo'], 'explicacion_materiales')
        self.assertIn(adhesivo.nombre, resultado['mensaje'])
        self.assertIn(lija.nombre, resultado['mensaje'])
        self.assertIn('no modifica cantidades', resultado['mensaje'])
        self.assertEqual(resultado['productos'], [])
