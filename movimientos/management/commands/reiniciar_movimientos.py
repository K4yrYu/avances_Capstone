from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from productos.models import Producto

from movimientos.models import MovimientoInventario
from movimientos.services import datos_historicos_producto


class Command(BaseCommand):
    help = "Reinicia el Kardex y crea un saldo inicial desde el stock actual de cada producto."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirmar",
            action="store_true",
            help="Confirma la eliminación del historial actual.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if not options["confirmar"]:
            raise CommandError("Debes usar --confirmar después de generar un respaldo.")

        eliminados, _ = MovimientoInventario.objects.all().delete()
        iniciales = []
        for producto in Producto.objects.all().iterator():
            iniciales.append(MovimientoInventario(
                **datos_historicos_producto(producto),
                tipo=MovimientoInventario.Tipo.INICIAL,
                estado=MovimientoInventario.Estado.APLICADO,
                origen=MovimientoInventario.Origen.STOCK_INICIAL,
                cantidad_solicitada=producto.stock,
                cantidad_movida=producto.stock,
                entrada=producto.stock,
                stock_anterior=0,
                stock_resultante=producto.stock,
                observacion="Nueva base inicial del Kardex.",
                clave_idempotencia=f"reinicio-stock-inicial:{producto.pk}",
            ))
        MovimientoInventario.objects.bulk_create(iniciales)
        self.stdout.write(self.style.SUCCESS(
            f"Historial reiniciado: {eliminados} registros retirados y "
            f"{len(iniciales)} saldos iniciales creados."
        ))
