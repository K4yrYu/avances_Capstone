from unittest.mock import Mock, patch
from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse
from transbank.common import request_service as sdk_request_service

from productos.models import Producto
from usuarios.models import Usuario
from .models import Detalle, Venta
from .services.transbank_tls import cliente_http_transbank
from .views import _webpay_transaction


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SeguridadCarritoTests(TestCase):
    def setUp(self):
        self.dueno = Usuario.objects.create_user(
            rut='55555555-5', username='dueno', email='dueno@example.com',
            telefono='+56955555555', password='Ferremas!2026Clave',
        )
        self.otro = Usuario.objects.create_user(
            rut='66666666-6', username='otro', email='otro@example.com',
            telefono='+56966666666', password='Ferremas!2026Clave',
        )
        self.admin = Usuario.objects.create_user(
            rut='88888888-8', username='admin_ventas', email='admin-ventas@example.com',
            telefono='+56988888888', password='Ferremas!2026Clave', is_staff=True,
        )
        self.producto = Producto.objects.create(
            nombre='Martillo', descripcion='Martillo', precio=10000,
            imagen='https://example.com/martillo.jpg', stock=10,
            categoria='Herramientas', activo=True,
        )
        self.venta = Venta.objects.create(id_usuario=self.dueno, total_venta=20000)
        self.detalle = Detalle.objects.create(
            id_venta=self.venta, producto=self.producto, cantidad_producto=2,
        )

    def test_otro_usuario_no_puede_modificar_detalle(self):
        self.client.force_login(self.otro)

        response = self.client.put(
            reverse('actualizar_cantidad_producto', args=[self.detalle.id]),
            {'cantidad_producto': 1},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 404)
        self.detalle.refresh_from_db()
        self.assertEqual(self.detalle.cantidad_producto, 2)

    def test_cantidad_cero_es_rechazada(self):
        self.client.force_login(self.dueno)

        response = self.client.put(
            reverse('actualizar_cantidad_producto', args=[self.detalle.id]),
            {'cantidad_producto': 0},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.detalle.refresh_from_db()
        self.assertEqual(self.detalle.cantidad_producto, 2)

    def test_disminuir_ultimo_producto_lo_elimina_y_deja_total_cero(self):
        self.detalle.cantidad_producto = 1
        self.detalle.save(update_fields=['cantidad_producto', 'subtotal_venta'])
        self.venta.total_venta = self.detalle.subtotal_venta
        self.venta.save(update_fields=['total_venta'])
        self.client.force_login(self.dueno)

        response = self.client.put(
            reverse('disminuir_cantidad_producto', args=[self.detalle.id]),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['total_carrito'], 0)
        self.assertFalse(Detalle.objects.filter(id=self.detalle.id).exists())
        self.venta.refresh_from_db()
        self.assertEqual(self.venta.total_venta, 0)

    def test_paneles_y_api_de_ventas_requieren_administrador(self):
        self.client.force_login(self.dueno)

        pagina = self.client.get(reverse('historial_ventas'))
        api = self.client.get(reverse('api_historial_ventas'))

        self.assertEqual(pagina.status_code, 302)
        self.assertEqual(api.status_code, 403)

    def test_carrito_no_aparece_como_retiro_ni_genera_boleta(self):
        self.client.force_login(self.admin)

        retiros = self.client.get(reverse('api_retiros'))
        boleta = self.client.get(reverse('api_boleta', args=[self.venta.id]))

        self.assertEqual(retiros.status_code, 200)
        self.assertEqual(retiros.json(), [])
        self.assertEqual(boleta.status_code, 404)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class CalculadoraCarritoTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            rut='33333333-3', username='calculador', email='calculador@example.com',
            telefono='+56933333333', password='Ferremas!2026Clave',
        )
        self.pintura = Producto.objects.create(
            nombre='Pintura calculable carrito', descripcion='Ficha verificada',
            precio=20000, imagen='productos/pintura-calculo.webp', stock=5,
            categoria='Pinturas', marca='SFI', color='Blanco', color_hex='#FFFFFF',
            ambiente_uso='interior',
            superficies_compatibles=['hormigon', 'yeso_carton'],
            tipo_pintura='latex', terminacion='mate',
            propiedades_pintura=['base_agua', 'bajo_olor'],
            preparaciones_recomendadas=['limpieza', 'sellador'],
            repintado_min_horas=Decimal('3.00'), repintado_max_horas=Decimal('6.00'),
            unidad_venta='envase', contenido=Decimal('4.000'), unidad_contenido='l',
            tipo_calculo='pintura', rendimiento=Decimal('10.000'), unidad_rendimiento='m2_l',
            capas_recomendadas=2, porcentaje_desperdicio=Decimal('10.00'),
            informacion_tecnica_verificada=True, activo=True,
        )

    def test_servidor_calcula_cantidad_y_total_antes_de_agregar(self):
        self.client.force_login(self.usuario)

        response = self.client.post(
            reverse('agregar_calculo_pintura_carrito'),
            {
                'producto': self.pintura.id, 'superficie': 51,
                'ambiente': 'interior', 'tipo_superficie': 'hormigon',
                'estado_superficie': 'nueva', 'terminacion': 'cualquiera',
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200, response.content)
        detalle = Detalle.objects.get(id_venta__id_usuario=self.usuario)
        self.assertEqual(detalle.cantidad_producto, 3)
        self.assertEqual(detalle.subtotal_venta, 60000)
        self.assertEqual(detalle.id_venta.total_venta, 60000)

    def test_recomendacion_reemplaza_cantidad_existente_sin_duplicar(self):
        venta = Venta.objects.create(id_usuario=self.usuario, estado_venta='carrito')
        Detalle.objects.create(id_venta=venta, producto=self.pintura, cantidad_producto=1)
        self.client.force_login(self.usuario)

        response = self.client.post(
            reverse('agregar_calculo_pintura_carrito'),
            {
                'producto': self.pintura.id, 'superficie': 51,
                'ambiente': 'interior', 'tipo_superficie': 'hormigon',
                'estado_superficie': 'nueva', 'terminacion': 'cualquiera',
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(venta.detalles.count(), 1)
        self.assertEqual(venta.detalles.get().cantidad_producto, 3)

    def test_stock_insuficiente_no_modifica_el_carrito(self):
        self.pintura.stock = 2
        self.pintura.save(update_fields=['stock'])
        self.client.force_login(self.usuario)

        response = self.client.post(
            reverse('agregar_calculo_pintura_carrito'),
            {
                'producto': self.pintura.id, 'superficie': 51,
                'ambiente': 'interior', 'tipo_superficie': 'hormigon',
                'estado_superficie': 'nueva', 'terminacion': 'cualquiera',
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Venta.objects.filter(id_usuario=self.usuario).exists())

    def test_no_agrega_una_pintura_incompatible_con_el_proyecto(self):
        self.client.force_login(self.usuario)

        response = self.client.post(
            reverse('agregar_calculo_pintura_carrito'),
            {
                'producto': self.pintura.id,
                'superficie': 51,
                'ambiente': 'exterior',
                'tipo_superficie': 'hormigon',
                'estado_superficie': 'nueva',
                'terminacion': 'cualquiera',
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Venta.objects.filter(id_usuario=self.usuario).exists())

    def test_no_agrega_una_pintura_con_terminacion_distinta(self):
        self.client.force_login(self.usuario)

        response = self.client.post(
            reverse('agregar_calculo_pintura_carrito'),
            {
                'producto': self.pintura.id,
                'superficie': 51,
                'ambiente': 'interior',
                'tipo_superficie': 'hormigon',
                'estado_superficie': 'nueva',
                'terminacion': 'satinado',
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Venta.objects.filter(id_usuario=self.usuario).exists())


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SeguridadWebpayTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            rut='77777777-7', username='comprador', email='comprador@example.com',
            telefono='+56977777777', password='Ferremas!2026Clave',
        )
        self.producto = Producto.objects.create(
            nombre='Sierra', descripcion='Sierra', precio=15000,
            imagen='https://example.com/sierra.jpg', stock=8,
            categoria='Herramientas', activo=True,
        )
        self.venta = Venta.objects.create(id_usuario=self.usuario, total_venta=30000)
        Detalle.objects.create(id_venta=self.venta, producto=self.producto, cantidad_producto=2)
        self.client.force_login(self.usuario)

    def _iniciar_pago(self, tx):
        tx.create.return_value = {
            'token': 'token-webpay-seguro',
            'url': 'https://webpay3gint.transbank.cl/webpayserver/initTransaction',
        }
        with patch('carro_compras.views._webpay_transaction', return_value=tx):
            response = self.client.post(
                reverse('iniciar_pago_webpay'),
                {'tipo_entrega': 'retiro'},
            )
        self.assertEqual(response.status_code, 302)
        self.venta.refresh_from_db()
        return response

    def _respuesta_autorizada(self, **overrides):
        response = {
            'status': 'AUTHORIZED',
            'response_code': 0,
            'buy_order': self.venta.webpay_buy_order,
            'session_id': self.venta.webpay_session_id,
            'amount': self.venta.webpay_amount,
            'card_detail': {'card_number': '6623'},
        }
        response.update(overrides)
        return response

    @patch.object(cliente_http_transbank.session, 'request')
    def test_cliente_transbank_exige_tls_y_endpoint_oficial(self, request):
        cliente_http_transbank.post(
            'https://webpay3gint.transbank.cl/rswebpaytransaction/api/webpay/v1.2/transactions/',
            data='{}',
        )

        self.assertEqual(request.call_args.args[0], 'POST')
        self.assertTrue(request.call_args.kwargs['verify'])
        with self.assertRaisesMessage(ValueError, 'endpoints oficiales'):
            cliente_http_transbank.post('https://example.com/transaccion')
        with self.assertRaisesMessage(ValueError, 'endpoints oficiales'):
            cliente_http_transbank.post(
                'http://webpay3gint.transbank.cl/rswebpaytransaction/api/webpay/v1.2/transactions/'
            )

    def test_factory_conecta_solo_el_sdk_al_cliente_tls_dedicado(self):
        cliente_anterior = sdk_request_service.requests
        try:
            _webpay_transaction()
            self.assertIs(sdk_request_service.requests, cliente_http_transbank)
        finally:
            sdk_request_service.requests = cliente_anterior

    def test_iniciar_pago_congela_total_y_referencia(self):
        tx = Mock()

        self._iniciar_pago(tx)

        self.assertEqual(self.venta.estado_venta, 'pago_pendiente')
        self.assertEqual(self.venta.webpay_amount, 30000)
        self.assertEqual(self.venta.webpay_transaction_id, 'token-webpay-seguro')
        self.assertTrue(self.venta.webpay_buy_order)
        self.assertTrue(self.venta.webpay_session_id)

    def test_inicio_ajax_entrega_url_sin_navegar_al_endpoint_api(self):
        tx = Mock()
        tx.create.return_value = {
            'token': 'token-webpay-seguro',
            'url': 'https://webpay3gint.transbank.cl/webpayserver/initTransaction',
        }

        with patch('carro_compras.views._webpay_transaction', return_value=tx):
            response = self.client.post(
                reverse('iniciar_pago_webpay'),
                {'tipo_entrega': 'retiro'},
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
                HTTP_ACCEPT='application/json',
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['redirect_url'].startswith('https://webpay3gint.transbank.cl/'))

    def test_volver_desde_webpay_reabre_el_carrito(self):
        tx = Mock()
        self._iniciar_pago(tx)

        response = self.client.post(reverse('cancelar_pago_webpay'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['cancelled'])
        self.venta.refresh_from_db()
        self.assertEqual(self.venta.estado_venta, 'carrito')
        self.assertIsNone(self.venta.webpay_transaction_id)

    def test_iniciar_pago_rechaza_redireccion_fuera_de_transbank(self):
        tx = Mock()
        tx.create.return_value = {
            'token': 'token-webpay-seguro',
            'url': 'https://sitio-malicioso.example/robar-token',
        }

        with patch('carro_compras.views._webpay_transaction', return_value=tx):
            response = self.client.post(
                reverse('iniciar_pago_webpay'), {'tipo_entrega': 'retiro'}
            )

        self.assertEqual(response.status_code, 502)
        self.venta.refresh_from_db()
        self.assertEqual(self.venta.estado_venta, 'carrito')
        self.assertIsNone(self.venta.webpay_transaction_id)

    def test_callback_malformado_deja_pago_pendiente_para_revision(self):
        tx = Mock()
        self._iniciar_pago(tx)
        tx.commit.return_value = ['respuesta', 'inválida']

        with patch('carro_compras.views._webpay_transaction', return_value=tx):
            response = self.client.post(
                reverse('respuesta_pago_webpay'), {'token_ws': 'token-webpay-seguro'}
            )

        self.assertEqual(response.status_code, 502)
        self.venta.refresh_from_db()
        self.assertEqual(self.venta.estado_venta, 'pago_pendiente')

    def test_monto_manipulado_revierte_pago_y_no_descuenta_stock(self):
        tx = Mock()
        self._iniciar_pago(tx)
        tx.commit.return_value = self._respuesta_autorizada(amount=1)

        with patch('carro_compras.views._webpay_transaction', return_value=tx):
            response = self.client.post(
                reverse('respuesta_pago_webpay'), {'token_ws': 'token-webpay-seguro'}
            )

        self.assertEqual(response.status_code, 409)
        tx.refund.assert_called_once_with('token-webpay-seguro', 1)
        self.venta.refresh_from_db()
        self.producto.refresh_from_db()
        self.assertEqual(self.venta.estado_venta, 'carrito')
        self.assertEqual(self.producto.stock, 8)

    def test_pago_confirmado_descuenta_stock_una_sola_vez(self):
        tx = Mock()
        self._iniciar_pago(tx)
        tx.commit.return_value = self._respuesta_autorizada()

        with patch('carro_compras.views._webpay_transaction', return_value=tx):
            primera = self.client.post(
                reverse('respuesta_pago_webpay'), {'token_ws': 'token-webpay-seguro'}
            )
            segunda = self.client.post(
                reverse('respuesta_pago_webpay'), {'token_ws': 'token-webpay-seguro'}
            )

        self.assertEqual(primera.status_code, 200)
        self.assertEqual(segunda.status_code, 200)
        self.producto.refresh_from_db()
        self.venta.refresh_from_db()
        self.assertEqual(self.producto.stock, 6)
        self.assertEqual(self.venta.estado_venta, 'pagado')
        self.assertEqual(tx.commit.call_count, 1)
