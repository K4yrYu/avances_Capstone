from django.test import SimpleTestCase, TestCase

from productos.models import Producto
from .services.asistente_sfi import procesar_consulta
from .services.situaciones_cotidianas import detectar_situacion_cotidiana


class DetectorSituacionesCotidianasTests(SimpleTestCase):
    def test_corrige_error_comun_al_pedir_clavos(self):
        situacion = detectar_situacion_cotidiana('necesito una cosa para poner clabos')
        self.assertEqual(situacion['codigo'], 'clavar')

    def test_pide_datos_para_desague_sin_recomendar_antes_de_tiempo(self):
        situacion = detectar_situacion_cotidiana('el agua no baja del lavaplatos')
        self.assertEqual(situacion['codigo'], 'desague_obstruido')
        self.assertEqual(situacion['tipo'], 'aclaracion')
        self.assertLessEqual(len(situacion['preguntas']), 3)

    def test_reconoce_humedad_expresada_sin_vocabulario_tecnico(self):
        situacion = detectar_situacion_cotidiana('la pared se esta poniendo negra')
        self.assertEqual(situacion['codigo'], 'humedad_muro')

    def test_reconoce_puerta_que_roza(self):
        situacion = detectar_situacion_cotidiana('la puerta esta topando con el piso')
        self.assertEqual(situacion['codigo'], 'puerta_roza')

    def test_reconoce_gotera_en_techo_como_diagnostico_acotado(self):
        situacion = detectar_situacion_cotidiana('quiero reparar una gotera en el techo')
        self.assertEqual(situacion['codigo'], 'filtracion_techo')
        self.assertEqual(situacion['tipo'], 'aclaracion')
        self.assertIn('cubierta', situacion['preguntas'][0].casefold())

    def test_prioriza_riesgo_sobre_busqueda_de_productos(self):
        situacion = detectar_situacion_cotidiana('sale humo del enchufe y huele quemado')
        self.assertEqual(situacion['tipo'], 'riesgo')


