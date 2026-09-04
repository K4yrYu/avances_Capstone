from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from carro_compras.models import Detalle, Venta
from productos.models import Producto
from usuarios.models import Usuario


class HomeSfiTests(TestCase):
    def setUp(self):
        Producto.objects.all().delete()
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
        self.assertContains(response, reverse('calculadora_pintura'))
        self.assertContains(response, 'Compra la pintura justa para tu proyecto')
        self.assertNotContains(response, 'images.unsplash.com')
        self.assertEqual(response.context['total_productos'], 1)
        self.assertEqual(response.context['total_categorias'], 1)

    def test_panel_admin_muestra_grafico_y_filtra_categoria(self):
        admin = Usuario.objects.create_user(
            rut='87654321-4', username='admin_grafico', email='grafico@example.com',
            telefono='+56987654321', password='ClaveSegura!2026', is_staff=True,
        )
        venta = Venta.objects.create(
            id_usuario=admin, estado_venta='pagado', fecha_compra=timezone.now(),
            total_venta=self.producto.precio * 2,
        )
        Detalle.objects.create(
            id_venta=venta, producto=self.producto, cantidad_producto=2,
            subtotal_venta=self.producto.precio * 2,
        )
        self.client.force_login(admin)

        response = self.client.get(reverse('panel_administracion'), {
            'ventas_periodo': 30, 'ventas_categoria': 'Herramientas',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['categoria_ventas'], 'Herramientas')
        self.assertEqual(response.context['productos_mas_vendidos'][0]['vendidas'], 2)
        self.assertContains(response, 'dashboard-sales-chart')
        self.assertContains(response, 'dashboard-sales-column')
        self.assertContains(response, 'Mostrar gráfico')
        self.assertGreater(response.context['productos_mas_vendidos'][0]['altura_grafico'], 0)

    @override_settings(DEBUG=False)
    def test_error_404_usa_pantalla_personalizada_sfi(self):
        response = self.client.get('/pagina-que-no-existe/')

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, 'Página no encontrada', status_code=404)
        self.assertContains(response, 'ERROR 404', status_code=404)
        self.assertContains(response, 'img/frieren.gif', status_code=404)
