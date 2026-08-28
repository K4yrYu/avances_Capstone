from django.core.management.base import BaseCommand

from usuarios.services import limpiar_cuentas_no_verificadas


class Command(BaseCommand):
    help = 'Elimina cuentas de clientes no verificadas cuya activación ya expiró.'

    def handle(self, *args, **options):
        cantidad = limpiar_cuentas_no_verificadas()
        self.stdout.write(self.style.SUCCESS(
            f'Limpieza completada: {cantidad} cuenta(s) pendiente(s) eliminada(s).'
        ))
