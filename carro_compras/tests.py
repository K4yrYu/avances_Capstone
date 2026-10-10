from unittest.mock import Mock, patch
from decimal import Decimal
from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.db.models.deletion import ProtectedError
from transbank.common import request_service as sdk_request_service

from productos.models import Producto
from usuarios.models import Usuario
from .models import (
    ConfiguracionDespacho,
    DespachoVenta,
    Detalle,
    DetalleDespacho,
    FechaDespacho,
    Venta,
)
from .services.transbank_tls import cliente_http_transbank
from .views import _webpay_transaction
from movimientos.models import MovimientoInventario
from transbank.common.integration_commerce_codes import IntegrationCommerceCodes


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

    def test_abrir_carrito_sincroniza_precio_unitario_subtotal_y_total(self):
        self.producto.precio = 1990
        self.producto.save(update_fields=['precio'])
        self.client.force_login(self.dueno)

        response = self.client.get(reverse('vista_carrito'))

        self.assertEqual(response.status_code, 200)
        self.detalle.refresh_from_db()
        self.venta.refresh_from_db()
        self.assertEqual(self.detalle.precio_unitario, 1990)
        self.assertEqual(self.detalle.subtotal_venta, 3980)
        self.assertEqual(self.venta.total_venta, 3980)
        self.assertContains(response, 'data-clp="1990"')
        self.assertContains(response, 'data-clp="3980"')


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

    def test_factory_test_usa_credencial_oficial_del_sdk(self):
        transaccion = _webpay_transaction()
        self.assertEqual(transaccion.options.commerce_code, IntegrationCommerceCodes.WEBPAY_PLUS)

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
        self.assertEqual(
            MovimientoInventario.objects.filter(
                origen=MovimientoInventario.Origen.VENTA,
                producto_id_original=self.producto.pk,
            ).count(),
            1,
        )

    def test_pago_rechazado_no_descuenta_stock_ni_registra_salida(self):
        tx = Mock()
        self._iniciar_pago(tx)
        tx.commit.return_value = self._respuesta_autorizada(
            status='FAILED',
            response_code=-1,
        )

        with patch('carro_compras.views._webpay_transaction', return_value=tx):
            respuesta = self.client.post(
                reverse('respuesta_pago_webpay'),
                {'token_ws': 'token-webpay-seguro'},
            )

        self.producto.refresh_from_db()
        self.venta.refresh_from_db()
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self.producto.stock, 8)
        self.assertEqual(self.venta.estado_venta, 'carrito')
        self.assertFalse(
            MovimientoInventario.objects.filter(
                origen=MovimientoInventario.Origen.VENTA,
                producto_id_original=self.producto.pk,
            ).exists()
        )

    def test_precio_enviado_por_frontend_no_reemplaza_precio_del_catalogo(self):
        producto = Producto.objects.create(
            nombre='Taladro', descripcion='Taladro', precio=45990,
            imagen='https://example.com/taladro.jpg', stock=4,
            categoria='Herramientas', activo=True,
        )

        response = self.client.post(
            reverse('agregar_producto_carrito'),
            {'producto': producto.pk, 'cantidad_producto': 1, 'precio': 1},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        detalle = Detalle.objects.get(id_venta=self.venta, producto=producto)
        self.assertEqual(detalle.precio_unitario, 45990)
        self.assertEqual(detalle.subtotal_venta, 45990)

    def test_iniciar_pago_actualiza_precio_y_total_desde_catalogo(self):
        detalle = self.venta.detalles.get()
        Detalle.objects.filter(pk=detalle.pk).update(
            precio_unitario=10000,
            subtotal_venta=20000,
        )
        Venta.objects.filter(pk=self.venta.pk).update(total_venta=20000)
        self.producto.precio = 12000
        self.producto.save(update_fields=['precio'])
        tx = Mock()

        self._iniciar_pago(tx)

        detalle.refresh_from_db()
        self.assertEqual(detalle.precio_unitario, 12000)
        self.assertEqual(detalle.subtotal_venta, 24000)
        self.assertEqual(self.venta.total_venta, 24000)
        self.assertEqual(self.venta.webpay_amount, 24000)
        self.assertEqual(tx.create.call_args.kwargs['amount'], 24000)

    def test_iniciar_pago_rechaza_stock_insuficiente_sin_llamar_webpay(self):
        self.producto.stock = 1
        self.producto.save(update_fields=['stock'])
        tx = Mock()

        with patch('carro_compras.views._webpay_transaction', return_value=tx):
            response = self.client.post(
                reverse('iniciar_pago_webpay'),
                {'tipo_entrega': 'retiro'},
            )

        self.assertEqual(response.status_code, 409)
        tx.create.assert_not_called()
        self.venta.refresh_from_db()
        self.assertEqual(self.venta.estado_venta, 'carrito')

    def test_iniciar_pago_rechaza_producto_inactivo_sin_llamar_webpay(self):
        self.producto.activo = False
        self.producto.save(update_fields=['activo'])
        tx = Mock()

        with patch('carro_compras.views._webpay_transaction', return_value=tx):
            response = self.client.post(
                reverse('iniciar_pago_webpay'),
                {'tipo_entrega': 'retiro'},
            )

        self.assertEqual(response.status_code, 409)
        tx.create.assert_not_called()
        self.venta.refresh_from_db()
        self.assertEqual(self.venta.estado_venta, 'carrito')

    def test_precio_queda_congelado_despues_de_iniciar_pago(self):
        tx = Mock()
        self._iniciar_pago(tx)
        detalle = self.venta.detalles.get()
        precio_congelado = detalle.precio_unitario
        self.producto.precio = 99999
        self.producto.save(update_fields=['precio'])
        tx.commit.return_value = self._respuesta_autorizada()

        with patch('carro_compras.views._webpay_transaction', return_value=tx):
            response = self.client.post(
                reverse('respuesta_pago_webpay'),
                {'token_ws': 'token-webpay-seguro'},
            )

        self.assertEqual(response.status_code, 200)
        detalle.refresh_from_db()
        self.venta.refresh_from_db()
        self.assertEqual(detalle.precio_unitario, precio_congelado)
        self.assertEqual(self.venta.total_venta, precio_congelado * 2)

    def test_eliminar_producto_pagado_conserva_detalle_y_boleta(self):
        detalle = self.venta.detalles.get()
        self.venta.estado_venta = 'pagado'
        self.venta.save(update_fields=['estado_venta'])
        nombre = detalle.nombre_producto
        precio = detalle.precio_unitario

        self.producto.delete()

        detalle.refresh_from_db()
        self.venta.refresh_from_db()
        self.assertIsNone(detalle.producto_id)
        self.assertEqual(detalle.nombre_producto, nombre)
        self.assertEqual(detalle.precio_unitario, precio)
        response = self.client.get(reverse('ver_boleta', args=[self.venta.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, nombre)
        self.assertContains(response, 'Producto hist')

    def test_usuario_con_venta_pagada_no_puede_eliminarse_fisicamente(self):
        self.venta.estado_venta = 'pagado'
        self.venta.save(update_fields=['estado_venta'])

        with self.assertRaises(ProtectedError):
            self.usuario.delete()

        self.assertTrue(Usuario.objects.filter(pk=self.usuario.pk).exists())
        self.assertTrue(Venta.objects.filter(pk=self.venta.pk).exists())


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ProgramacionDespachosTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            rut='12345678-5', username='cliente_despacho',
            email='despacho@example.com', telefono='+56912345678',
            password='Ferremas!2026Clave',
        )
        self.admin = Usuario.objects.create_user(
            rut='11111111-1', username='admin_despacho',
            email='admin-despacho@example.com', telefono='+56911111111',
            password='Ferremas!2026Clave', is_staff=True,
        )
        self.producto = Producto.objects.create(
            nombre='Cemento de prueba', descripcion='Producto para despacho',
            precio=10000, imagen='productos/cemento.webp', stock=20,
            categoria='Construcción', activo=True,
        )
        self.venta = Venta.objects.create(id_usuario=self.usuario, total_venta=20000)
        self.detalle = Detalle.objects.create(
            id_venta=self.venta,
            producto=self.producto,
            cantidad_producto=2,
        )
        self.configuracion = ConfiguracionDespacho.cargar()
        self.configuracion.cargo_segundo_despacho = 6500
        self.configuracion.capacidad_diaria = 2
        self.configuracion.dias_anticipacion_minima = 1
        self.configuracion.dias_horizonte = 30
        self.configuracion.save()
        self.fecha_1 = timezone.localdate() + timedelta(days=2)
        self.fecha_2 = timezone.localdate() + timedelta(days=3)
        self.client.force_login(self.usuario)

    def _iniciar_despacho(self, cantidad=1, fecha_2=None):
        tx = Mock()
        tx.create.return_value = {
            'token': 'token-despacho-seguro',
            'url': 'https://webpay3gint.transbank.cl/webpayserver/initTransaction',
        }
        datos = {
            'tipo_entrega': 'despacho',
            'region_despacho': 'RM',
            'comuna_despacho': 'Santiago',
            'calle_despacho': 'Avenida Siempre Viva',
            'numero_despacho': '742',
            'referencia_despacho': 'Casa de prueba',
            'cantidad_despachos': cantidad,
            'fecha_despacho_1': self.fecha_1.isoformat(),
        }
        if cantidad == 2:
            datos.update({
                'fecha_despacho_2': (fecha_2 or self.fecha_2).isoformat(),
                f'detalle_{self.detalle.id}_despacho_1': 1,
            })
        with patch('carro_compras.views._webpay_transaction', return_value=tx):
            respuesta = self.client.post(
                reverse('iniciar_pago_webpay'),
                datos,
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
                HTTP_ACCEPT='application/json',
            )
        return respuesta, tx

    def test_un_despacho_reserva_fecha_sin_cargo(self):
        respuesta, tx = self._iniciar_despacho()

        self.assertEqual(respuesta.status_code, 200)
        self.venta.refresh_from_db()
        despacho = self.venta.despachos.get()
        self.assertEqual(despacho.fecha_programada, self.fecha_1)
        self.assertEqual(despacho.cargo, 0)
        self.assertEqual(self.venta.webpay_amount, 20000)
        self.assertEqual(tx.create.call_args.kwargs['amount'], 20000)

    def test_dos_despachos_cobran_cargo_y_distribuyen_cantidades(self):
        respuesta, tx = self._iniciar_despacho(cantidad=2)

        self.assertEqual(respuesta.status_code, 200)
        self.venta.refresh_from_db()
        despachos = list(self.venta.despachos.order_by('numero'))
        self.assertEqual(len(despachos), 2)
        self.assertEqual(self.venta.cargo_despacho, 6500)
        self.assertEqual(self.venta.webpay_amount, 26500)
        self.assertEqual(tx.create.call_args.kwargs['amount'], 26500)
        self.assertEqual(
            list(DetalleDespacho.objects.filter(despacho__in=despachos).values_list('cantidad', flat=True)),
            [1, 1],
        )

    def test_webpay_confirma_total_con_cargo_y_programa_ambos_despachos(self):
        respuesta, _ = self._iniciar_despacho(cantidad=2)
        self.assertEqual(respuesta.status_code, 200)
        self.venta.refresh_from_db()
        tx = Mock()
        tx.commit.return_value = {
            'status': 'AUTHORIZED',
            'response_code': 0,
            'buy_order': self.venta.webpay_buy_order,
            'session_id': self.venta.webpay_session_id,
            'amount': self.venta.webpay_amount,
            'card_detail': {'card_number': '1234'},
        }

        with patch('carro_compras.views._webpay_transaction', return_value=tx):
            confirmacion = self.client.post(
                reverse('respuesta_pago_webpay'),
                {'token_ws': 'token-despacho-seguro'},
            )

        self.venta.refresh_from_db()
        self.producto.refresh_from_db()
        self.assertEqual(confirmacion.status_code, 200)
        self.assertEqual(self.venta.estado_venta, 'pagado')
        self.assertEqual(self.venta.total_venta, 26500)
        self.assertEqual(self.producto.stock, 18)
        self.assertEqual(
            set(self.venta.despachos.values_list('estado', flat=True)),
            {DespachoVenta.Estado.PROGRAMADO},
        )

    def test_dos_despachos_rechazan_la_misma_fecha(self):
        respuesta, tx = self._iniciar_despacho(cantidad=2, fecha_2=self.fecha_1)

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('fechas diferentes', respuesta.json()['error'])
        tx.create.assert_not_called()
        self.assertFalse(self.venta.despachos.exists())

    def test_despacho_rechaza_comuna_que_no_pertenece_a_region(self):
        respuesta = self.client.post(
            reverse('iniciar_pago_webpay'),
            {
                'tipo_entrega': 'despacho',
                'region_despacho': 'RM',
                'comuna_despacho': 'Valparaíso',
                'calle_despacho': 'Avenida Principal',
                'numero_despacho': '123',
                'cantidad_despachos': 1,
                'fecha_despacho_1': self.fecha_1.isoformat(),
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json',
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('región y comuna válidas', respuesta.json()['error'])
        self.assertFalse(self.venta.despachos.exists())

    def test_fecha_cerrada_no_acepta_nuevos_despachos(self):
        FechaDespacho.objects.create(fecha=self.fecha_1, cerrada=True, motivo='Feriado')

        respuesta, tx = self._iniciar_despacho()

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('cerrada', respuesta.json()['error'])
        tx.create.assert_not_called()

    def test_fecha_completa_no_acepta_mas_despachos(self):
        self.configuracion.capacidad_diaria = 1
        self.configuracion.save(update_fields=['capacidad_diaria'])
        otra_venta = Venta.objects.create(
            id_usuario=self.admin,
            estado_venta='pagado',
            tipo_entrega='despacho',
            total_venta=10000,
        )
        DespachoVenta.objects.create(
            venta=otra_venta,
            numero=1,
            fecha_programada=self.fecha_1,
            direccion='Dirección ya programada',
            estado=DespachoVenta.Estado.PROGRAMADO,
        )

        respuesta, tx = self._iniciar_despacho()

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn('no tiene cupos', respuesta.json()['error'])
        tx.create.assert_not_called()

    def test_admin_actualiza_cargo_y_capacidad(self):
        self.client.force_login(self.admin)
        respuesta = self.client.post(reverse('vista_despachos'), {
            'accion': 'configuracion',
            'cargo_segundo_despacho': 7990,
            'capacidad_diaria': 12,
            'dias_anticipacion_minima': 2,
            'dias_horizonte': 45,
            'despachos_activos': 'on',
        })

        self.assertEqual(respuesta.status_code, 302)
        self.configuracion.refresh_from_db()
        self.assertEqual(self.configuracion.cargo_segundo_despacho, 7990)
        self.assertEqual(self.configuracion.capacidad_diaria, 12)

    def test_carrito_y_panel_muestran_controles_de_programacion(self):
        carrito = self.client.get(reverse('vista_carrito'))
        self.assertContains(carrito, 'id="programacion-despacho"')
        self.assertContains(carrito, 'name="cantidad_despachos"')
        self.assertContains(carrito, 'id="distribucion-despachos"')
        self.assertContains(carrito, 'id="modal-distribucion-despachos"')
        self.assertContains(carrito, 'data-dispatch-product')

        self.client.force_login(self.admin)
        panel = self.client.get(reverse('vista_despachos'))
        self.assertContains(panel, 'Configuración de despachos')
        self.assertContains(panel, 'Cerrar para nuevos despachos')
        self.assertContains(panel, 'Capacidad de despacho')

    def test_disponibilidad_no_publica_fechas_cerradas_como_elegibles(self):
        FechaDespacho.objects.create(fecha=self.fecha_1, cerrada=True, motivo='Sin transporte')

        respuesta = self.client.get(reverse('api_disponibilidad_despachos'))

        self.assertEqual(respuesta.status_code, 200)
        fecha = next(
            item for item in respuesta.json()['fechas']
            if item['fecha'] == self.fecha_1.isoformat()
        )
        self.assertFalse(fecha['disponible'])
        self.assertTrue(fecha['cerrada'])

    def test_venta_se_completa_solo_al_entregar_ambos_despachos(self):
        self.venta.estado_venta = 'pagado'
        self.venta.tipo_entrega = 'despacho'
        self.venta.save(update_fields=['estado_venta', 'tipo_entrega'])
        primero = DespachoVenta.objects.create(
            venta=self.venta, numero=1, fecha_programada=self.fecha_1,
            direccion='Dirección', estado=DespachoVenta.Estado.PROGRAMADO,
        )
        segundo = DespachoVenta.objects.create(
            venta=self.venta, numero=2, fecha_programada=self.fecha_2,
            direccion='Dirección', estado=DespachoVenta.Estado.PROGRAMADO,
        )
        self.client.force_login(self.admin)

        primera_respuesta = self.client.post(
            reverse('api_confirmar_despacho', args=[primero.id])
        )
        self.venta.refresh_from_db()
        self.assertEqual(primera_respuesta.status_code, 200)
        self.assertEqual(self.venta.estado_entrega, 'pendiente')

        segunda_respuesta = self.client.post(
            reverse('api_confirmar_despacho', args=[segundo.id])
        )
        self.venta.refresh_from_db()
        self.assertEqual(segunda_respuesta.status_code, 200)
        self.assertEqual(self.venta.estado_entrega, 'completado')

    def test_api_admin_ordena_despachos_por_fecha_e_incluye_contacto(self):
        self.venta.estado_venta = 'pagado'
        self.venta.tipo_entrega = 'despacho'
        self.venta.save(update_fields=['estado_venta', 'tipo_entrega'])
        segundo = DespachoVenta.objects.create(
            venta=self.venta, numero=2, fecha_programada=self.fecha_2,
            direccion='Calle Prueba 123, Santiago', estado=DespachoVenta.Estado.PROGRAMADO,
        )
        primero = DespachoVenta.objects.create(
            venta=self.venta, numero=1, fecha_programada=self.fecha_1,
            direccion='Calle Prueba 123, Santiago', estado=DespachoVenta.Estado.PROGRAMADO,
        )
        DetalleDespacho.objects.create(despacho=primero, detalle=self.detalle, cantidad=1)
        DetalleDespacho.objects.create(despacho=segundo, detalle=self.detalle, cantidad=1)
        self.client.force_login(self.admin)

        respuesta = self.client.get(reverse('api_despachos'))

        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()
        self.assertEqual([item['id'] for item in datos], [primero.id, segundo.id])
        self.assertEqual(datos[0]['comprador_email'], self.usuario.email)
        self.assertEqual(datos[0]['comprador_telefono'], self.usuario.telefono)
        self.assertEqual(datos[0]['detalles'][0]['nombre_producto'], self.detalle.nombre_producto)

    def test_vista_repartidor_requiere_rol_o_administrador(self):
        respuesta_cliente = self.client.get(reverse('vista_repartidor_despachos'))
        self.assertEqual(respuesta_cliente.status_code, 302)

        self.usuario.rol = Usuario.Rol.REPARTIDOR
        self.usuario.save(update_fields=['rol'])
        respuesta_repartidor = self.client.get(reverse('vista_repartidor_despachos'))
        self.assertEqual(respuesta_repartidor.status_code, 200)

        self.client.force_login(self.admin)
        respuesta_admin = self.client.get(reverse('vista_repartidor_despachos'))
        self.assertEqual(respuesta_admin.status_code, 200)

    def test_repartidor_actualiza_estado_en_orden(self):
        self.venta.estado_venta = 'pagado'
        self.venta.tipo_entrega = 'despacho'
        self.venta.save(update_fields=['estado_venta', 'tipo_entrega'])
        despacho = DespachoVenta.objects.create(
            venta=self.venta, numero=1, fecha_programada=self.fecha_1,
            direccion='Calle Prueba 123, Santiago', estado=DespachoVenta.Estado.PROGRAMADO,
        )
        self.usuario.rol = Usuario.Rol.REPARTIDOR
        self.usuario.save(update_fields=['rol'])

        salto_invalido = self.client.patch(
            reverse('api_actualizar_estado_despacho', args=[despacho.id]),
            {'estado': 'entregado'}, content_type='application/json',
        )
        self.assertEqual(salto_invalido.status_code, 400)

        en_ruta = self.client.patch(
            reverse('api_actualizar_estado_despacho', args=[despacho.id]),
            {'estado': 'en_ruta'}, content_type='application/json',
        )
        self.assertEqual(en_ruta.status_code, 200)

        entregado = self.client.patch(
            reverse('api_actualizar_estado_despacho', args=[despacho.id]),
            {'estado': 'entregado'}, content_type='application/json',
        )
        self.assertEqual(entregado.status_code, 200)
        despacho.refresh_from_db()
        self.venta.refresh_from_db()
        self.assertEqual(despacho.estado, DespachoVenta.Estado.ENTREGADO)
        self.assertEqual(self.venta.estado_entrega, 'completado')

    def test_encargado_retiros_accede_a_retiros_pero_no_a_despachos(self):
        self.usuario.rol = Usuario.Rol.RETIROS
        self.usuario.save(update_fields=['rol'])

        retiros = self.client.get(reverse('vista_retiros'))
        despachos = self.client.get(reverse('vista_repartidor_despachos'))
        api_retiros = self.client.get(reverse('api_retiros'))

        self.assertEqual(retiros.status_code, 200)
        self.assertEqual(api_retiros.status_code, 200)
        self.assertEqual(despachos.status_code, 302)
