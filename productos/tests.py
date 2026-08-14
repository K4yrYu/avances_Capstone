import base64
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from usuarios.models import Usuario
from .models import HistorialPrecio, Producto
from .serializers import ProductoSerializer


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SeguridadProductosTests(TestCase):
    def setUp(self):
        self.producto = Producto.objects.create(
            nombre='Taladro', descripcion='Taladro seguro', precio=50000,
            imagen='https://example.com/taladro.jpg', stock=10,
            categoria='Herramientas', activo=True,
        )
        self.admin = Usuario.objects.create_user(
            rut='44444444-4', username='admin_productos', email='admin-productos@example.com',
            telefono='+56944444444', password='Ferremas!2026Clave', is_staff=True,
        )

    def test_producto_inactivo_no_es_visible_publicamente(self):
        self.producto.activo = False
        self.producto.save(update_fields=['activo'])

        response = self.client.get(reverse('detalle_producto', args=[self.producto.id]))

        self.assertEqual(response.status_code, 404)

    def test_precio_invalido_no_genera_error_500_ni_historial(self):
        self.client.force_login(self.admin)
        payload = {
            'nombre': self.producto.nombre,
            'descripcion': self.producto.descripcion,
            'precio': 'no-es-numero',
            'stock': self.producto.stock,
            'categoria': self.producto.categoria,
            'activo': True,
        }

        response = self.client.put(
            reverse('api_editar_producto', args=[self.producto.id]),
            payload,
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(HistorialPrecio.objects.count(), 0)

    def test_nuevo_producto_exige_archivo_de_imagen(self):
        datos = {
            'nombre': 'Alicate', 'descripcion': 'Alicate universal',
            'precio': 12990, 'stock': 5, 'categoria': 'Herramientas',
            'activo': True,
        }

        serializer = ProductoSerializer(data=datos)

        self.assertFalse(serializer.is_valid())
        self.assertIn('imagen', serializer.errors)

    def test_nuevo_producto_acepta_imagen_subida(self):
        imagen = SimpleUploadedFile(
            'alicate.png',
            base64.b64decode(
                'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
            ),
            content_type='image/png',
        )
        datos = {
            'nombre': 'Alicate', 'descripcion': 'Alicate universal',
            'precio': 12990, 'stock': 5, 'categoria': 'Herramientas',
            'activo': True, 'imagen': imagen,
        }

        serializer = ProductoSerializer(data=datos)

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_api_guarda_imagen_subida_en_media(self):
        imagen = SimpleUploadedFile(
            'alicate.png',
            base64.b64decode(
                'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII='
            ),
            content_type='image/png',
        )
        self.client.force_login(self.admin)
        with tempfile.TemporaryDirectory() as media_temporal:
            with self.settings(MEDIA_ROOT=media_temporal):
                response = self.client.post(
                    reverse('api_agregar_producto'),
                    {
                        'nombre': 'Alicate profesional',
                        'descripcion': 'Alicate universal aislado',
                        'precio': 15990,
                        'stock': 12,
                        'categoria': 'Herramientas',
                        'activo': True,
                        'imagen': imagen,
                    },
                )

                self.assertEqual(response.status_code, 201, response.content)
                producto = Producto.objects.get(nombre='Alicate profesional')
                self.assertTrue(producto.imagen.name.startswith('productos/'))
