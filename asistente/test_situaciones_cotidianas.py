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

    def test_riesgo_no_ofrece_productos(self):
        resultado = procesar_consulta('el enchufe tira chispas y huele quemado', [])

        self.assertEqual(resultado['tipo'], 'orientacion_seguridad')
        self.assertEqual(resultado['productos'], [])
        self.assertIn('profesional', resultado['mensaje'].casefold())
