from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from django.urls import reverse

from productos.models import Producto

from .models import LoteInventario, MovimientoInventario
from .services import descontar_lotes_fefo, registrar_movimiento_stock


class AccesoMovimientosTests(TestCase):
    def crear_usuario(self, username, staff=False):
        return get_user_model().objects.create_user(
            username=username,
            password="ClaveSegura2398!",
            email=f"{username}@example.com",
            rut="18654321-4" if staff else "17654321-9",
            telefono="+56912345678",
            email_confirmado=True,
            is_active=True,
            is_staff=staff,
        )

    def test_administrador_puede_abrir_movimientos(self):
        self.client.force_login(self.crear_usuario("admin_movimientos", staff=True))
        respuesta = self.client.get(reverse("movimientos:lista"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Movimientos")

    def test_usuario_normal_no_puede_abrir_movimientos(self):
        self.client.force_login(self.crear_usuario("cliente_movimientos"))
        respuesta = self.client.get(reverse("movimientos:lista"))
        self.assertEqual(respuesta.status_code, 302)


class RegistroHistoricoTests(TestCase):
    def setUp(self):
        self.producto = Producto.objects.create(
            nombre="Taladro histórico",
            descripcion="Producto para verificar movimientos.",
            precio=49990,
            imagen="productos/taladro-historico.jpg",
            stock=10,
            categoria="Herramientas",
            marca="SFI",
            modelo="TH-10",
            sku="MOV-TH-10",
        )

    def test_creacion_y_cambio_nombre_conservan_fotos_historicas(self):
        inicial = MovimientoInventario.objects.get(
            tipo=MovimientoInventario.Tipo.INICIAL,
            producto_id_original=self.producto.pk,
        )
        self.assertEqual(inicial.producto_nombre, "Taladro histórico")

        self.producto.nombre = "Taladro renombrado"
        self.producto.precio = 45990
        self.producto.save()

        modificacion = MovimientoInventario.objects.filter(tipo=MovimientoInventario.Tipo.MODIFICACION).latest("id")
        self.assertEqual(inicial.producto_nombre, "Taladro histórico")
        self.assertEqual(inicial.precio_unitario, 49990)
        self.assertEqual(modificacion.producto_nombre, "Taladro renombrado")
        self.assertIn("nombre", modificacion.cambios)
        self.assertIn("precio", modificacion.cambios)

    def test_salida_es_idempotente_y_actualiza_stock_una_vez(self):
        movimiento = registrar_movimiento_stock(
            producto_id=self.producto.pk,
            tipo=MovimientoInventario.Tipo.SALIDA,
            cantidad=3,
            origen=MovimientoInventario.Origen.VENTA,
            clave_idempotencia="venta:prueba:detalle:1",
        )
        repetido = registrar_movimiento_stock(
            producto_id=self.producto.pk,
            tipo=MovimientoInventario.Tipo.SALIDA,
            cantidad=3,
            origen=MovimientoInventario.Origen.VENTA,
            clave_idempotencia="venta:prueba:detalle:1",
        )
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.stock, 7)
        self.assertEqual(movimiento.pk, repetido.pk)

    def test_registro_sobrevive_a_eliminacion_del_producto(self):
        producto_id = self.producto.pk
        self.producto.delete()
        eliminacion = MovimientoInventario.objects.get(tipo=MovimientoInventario.Tipo.ELIMINACION)
        self.assertEqual(eliminacion.producto_id_original, producto_id)
        self.assertEqual(eliminacion.producto_nombre, "Taladro histórico")
        self.assertIsNone(eliminacion.producto)

    def test_movimiento_no_se_puede_editar_ni_eliminar(self):
        movimiento = MovimientoInventario.objects.get(
            tipo=MovimientoInventario.Tipo.INICIAL,
            producto_id_original=self.producto.pk,
        )
        movimiento.observacion = "Intento de edición"
        with self.assertRaises(ValidationError):
            movimiento.save()
        with self.assertRaises(ValidationError):
            movimiento.delete()


class AjusteManualTests(AccesoMovimientosTests):
    def test_ajuste_manual_registra_responsable_y_stock(self):
        admin = self.crear_usuario("admin_ajuste", staff=True)
        producto = Producto.objects.create(
            nombre="Producto ajustable", descripcion="Prueba", precio=1000,
            imagen="productos/ajuste.jpg", stock=5, sku="MOV-AJUSTE-1",
        )
        self.client.force_login(admin)
        respuesta = self.client.post(reverse("movimientos:registrar_ajuste"), {
            "producto": producto.pk,
            "nuevo_stock": 12,
            "observacion": "Conteo físico de inventario.",
        })
        producto.refresh_from_db()
        self.assertRedirects(respuesta, reverse("movimientos:lista"))
        self.assertEqual(producto.stock, 12)
        ajuste = MovimientoInventario.objects.get(tipo=MovimientoInventario.Tipo.AJUSTE)
        self.assertEqual(ajuste.entrada, 7)
        self.assertEqual(ajuste.responsable, admin)


class ReinicioKardexTests(TestCase):
    def test_reinicio_conserva_stock_y_crea_una_base_por_producto(self):
        producto = Producto.objects.create(
            nombre="Producto para reinicio", descripcion="Prueba", precio=2500,
            imagen="productos/reinicio.jpg", stock=14, sku="MOV-REINICIO-1",
        )
        registrar_movimiento_stock(
            producto_id=producto.pk,
            tipo=MovimientoInventario.Tipo.SALIDA,
            cantidad=2,
            origen=MovimientoInventario.Origen.VENTA,
        )
        producto.refresh_from_db()

        call_command("reiniciar_movimientos", confirmar=True, verbosity=0)

        producto.refresh_from_db()
        self.assertEqual(producto.stock, 12)
        self.assertEqual(MovimientoInventario.objects.count(), Producto.objects.count())
        inicial = MovimientoInventario.objects.get(producto_id_original=producto.pk)
        self.assertEqual(inicial.tipo, MovimientoInventario.Tipo.INICIAL)
        self.assertEqual(inicial.stock_resultante, 12)


class LotesFefoTests(TestCase):
    def test_descuenta_primero_el_lote_que_vence_antes(self):
        producto = Producto.objects.create(
            nombre='Sellador con lote', descripcion='Prueba FEFO', precio=8990,
            imagen='productos/sellador.jpg', stock=10, sku='FEFO-001',
            controla_vencimiento=True,
        )
        hoy = timezone.localdate()
        primero = LoteInventario.objects.create(
            producto=producto, lote='L-A', cantidad_disponible=4,
            fecha_ingreso=hoy, fecha_vencimiento=hoy + timedelta(days=30),
        )
        segundo = LoteInventario.objects.create(
            producto=producto, lote='L-B', cantidad_disponible=6,
            fecha_ingreso=hoy, fecha_vencimiento=hoy + timedelta(days=90),
        )

        descontar_lotes_fefo(producto_id=producto.pk, cantidad=5)

        primero.refresh_from_db()
        segundo.refresh_from_db()
        self.assertEqual(primero.cantidad_disponible, 0)
        self.assertEqual(segundo.cantidad_disponible, 5)

    def test_no_utiliza_lotes_vencidos(self):
        producto = Producto.objects.create(
            nombre='Adhesivo vencido', descripcion='Prueba', precio=5990,
            imagen='productos/adhesivo.jpg', stock=2, sku='FEFO-002',
            controla_vencimiento=True,
        )
        hoy = timezone.localdate()
        LoteInventario.objects.create(
            producto=producto, lote='VENCIDO', cantidad_disponible=2,
            fecha_ingreso=hoy - timedelta(days=60),
            fecha_vencimiento=hoy - timedelta(days=1),
        )

        with self.assertRaises(ValidationError):
            descontar_lotes_fefo(producto_id=producto.pk, cantidad=1)
