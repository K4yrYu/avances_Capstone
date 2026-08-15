from django.test import TestCase
from django.urls import reverse

from productos.models import Producto


class HomeSfiTests(TestCase):
    def setUp(self):
        self.producto = Producto.objects.create(
            nombre='Taladro de prueba SFI',
            descripcion='Producto creado para validar el inicio.',
            precio=29990,
            imagen='productos/producto-prueba.jpg',
            stock=7,
            categoria='Herramientas',
            activo=True,
        )

    def test_home_muestra_identidad_sfi_y_producto_destacado(self):
        response = self.client.get(reverse('index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sistema Ferretero Inteligente')
        self.assertContains(response, self.producto.nombre)
        self.assertContains(response, reverse('detalle_producto', args=[self.producto.id]))
        self.assertNotContains(response, 'images.unsplash.com')
        self.assertEqual(response.context['total_productos'], 1)
        self.assertEqual(response.context['total_categorias'], 1)