class FlujoSituacionesCotidianasTests(TestCase):
    def test_error_ortografico_recomienda_producto_real_del_catalogo(self):
        martillo = Producto.objects.create(
            nombre='Martillo carpintero 16 oz',
            descripcion='Herramienta para clavar y retirar clavos',
            precio=15000,
            stock=18,
            categoria='Herramientas',
            marca='Unitools',
            activo=True,
        )

        resultado = procesar_consulta('necesito algo para poner clabos', [])

        self.assertEqual(resultado['tipo'], 'productos')
        self.assertEqual(resultado['productos'][0]['id'], martillo.id)

    def test_problema_ambiguo_solicita_especificaciones_sin_productos(self):
        resultado = procesar_consulta('la pared se está poniendo negra', [])

        self.assertEqual(resultado['tipo'], 'aclaracion_cotidiana')
        self.assertEqual(resultado['productos'], [])
        self.assertIn('origen de la humedad', resultado['mensaje'])
        self.assertNotIn('fotograf', resultado['mensaje'].casefold())

    def test_seguimiento_gotera_no_pide_medidas_de_techumbre_nueva(self):
        historial = [
            {'role': 'user', 'content': 'Quiero reparar una gotera en el techo.'},
            {
                'role': 'assistant',
                'content': (
                    'La filtración puede provenir de la cubierta, una unión o el drenaje. '
                    '¿La cubierta es zinc, policarbonato, teja u otro material?'
                ),
            },
        ]

        resultado = procesar_consulta(
            'Es policarbonato y no veo nada roto ni suelto.', historial,
        )

        self.assertEqual(resultado['tipo'], 'seguimiento_gotera')
        self.assertIn('solo falta identificar el punto', resultado['mensaje'].casefold())
        self.assertNotIn('largo y ancho', resultado['mensaje'].casefold())
        self.assertNotIn('estructura de apoyo', resultado['mensaje'].casefold())

    def test_gotera_sin_origen_entrega_revision_y_sellos_compatibles(self):
        Producto.objects.create(
            nombre='Sellador neutro compatible con policarbonato prueba',
            descripcion='Sellar uniones de policarbonato.',
            precio=6990,
            stock=10,
            categoria='Adhesivos',
            activo=True,
        )
        Producto.objects.create(
            nombre='Cinta butílica impermeable prueba',
            descripcion='Sellar traslapes de cubierta.',
            precio=8990,
            stock=10,
            categoria='Adhesivos',
            activo=True,
        )
        historial = [
            {'role': 'user', 'content': 'Quiero reparar una gotera en el techo.'},
            {
                'role': 'assistant',
                'content': 'La filtración puede provenir de la cubierta, una unión o el drenaje.',
            },
            {'role': 'user', 'content': 'Es policarbonato y no veo nada roto.'},
        ]

        resultado = procesar_consulta('No logro ubicar el punto de entrada.', historial)

        self.assertEqual(resultado['tipo'], 'orientacion_gotera')
        self.assertIn('no conviene sellar toda la cubierta al azar', resultado['mensaje'].casefold())
        nombres = ' '.join(item['nombre'].casefold() for item in resultado['productos'])
        self.assertIn('sellador neutro', nombres)
        self.assertIn('cinta butílica', nombres)

    def test_gotera_zinc_sin_origen_no_recomienda_sellador_policarbonato(self):
        Producto.objects.create(
            nombre='Cinta butílica impermeable para zinc prueba',
            descripcion='Sella traslapes de cubiertas de zinc.',
            precio=8990,
            stock=10,
            categoria='Adhesivos',
            activo=True,
        )
        Producto.objects.create(
            nombre='Tapagoteras acrílico impermeabilizante prueba',
            descripcion='Reparación puntual de filtraciones exteriores.',
            precio=6990,
            stock=10,
            categoria='Adhesivos',
            activo=True,
        )
        Producto.objects.create(
            nombre='Sellador neutro compatible con policarbonato prueba',
            descripcion='Sellar uniones de policarbonato.',
            precio=6990,
            stock=10,
            categoria='Adhesivos',
            activo=True,
        )
        historial = [
            {'role': 'user', 'content': 'Quiero reparar una gotera en el techo.'},
            {'role': 'assistant', 'content': 'La filtración puede provenir de la cubierta, una unión o el drenaje.'},
            {'role': 'user', 'content': 'Es zinc y no veo planchas rotas.'},
        ]

        resultado = procesar_consulta('No logro ubicar el punto de entrada.', historial)

        self.assertEqual(resultado['tipo'], 'orientacion_gotera')
        self.assertIn('gotera en zinc', resultado['mensaje'].casefold())
        nombres = ' '.join(item['nombre'].casefold() for item in resultado['productos'])
        self.assertIn('cinta butílica', nombres)
        self.assertIn('tapagoteras', nombres)
        self.assertNotIn('sellador neutro compatible con policarbonato', nombres)

    def test_gotera_tejas_entrega_materiales_sin_pedir_medidas(self):
        Producto.objects.create(
            nombre='Tapagoteras acrílico impermeabilizante prueba teja',
            descripcion='Reparación puntual de filtraciones exteriores.',
            precio=6990,
            stock=10,
            categoria='Adhesivos',
            activo=True,
        )

        resultado = procesar_consulta('¿Qué sirve para tapar las goteras en un techo de tejas?', [])

        self.assertEqual(resultado['tipo'], 'orientacion_gotera')
        self.assertIn('techo de teja', resultado['mensaje'].casefold())
        self.assertNotIn('largo y ancho', resultado['mensaje'].casefold())
        self.assertTrue(resultado['productos'])

    def test_riesgo_no_ofrece_productos(self):
        resultado = procesar_consulta('el enchufe tira chispas y huele quemado', [])

        self.assertEqual(resultado['tipo'], 'orientacion_seguridad')
        self.assertEqual(resultado['productos'], [])
        self.assertIn('profesional', resultado['mensaje'].casefold())
