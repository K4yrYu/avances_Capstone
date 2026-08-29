from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core import mail
from django.core.cache import cache
from django.core.signing import TimestampSigner
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token

from .models import Usuario
from .middleware import LimpiezaCuentasPendientesMiddleware
from .serializers import RegistroUsuarioSerializer
from .services import limpiar_cuentas_no_verificadas
from .throttles import RegistroRateThrottle


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
)
class SeguridadUsuariosTests(TestCase):
    password = 'Ferremas!2026Clave'

    def setUp(self):
        cache.clear()
        self.payload = {
            'rut': '12345678-5',
            'username': 'cliente_seguro',
            'first_name': 'Cliente',
            'last_name': 'Seguro',
            'email': 'cliente@example.com',
            'telefono': '+56912345678',
            'password': self.password,
            'password2': self.password,
        }

    def test_registro_publico_no_puede_crear_administrador(self):
        payload = {**self.payload, 'is_staff': True, 'is_superuser': True, 'is_active': True}

        response = self.client.post(reverse('api_registro'), payload, content_type='application/json')

        self.assertEqual(response.status_code, 201)
        usuario = Usuario.objects.get(username='cliente_seguro')
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)
        self.assertFalse(usuario.is_active)
        self.assertFalse(usuario.email_confirmado)
        self.assertIsNotNone(usuario.correo_activacion_enviado_en)
        self.assertIsNotNone(usuario.activacion_expira_en)
        self.assertAlmostEqual(
            (usuario.activacion_expira_en - usuario.correo_activacion_enviado_en).total_seconds(),
            24 * 60 * 60,
            delta=2,
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('será eliminado', mail.outbox[0].body)

    def test_registro_rechaza_contrasena_debil(self):
        payload = {**self.payload, 'password': '1', 'password2': '1'}

        serializer = RegistroUsuarioSerializer(data=payload)

        self.assertFalse(serializer.is_valid())
        self.assertIn('password', serializer.errors)

    def test_registro_permite_diez_solicitudes_en_ventana_de_tres_minutos(self):
        throttle = RegistroRateThrottle()
        throttle.scope = 'register'

        solicitudes, duracion = throttle.parse_rate('10/3minutes')

        self.assertEqual(solicitudes, 10)
        self.assertEqual(duracion, 180)

    def test_email_es_unico_sin_importar_mayusculas_en_api(self):
        Usuario.objects.create_user(
            rut='11111111-1', username='existente', email='cliente@example.com',
            telefono='+56911111111', password=self.password,
        )
        payload = {**self.payload, 'email': 'CLIENTE@EXAMPLE.COM'}

        response = self.client.post(reverse('api_registro'), payload, content_type='application/json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('email', response.json())

    def test_login_reemplaza_token_anterior(self):
        usuario = Usuario.objects.create_user(
            rut='22222222-2', username='login_seguro', email='login@example.com',
            telefono='+56922222222', password=self.password, is_active=True,
        )
        token_anterior = Token.objects.create(user=usuario).key

        response = self.client.post(
            reverse('api_login'),
            {'username': usuario.username, 'password': self.password},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.json()['token'], token_anterior)
        self.assertEqual(Token.objects.filter(user=usuario).count(), 1)

    def test_enlace_de_activacion_no_reactiva_usuario_suspendido(self):
        usuario = Usuario.objects.create_user(
            rut='33333333-3', username='suspendido', email='suspendido@example.com',
            telefono='+56933333333', password=self.password,
            is_active=False, email_confirmado=True,
        )
        token = TimestampSigner().sign(usuario.email)

        response = self.client.get(reverse('activar_cuenta', args=[token]))

        self.assertEqual(response.status_code, 200)
        usuario.refresh_from_db()
        self.assertFalse(usuario.is_active)

    def test_activacion_valida_protege_la_cuenta_de_la_limpieza(self):
        usuario = Usuario.objects.create_user(
            rut='44444444-4', username='por_activar', email='activar@example.com',
            telefono='+56944444444', password=self.password,
            is_active=False, email_confirmado=False,
            correo_activacion_enviado_en=timezone.now(),
            activacion_expira_en=timezone.now() + timedelta(hours=24),
        )
        token = TimestampSigner().sign(usuario.email)

        response = self.client.get(reverse('activar_cuenta', args=[token]))

        self.assertEqual(response.status_code, 200)
        usuario.refresh_from_db()
        self.assertTrue(usuario.is_active)
        self.assertTrue(usuario.email_confirmado)
        self.assertIsNone(usuario.activacion_expira_en)
        self.assertEqual(limpiar_cuentas_no_verificadas(), 0)
        self.assertTrue(Usuario.objects.filter(pk=usuario.pk).exists())

    def test_limpieza_elimina_solo_cuenta_publica_vencida(self):
        vencida = Usuario.objects.create_user(
            rut='55555555-5', username='vencida', email='vencida@example.com',
            telefono='+56955555555', password=self.password,
            is_active=False, email_confirmado=False,
            correo_activacion_enviado_en=timezone.now() - timedelta(hours=25),
            activacion_expira_en=timezone.now() - timedelta(hours=1),
        )
        activada = Usuario.objects.create_user(
            rut='66666666-6', username='activada', email='activada@example.com',
            telefono='+56966666666', password=self.password,
            is_active=True, email_confirmado=True,
            correo_activacion_enviado_en=timezone.now() - timedelta(days=2),
            activacion_expira_en=timezone.now() - timedelta(days=1),
        )
        creada_por_admin = Usuario.objects.create_user(
            rut='77777777-7', username='administrativa', email='admin-creada@example.com',
            telefono='+56977777777', password=self.password,
            is_active=False, email_confirmado=False,
        )

        eliminadas = limpiar_cuentas_no_verificadas()

        self.assertEqual(eliminadas, 1)
        self.assertFalse(Usuario.objects.filter(pk=vencida.pk).exists())
        self.assertTrue(Usuario.objects.filter(pk=activada.pk).exists())
        self.assertTrue(Usuario.objects.filter(pk=creada_por_admin.pk).exists())

    def test_enlace_con_expiracion_persistida_no_activa_usuario(self):
        usuario = Usuario.objects.create_user(
            rut='88888888-8', username='expirado', email='expirado@example.com',
            telefono='+56988888888', password=self.password,
            is_active=False, email_confirmado=False,
            correo_activacion_enviado_en=timezone.now() - timedelta(hours=25),
            activacion_expira_en=timezone.now() - timedelta(seconds=1),
        )
        token = TimestampSigner().sign(usuario.email)

        response = self.client.get(reverse('activar_cuenta', args=[token]))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Usuario.objects.filter(pk=usuario.pk).exists())

    def test_limpieza_diaria_usa_las_cuatro_de_la_madrugada_en_chile(self):
        request = RequestFactory().get('/')
        middleware = LimpiezaCuentasPendientesMiddleware(
            lambda _request: HttpResponse('ok')
        )
        hora_chile = ZoneInfo('America/Santiago')

        with patch(
            'usuarios.middleware.timezone.localtime',
            return_value=datetime(2026, 8, 24, 3, 59, tzinfo=hora_chile),
        ), patch(
            'usuarios.middleware.limpiar_cuentas_no_verificadas'
        ) as limpiar:
            middleware(request)
            limpiar.assert_not_called()

        cache.clear()
        with patch(
            'usuarios.middleware.timezone.localtime',
            return_value=datetime(2026, 8, 24, 4, 0, tzinfo=hora_chile),
        ), patch(
            'usuarios.middleware.limpiar_cuentas_no_verificadas',
            return_value=0,
        ) as limpiar:
            middleware(request)
            middleware(request)
            limpiar.assert_called_once_with()

