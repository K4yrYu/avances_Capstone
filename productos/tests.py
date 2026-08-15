import base64
import tempfile
from decimal import Decimal

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from usuarios.models import Usuario
from .models import HistorialPrecio, Producto, Proveedor, SolicitudReposicion
from .serializers import ProductoSerializer


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SeguridadProductosTests(TestCase):
    def setUp(self):
        self.producto = Producto.objects.create(
            nombre='Taladro', descripcion='Taladro seguro', precio=50000,
            imagen='https://example.com/taladro.jpg', stock=10,
            categoria='Herramientas', activo=True, marca='Bauker',
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

    def test_catalogo_publico_usa_identidad_sfi_y_controles_de_orden(self):
        response = self.client.get(reverse('lista_productos'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Catálogo SFI')
        self.assertContains(response, 'id="buscador-productos"')
        self.assertContains(response, 'id="filtro-categoria"')
        self.assertContains(response, 'id="orden-productos"')
        self.assertContains(response, reverse('api_lista_productos'))

    def test_precio_invalido_no_genera_error_500_ni_historial(self):
        self.client.force_login(self.admin)
        payload = {
            'nombre': self.producto.nombre,
            'descripcion': self.producto.descripcion,
            'precio': 'no-es-numero',
            'stock': self.producto.stock,
            'categoria': self.producto.categoria,
            'marca': self.producto.marca,
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
            'activo': True, 'marca': 'Bauker',
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
            'activo': True, 'marca': 'Bauker', 'imagen': imagen,
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
                        'marca': 'Bauker',
                        'activo': True,
                        'imagen': imagen,
                    },
                )

                self.assertEqual(response.status_code, 201, response.content)
                producto = Producto.objects.get(nombre='Alicate profesional')
                self.assertTrue(producto.imagen.name.startswith('productos/'))

    def test_ficha_de_pintura_verificada_exige_datos_de_calculo(self):
        serializer = ProductoSerializer(
            self.producto,
            data={
                'tipo_calculo': 'pintura',
                'informacion_tecnica_verificada': True,
            },
            partial=True,
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn('contenido', serializer.errors)
        self.assertIn('rendimiento', serializer.errors)
        self.assertIn('capas_recomendadas', serializer.errors)
        self.assertIn('ambiente_uso', serializer.errors)

    def test_ficha_de_pintura_completa_queda_apta_para_calculo(self):
        serializer = ProductoSerializer(
            self.producto,
            data={
                'marca': 'Pinturas SFI',
                'unidad_venta': 'envase',
                'contenido': '4.000',
                'unidad_contenido': 'l',
                'tipo_calculo': 'pintura',
                'ambiente_uso': 'interior',
                'superficies_compatibles': ['hormigon', 'pasta_muro'],
                'tipo_pintura': 'latex',
                'terminacion': 'mate',
                'propiedades_pintura': ['base_agua', 'bajo_olor'],
                'preparaciones_recomendadas': ['limpieza', 'sellador'],
                'repintado_min_horas': '3.00',
                'repintado_max_horas': '6.00',
                'rendimiento': '10.000',
                'unidad_rendimiento': 'm2_l',
                'capas_recomendadas': 2,
                'porcentaje_desperdicio': '10.00',
                'informacion_tecnica_verificada': True,
                'especificaciones': {'Terminación': 'Mate'},
            },
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        producto = serializer.save()
        self.assertTrue(producto.apto_para_calculo)
        self.assertEqual(producto.ambiente_uso, 'interior')
        self.assertEqual(producto.superficies_compatibles, ['hormigon', 'pasta_muro'])
        self.assertEqual(producto.presentacion, '4 L')

    def test_api_publica_ficha_tecnica_estructurada(self):
        self.producto.marca = 'Bauker'
        self.producto.modelo = 'PRO-1'
        self.producto.save(update_fields=['marca', 'modelo'])

        response = self.client.get(reverse('api_lista_productos'))

        self.assertEqual(response.status_code, 200)
        producto = next(item for item in response.json() if item['id'] == self.producto.id)
        self.assertEqual(producto['marca'], 'Bauker')
        self.assertEqual(producto['modelo'], 'PRO-1')
        self.assertIn('presentacion', producto)
        self.assertIn('apto_para_calculo', producto)

    def test_crear_y_editar_comparten_formulario_profesional(self):
        self.client.force_login(self.admin)

        crear = self.client.get(reverse('formulario_producto'))
        editar = self.client.get(reverse('editar_producto', args=[self.producto.id]))

        self.assertContains(crear, 'id="tipo_calculo"')
        self.assertContains(crear, 'id="informacion_tecnica_verificada"')
        self.assertContains(editar, 'data-mode="edit"')
        self.assertContains(editar, self.producto.nombre)

    def test_color_se_descarta_en_productos_que_no_son_pintura(self):
        serializer = ProductoSerializer(
            self.producto,
            data={'color': 'Azul', 'color_hex': '#315B7D'},
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        producto = serializer.save()
        self.assertEqual(producto.color, '')
        self.assertEqual(producto.color_hex, '')

    def test_admin_puede_crear_proveedor_desde_formulario_producto(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse('crear_proveedor'),
            {'nombre': 'Proveedor formulario', 'email': 'pedidos-formulario@example.com'},
            HTTP_ACCEPT='application/json',
        )

        self.assertEqual(response.status_code, 201, response.content)
        proveedor = Proveedor.objects.get(nombre='Proveedor formulario')
        self.assertEqual(response.json()['id'], proveedor.id)
        self.assertEqual(response.json()['email'], proveedor.email)

    def test_directorio_muestra_productos_por_proveedor(self):
        proveedor = Proveedor.objects.create(
            nombre='Proveedor directorio', email='directorio@example.com',
        )
        self.producto.proveedor = proveedor
        self.producto.save(update_fields=['proveedor'])
        self.client.force_login(self.admin)

        response = self.client.get(reverse('gestion_proveedores'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, proveedor.nombre)
        self.assertContains(response, self.producto.nombre)


class CalculadoraPinturaTests(TestCase):
    def setUp(self):
        self.pintura = Producto.objects.create(
            nombre='Pintura calculable', descripcion='Pintura con ficha comprobada',
            precio=20000, imagen='productos/pintura-calculo.webp', stock=5,
            categoria='Pinturas', marca='SFI', color='Blanco', color_hex='#FFFFFF',
            ambiente_uso='interior_exterior',
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

    def test_calculo_usa_rendimiento_capas_margen_y_envases_completos(self):
        response = self.client.post(
            reverse('api_calcular_pintura'),
            {
                'superficie': 51, 'color': 'Blanco', 'ambiente': 'interior',
                'tipo_superficie': 'hormigon', 'estado_superficie': 'nueva',
                'terminacion': 'cualquiera',
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200, response.content)
        item = next(resultado for resultado in response.json()['recomendaciones'] if resultado['producto_id'] == self.pintura.id)
        self.assertEqual(Decimal(str(item['litros_necesarios'])), Decimal('12'))
        self.assertEqual(item['cantidad_envases'], 3)
        self.assertEqual(Decimal(str(item['sobrante_estimado'])), Decimal('0'))
        self.assertEqual(item['presupuesto_total'], 60000)
        self.assertTrue(item['stock_suficiente'])
        self.assertEqual(item['ambiente_uso'], 'interior_exterior')
        self.assertEqual(item['ambiente_uso_display'], 'Interior y exterior')
        self.assertEqual(item['estado_superficie'], 'nueva')
        self.assertEqual(
            item['preparacion_proyecto_display'],
            ['Limpiar y secar', 'Aplicar sellador'],
        )

    def test_calculadora_filtra_la_terminacion_solicitada(self):
        response = self.client.post(
            reverse('api_calcular_pintura'),
            {
                'superficie': 50, 'ambiente': 'interior',
                'tipo_superficie': 'hormigon', 'estado_superficie': 'nueva',
                'terminacion': 'satinado',
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertNotIn(
            self.pintura.id,
            [item['producto_id'] for item in response.json()['recomendaciones']],
        )

    def test_calculadora_advierte_antes_de_pintar_sobre_humedad(self):
        response = self.client.post(
            reverse('api_calcular_pintura'),
            {
                'superficie': 50, 'ambiente': 'interior',
                'tipo_superficie': 'hormigon', 'estado_superficie': 'humedad',
                'terminacion': 'mate',
            },
            content_type='application/json',
        )

        item = next(
            resultado for resultado in response.json()['recomendaciones']
            if resultado['producto_id'] == self.pintura.id
        )
        self.assertIn('Corrige primero el origen de la humedad', item['advertencia_preparacion'])

    def test_api_rechaza_superficie_invalida(self):
        response = self.client.post(
            reverse('api_calcular_pintura'),
            {
                'superficie': '50.5', 'ambiente': 'interior',
                'tipo_superficie': 'hormigon', 'estado_superficie': 'nueva',
                'terminacion': 'cualquiera',
            },
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('superficie', response.json())

    def test_pintura_sin_ficha_verificada_no_se_recomienda(self):
        self.pintura.informacion_tecnica_verificada = False
        self.pintura.save(update_fields=['informacion_tecnica_verificada'])

        response = self.client.post(
            reverse('api_calcular_pintura'),
            {
                'superficie': 50, 'color': 'Blanco', 'ambiente': 'interior',
                'tipo_superficie': 'hormigon', 'estado_superficie': 'nueva',
                'terminacion': 'cualquiera',
            },
            content_type='application/json',
        )

        ids = [item['producto_id'] for item in response.json()['recomendaciones']]
        self.assertNotIn(self.pintura.id, ids)

    def test_calculadora_excluye_ambiente_y_superficie_incompatibles(self):
        self.pintura.ambiente_uso = 'interior'
        self.pintura.save(update_fields=['ambiente_uso'])

        exterior = self.client.post(
            reverse('api_calcular_pintura'),
            {
                'superficie': 50, 'ambiente': 'exterior',
                'tipo_superficie': 'hormigon', 'estado_superficie': 'nueva',
                'terminacion': 'cualquiera',
            },
            content_type='application/json',
        )
        madera = self.client.post(
            reverse('api_calcular_pintura'),
            {
                'superficie': 50, 'ambiente': 'interior',
                'tipo_superficie': 'madera', 'estado_superficie': 'nueva',
                'terminacion': 'cualquiera',
            },
            content_type='application/json',
        )

        self.assertNotIn(
            self.pintura.id,
            [item['producto_id'] for item in exterior.json()['recomendaciones']],
        )
        self.assertNotIn(
            self.pintura.id,
            [item['producto_id'] for item in madera.json()['recomendaciones']],
        )

    def test_productos_ofrece_acceso_sin_quitar_protagonismo_al_catalogo(self):
        response = self.client.get(reverse('lista_productos'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="product-list"')
        self.assertContains(response, reverse('calculadora_pintura'))
        self.assertNotContains(response, 'id="paint-calculator-form"')

    def test_calculadora_tiene_un_apartado_exclusivo(self):
        response = self.client.get(reverse('calculadora_pintura'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="paint-calculator-form"')
        self.assertContains(response, 'id="estado_superficie"')
        self.assertContains(response, 'id="terminacion"')
        self.assertContains(response, reverse('agregar_calculo_pintura_carrito'))


@override_settings(
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='SFI <pedidos@sfi.local>',
)
class ReposicionInventarioTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user(
            rut='55555555-5', username='admin_reposicion', email='admin-reposicion@example.com',
            telefono='+56955555555', password='Ferremas!2026Clave', is_staff=True,
        )
        self.proveedor = Proveedor.objects.create(
            nombre='Proveedor de prueba', email='compras@example.com', activo=True,
        )
        self.producto = Producto.objects.create(
            nombre='Pintura prueba azul', descripcion='Pintura para probar reposicion',
            precio=24990, imagen='productos/prueba.webp', stock=4, stock_minimo=10,
            categoria='Pinturas', marca='Sipa', color='Azul', color_hex='#315B7D',
            proveedor=self.proveedor, activo=True,
        )
        self.client.force_login(self.admin)

    def test_admin_puede_enviar_solicitud_por_correo(self):
        response = self.client.post(reverse('crear_solicitud_reposicion'), {
            'proveedor_id': self.proveedor.id,
            'productos': [self.producto.id],
            f'cantidad_{self.producto.id}': 16,
            'observaciones': 'Entregar durante la manana.',
        })

        solicitud = SolicitudReposicion.objects.get(proveedor=self.proveedor)
        self.assertRedirects(response, reverse('gestion_reposicion'))
        self.assertEqual(solicitud.estado, 'enviada')
        self.assertEqual(solicitud.items.get().cantidad_solicitada, 16)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['compras@example.com'])
        self.assertIn(solicitud.numero, mail.outbox[0].subject)

    def test_producto_sobre_el_minimo_no_puede_solicitarse(self):
        self.producto.stock = 11
        self.producto.save(update_fields=['stock'])

        response = self.client.post(reverse('crear_solicitud_reposicion'), {
            'proveedor_id': self.proveedor.id,
            'productos': [self.producto.id],
            f'cantidad_{self.producto.id}': 10,
        })

        self.assertRedirects(response, reverse('gestion_reposicion'))
        self.assertFalse(SolicitudReposicion.objects.filter(proveedor=self.proveedor).exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_recibir_solicitud_actualiza_stock_una_sola_vez(self):
        self.client.post(reverse('crear_solicitud_reposicion'), {
            'proveedor_id': self.proveedor.id,
            'productos': [self.producto.id],
            f'cantidad_{self.producto.id}': 16,
        })
        solicitud = SolicitudReposicion.objects.get(proveedor=self.proveedor)

        response = self.client.post(reverse('recibir_solicitud_reposicion', args=[solicitud.id]))
        repetida = self.client.post(reverse('recibir_solicitud_reposicion', args=[solicitud.id]))

        self.producto.refresh_from_db()
        solicitud.refresh_from_db()
        self.assertRedirects(response, reverse('gestion_reposicion'))
        self.assertRedirects(repetida, reverse('gestion_reposicion'))
        self.assertEqual(self.producto.stock, 20)
        self.assertEqual(solicitud.estado, 'recibida')
