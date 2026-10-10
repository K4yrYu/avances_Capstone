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
from .serializers import AdminUsuarioSerializer, RegistroUsuarioSerializer
from .serializers import UsuarioListaSerializer
from maestros.models import PerfilMaestro
from .services import limpiar_cuentas_no_verificadas
from .throttles import RegistroRateThrottle
from .validators import calcular_digito_verificador_rut, validar_rut


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
        payload = {**self.payload, 'rol': 'administrador', 'is_staff': True, 'is_superuser': True, 'is_active': True}

        response = self.client.post(reverse('api_registro'), payload, content_type='application/json')

        self.assertEqual(response.status_code, 201)
        usuario = Usuario.objects.get(username='cliente_seguro')
        self.assertFalse(usuario.is_staff)
        self.assertFalse(usuario.is_superuser)
        self.assertFalse(usuario.is_active)
        self.assertFalse(usuario.email_confirmado)
        self.assertEqual(usuario.rol, Usuario.Rol.CLIENTE)
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

    def test_calculo_modulo_11_del_rut(self):
        self.assertEqual(calcular_digito_verificador_rut('12345678'), '5')
        self.assertEqual(calcular_digito_verificador_rut('1000005'), 'K')
        self.assertEqual(validar_rut('12.345.678-5'), '12345678-5')

    def test_registro_publico_rechaza_rut_con_digito_incorrecto(self):
        response = self.client.post(
            reverse('api_registro'),
            {**self.payload, 'rut': '12345678-9'},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('rut', response.json())
        self.assertFalse(Usuario.objects.filter(username='cliente_seguro').exists())

    def test_registro_publico_normaliza_rut_con_puntos(self):
        response = self.client.post(
            reverse('api_registro'),
            {**self.payload, 'rut': '12.345.678-5'},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Usuario.objects.get(username='cliente_seguro').rut, '12345678-5')

    def test_registro_administrativo_rechaza_rut_invalido(self):
        serializer = AdminUsuarioSerializer(data={
            **self.payload,
            'rut': '12345678-9',
            'username': 'creado_por_admin',
            'email': 'creado-por-admin@example.com',
            'is_staff': False,
        })

        self.assertFalse(serializer.is_valid())
        self.assertIn('rut', serializer.errors)

    def test_admin_puede_crear_perfiles_operativos_separados(self):
        casos = (
            ('11111111-1', Usuario.Rol.REPARTIDOR),
            ('22222222-2', Usuario.Rol.RETIROS),
        )
        for indice, (rut, rol) in enumerate(casos, start=1):
            serializer = AdminUsuarioSerializer(data={
                **self.payload,
                'rut': rut,
                'username': f'operativo_{indice}',
                'email': f'operativo-{indice}@example.com',
                'rol': rol,
            })
            self.assertTrue(serializer.is_valid(), serializer.errors)
            usuario = serializer.save()
            self.assertEqual(usuario.rol, rol)
            self.assertFalse(usuario.is_staff)

    def test_listado_clasifica_como_maestro_a_quien_tiene_perfil(self):
        usuario = Usuario.objects.create_user(
            rut='11111111-1', username='maestro_listado', email='maestro-listado@example.com',
            telefono='+56911111111', password=self.password,
        )
        PerfilMaestro.objects.create(
            usuario=usuario,
            descripcion_profesional='Maestro de prueba',
            anos_experiencia=5,
            region='RM',
            comuna='Santiago',
            zonas_trabajo='Santiago',
        )

        datos = UsuarioListaSerializer(usuario).data

        self.assertEqual(datos['rol'], 'maestro')

    def test_edicion_conserva_rut_legacy_si_no_se_modifica(self):
        usuario = Usuario.objects.create_user(
            rut='11111111-1', username='legacy', email='legacy@example.com',
            telefono='+56911111111', password=self.password,
        )
        serializer = AdminUsuarioSerializer(
            usuario,
            data={'rut': '11111111-1', 'first_name': 'Actualizado'},
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        actualizado = serializer.save()
        self.assertEqual(actualizado.rut, '11111111-1')
        self.assertEqual(actualizado.first_name, 'Actualizado')

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

