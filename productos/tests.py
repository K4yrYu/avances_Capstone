import base64
import tempfile
from datetime import timedelta
from decimal import Decimal

from django.core import mail
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import Sum
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from usuarios.models import Usuario
from .models import HistorialPrecio, Producto, Proveedor, SolicitudReposicion
from .serializers import ProductoSerializer
from movimientos.models import MovimientoInventario


class CatalogoBanoTests(TestCase):
    SKUS = {
        'BAN-POR-144', 'BAN-CER-150', 'BAN-ADH-25', 'BAN-FRA-5',
        'BAN-IMP-4', 'BAN-SEP-100', 'BAN-SIL-300', 'BAN-WC-DD',
        'BAN-MUE-60', 'BAN-GRI-LV', 'BAN-KIT-LV', 'BAN-DUC-CRO',
    }

    def test_catalogo_bano_tiene_fichas_tecnicas_e_imagenes_locales(self):
        productos = list(Producto.objects.filter(sku__in=self.SKUS))

        self.assertEqual(len(productos), len(self.SKUS))
        for producto in productos:
            self.assertTrue(producto.informacion_tecnica_verificada)
            self.assertTrue(producto.especificaciones)
            self.assertTrue(producto.uso_recomendado)
            self.assertTrue(producto.imagen.name.startswith('productos/bano/'))
            self.assertTrue(default_storage.exists(producto.imagen.name))
            self.assertGreater(producto.precio, 0)
            self.assertGreater(producto.stock, 0)

    def test_materiales_por_superficie_tienen_rendimiento_verificado(self):
        materiales = Producto.objects.filter(
            sku__in={'BAN-POR-144', 'BAN-CER-150', 'BAN-ADH-25', 'BAN-FRA-5', 'BAN-IMP-4'},
        )

        self.assertEqual(materiales.count(), 5)
        for producto in materiales:
            self.assertEqual(producto.tipo_calculo, 'superficie')
            self.assertEqual(producto.unidad_rendimiento, 'm2_unidad')
            self.assertGreater(producto.rendimiento, 0)


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

    def test_edicion_valida_actualiza_producto_y_registra_movimiento(self):
        self.client.force_login(self.admin)
        response = self.client.put(
            reverse('api_editar_producto', args=[self.producto.id]),
            {'nombre': 'Taladro actualizado', 'precio': 45990},
            content_type='application/json',
        )

        self.producto.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.producto.nombre, 'Taladro actualizado')
        self.assertEqual(self.producto.precio, 45990)
        movimiento = MovimientoInventario.objects.filter(
            producto_id_original=self.producto.pk,
            tipo=MovimientoInventario.Tipo.MODIFICACION,
        ).latest('id')
        self.assertIn('nombre', movimiento.cambios)
        self.assertIn('precio', movimiento.cambios)
        self.assertEqual(movimiento.responsable, self.admin)

    def test_edicion_rechaza_cambio_directo_de_stock(self):
        self.client.force_login(self.admin)
        response = self.client.put(
            reverse('api_editar_producto', args=[self.producto.id]),
            {'stock': 999},
            content_type='application/json',
        )

        self.producto.refresh_from_db()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.producto.stock, 10)
        self.assertIn('stock', response.json())

    def test_formulario_edicion_muestra_stock_solo_lectura(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('editar_producto', args=[self.producto.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'readonly aria-readonly="true"')

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
        self.producto.sku = 'SFI-TEST-PRO-1'
        self.producto.save(update_fields=['marca', 'modelo', 'sku'])

        response = self.client.get(reverse('api_lista_productos'))

        self.assertEqual(response.status_code, 200)
        producto = next(item for item in response.json() if item['id'] == self.producto.id)
        self.assertEqual(producto['marca'], 'Bauker')
        self.assertEqual(producto['modelo'], 'PRO-1')
        self.assertEqual(producto['sku'], 'SFI-TEST-PRO-1')
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
        movimiento = MovimientoInventario.objects.get(
            tipo=MovimientoInventario.Tipo.SOLICITUD,
            producto=self.producto,
        )
        self.assertEqual(movimiento.cantidad_solicitada, 16)
        self.assertEqual(movimiento.proveedor_nombre, self.proveedor.nombre)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 4)
        pagina = self.client.get(reverse('gestion_reposicion'))
        self.assertContains(pagina, 'Confirmar recibo de productos')
        self.assertContains(pagina, f'id="recepcion-{solicitud.id}"')
        self.assertNotIn(self.producto, pagina.context['productos_alerta'])

    def test_panel_rotacion_solo_considera_ventas_pagadas(self):
        from carro_compras.models import Detalle, Venta

        producto_sin_ventas = Producto.objects.create(
            nombre='Producto sin ventas para rotación',
            descripcion='Producto usado para comprobar la baja rotación.',
            precio=1990,
            stock=10,
            stock_minimo=2,
            categoria=self.producto.categoria,
            activo=True,
        )

        venta_pagada = Venta.objects.create(
            id_usuario=self.admin,
            total_venta=self.producto.precio * 3,
            estado_venta='pagado',
            fecha_compra=timezone.now() - timedelta(days=2),
        )
        Detalle.objects.create(
            id_venta=venta_pagada,
            producto=self.producto,
            cantidad_producto=3,
            precio_unitario=self.producto.precio,
            subtotal_venta=self.producto.precio * 3,
        )
        venta_pendiente = Venta.objects.create(
            id_usuario=self.admin,
            total_venta=self.producto.precio * 7,
            estado_venta='pago_pendiente',
        )
        Detalle.objects.create(
            id_venta=venta_pendiente,
            producto=self.producto,
            cantidad_producto=7,
            precio_unitario=self.producto.precio,
            subtotal_venta=self.producto.precio * 7,
        )

        response = self.client.get(reverse('gestion_reposicion'), {'periodo': 30})

        self.assertEqual(response.status_code, 200)
        rotacion = {
            item['id']: item for item in response.context['rotacion_productos']
        }
        self.assertEqual(rotacion[self.producto.pk]['vendidas'], 3)
        self.assertTrue(any(
            item['vendidas'] == 0
            for item in response.context['baja_rotacion']
        ))
        self.assertTrue(any(
            item['vendidas'] > 0
            for item in response.context['baja_rotacion']
        ))
        self.assertContains(response, 'Selecciona una barra para ver detalles')
        self.assertContains(response, 'Baja rotación')
        self.assertContains(response, 'Aplicar')

        filtrada = self.client.get(reverse('gestion_reposicion'), {
            'periodo': 30, 'categoria': 'Pinturas',
        })
        self.assertEqual(filtrada.status_code, 200)
        self.assertEqual(filtrada.context['categoria_rotacion'], 'Pinturas')
        self.assertTrue(all(
            item['categoria'] == 'Pinturas'
            for item in filtrada.context['rotacion_productos']
        ))

    def test_producto_con_pedido_enviado_no_puede_solicitarse_otra_vez(self):
        datos = {
            'proveedor_id': self.proveedor.id,
            'productos': [self.producto.id],
            f'cantidad_{self.producto.id}': 16,
        }

        self.client.post(reverse('crear_solicitud_reposicion'), datos)
        respuesta_repetida = self.client.post(
            reverse('crear_solicitud_reposicion'), datos
        )

        self.assertRedirects(respuesta_repetida, reverse('gestion_reposicion'))
        self.assertEqual(SolicitudReposicion.objects.count(), 1)

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

    def test_solicitud_permite_observacion_vacia(self):
        response = self.client.post(reverse('crear_solicitud_reposicion'), {
            'proveedor_id': self.proveedor.id,
            'productos': [self.producto.id],
            f'cantidad_{self.producto.id}': 16,
            'observaciones': '',
        })

        solicitud = SolicitudReposicion.objects.get(proveedor=self.proveedor)
        self.assertRedirects(response, reverse('gestion_reposicion'))
        self.assertEqual(solicitud.observaciones, '')
        self.assertEqual(len(mail.outbox), 1)

    def test_recibir_solicitud_actualiza_stock_una_sola_vez(self):
        self.client.post(reverse('crear_solicitud_reposicion'), {
            'proveedor_id': self.proveedor.id,
            'productos': [self.producto.id],
            f'cantidad_{self.producto.id}': 16,
            'observaciones': 'Confirmar recepción completa.',
        })
        solicitud = SolicitudReposicion.objects.get(proveedor=self.proveedor)

        item = solicitud.items.get()
        datos = {
            'token_recepcion': 'recepcion-completa-prueba-unica',
            f'cantidad_{item.id}': 16,
            f'resultado_{item.id}': 'completo',
            f'motivo_{item.id}': '',
        }
        response = self.client.post(
            reverse('recibir_solicitud_reposicion', args=[solicitud.id]), datos
        )
        repetida = self.client.post(
            reverse('recibir_solicitud_reposicion', args=[solicitud.id]), datos
        )

        self.producto.refresh_from_db()
        solicitud.refresh_from_db()
        self.assertRedirects(response, reverse('gestion_reposicion'))
        self.assertRedirects(repetida, reverse('gestion_reposicion'))
        self.assertEqual(self.producto.stock, 20)
        self.assertEqual(solicitud.estado, 'recibida')
        self.assertEqual(
            MovimientoInventario.objects.filter(
                tipo=MovimientoInventario.Tipo.ENTRADA,
                producto=self.producto,
            ).count(),
            1,
        )

    def test_producto_no_recibido_permite_motivo_vacio_y_no_aumenta_stock(self):
        self.client.post(reverse('crear_solicitud_reposicion'), {
            'proveedor_id': self.proveedor.id,
            'productos': [self.producto.id],
            f'cantidad_{self.producto.id}': 16,
        })
        solicitud = SolicitudReposicion.objects.get(proveedor=self.proveedor)
        item = solicitud.items.get()
        url = reverse('recibir_solicitud_reposicion', args=[solicitud.id])

        self.client.post(url, {
            'token_recepcion': 'recepcion-no-llego-prueba-unica',
            f'cantidad_{item.id}': 0,
            f'resultado_{item.id}': 'no_llego',
            f'motivo_{item.id}': '',
        })
        self.producto.refresh_from_db()
        solicitud.refresh_from_db()
        self.assertEqual(self.producto.stock, 4)
        self.assertEqual(solicitud.estado, 'parcial')
        self.assertTrue(MovimientoInventario.objects.filter(
            tipo=MovimientoInventario.Tipo.INCIDENCIA,
            producto=self.producto,
        ).exists())
        incidencia = MovimientoInventario.objects.get(
            tipo=MovimientoInventario.Tipo.INCIDENCIA,
            producto=self.producto,
        )
        self.assertIn('No llegó', incidencia.referencia)
        self.assertIn('No llegó', incidencia.observacion)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[-1].to, [self.proveedor.email])
        self.assertIn('Incidencias de recepción', mail.outbox[-1].subject)
        self.assertIn(self.producto.nombre, mail.outbox[-1].body)
        pagina = self.client.get(reverse('gestion_reposicion'))
        self.assertIn(self.producto, pagina.context['productos_alerta'])
        self.assertEqual(len(pagina.context['solicitudes_activas']), 0)
        self.assertEqual(len(pagina.context['recepciones_historial']), 1)

    def test_recepcion_parcial_cierra_pendiente_y_vuelve_a_lista_de_compra(self):
        self.client.post(reverse('crear_solicitud_reposicion'), {
            'proveedor_id': self.proveedor.id,
            'productos': [self.producto.id],
            f'cantidad_{self.producto.id}': 16,
        })
        solicitud = SolicitudReposicion.objects.get(proveedor=self.proveedor)
        item = solicitud.items.get()
        url = reverse('recibir_solicitud_reposicion', args=[solicitud.id])

        self.client.post(url, {
            'token_recepcion': 'recepcion-parcial-prueba-primera',
            f'cantidad_{item.id}': 10,
            f'resultado_{item.id}': 'parcial',
            f'motivo_{item.id}': 'El proveedor dejo seis unidades pendientes.',
        })
        solicitud.refresh_from_db()
        self.producto.refresh_from_db()
        self.assertEqual(solicitud.estado, 'parcial')
        self.assertEqual(self.producto.stock, 14)
        pagina_parcial = self.client.get(reverse('gestion_reposicion'))
        self.assertEqual(len(pagina_parcial.context['solicitudes_activas']), 0)
        self.assertEqual(len(pagina_parcial.context['recepciones_historial']), 1)
        self.assertContains(pagina_parcial, '<b>10</b> recibido(s)', html=True)
        self.assertIn(self.producto, pagina_parcial.context['productos_alerta'])

        respuesta_repetida = self.client.post(url, {
            'token_recepcion': 'recepcion-parcial-prueba-segunda',
            f'cantidad_{item.id}': 6,
            f'resultado_{item.id}': 'completo',
            f'motivo_{item.id}': '',
        })
        solicitud.refresh_from_db()
        self.producto.refresh_from_db()
        self.assertRedirects(respuesta_repetida, reverse('gestion_reposicion'))
        self.assertEqual(solicitud.estado, 'parcial')
        self.assertEqual(self.producto.stock, 14)
        self.assertEqual(solicitud.recepciones.count(), 1)
        self.assertEqual(MovimientoInventario.objects.filter(
            tipo=MovimientoInventario.Tipo.ENTRADA,
            producto=self.producto,
        ).aggregate(total=Sum('entrada'))['total'], 10)

    def test_repetir_recepcion_con_incidencia_no_duplica_movimiento(self):
        self.client.post(reverse('crear_solicitud_reposicion'), {
            'proveedor_id': self.proveedor.id,
            'productos': [self.producto.id],
            f'cantidad_{self.producto.id}': 16,
        })
        solicitud = SolicitudReposicion.objects.get(proveedor=self.proveedor)
        item = solicitud.items.get()
        url = reverse('recibir_solicitud_reposicion', args=[solicitud.id])
        datos = {
            'token_recepcion': 'recepcion-incidencia-doble-click',
            f'cantidad_{item.id}': 0,
            f'resultado_{item.id}': 'no_llego',
            f'motivo_{item.id}': '',
        }

        self.client.post(url, datos)
        self.client.post(url, datos)

        self.assertEqual(solicitud.recepciones.count(), 1)
        self.assertEqual(MovimientoInventario.objects.filter(
            tipo=MovimientoInventario.Tipo.INCIDENCIA,
            producto=self.producto,
        ).count(), 1)
        self.assertEqual(len(mail.outbox), 2)
