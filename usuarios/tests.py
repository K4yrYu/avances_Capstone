from django.core import mail
from django.core.cache import cache
from django.core.signing import TimestampSigner
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token

from .models import Usuario
from .serializers import RegistroUsuarioSerializer


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
        self.assertEqual(len(mail.outbox), 1)

    def test_registro_rechaza_contrasena_debil(self):
        payload = {**self.payload, 'password': '1', 'password2': '1'}

        serializer = RegistroUsuarioSerializer(data=payload)

        self.assertFalse(serializer.is_valid())
        self.assertIn('password', serializer.errors)

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

