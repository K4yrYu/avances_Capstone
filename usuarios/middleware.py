import logging

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .services import limpiar_cuentas_no_verificadas


logger = logging.getLogger(__name__)


class LimpiezaCuentasPendientesMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ahora = timezone.localtime()
        if ahora.hour >= settings.ACCOUNT_CLEANUP_HOUR:
            clave = f'limpieza-cuentas-pendientes:{ahora.date().isoformat()}'
            if cache.add(clave, True, timeout=60 * 60 * 26):
                try:
                    eliminadas = limpiar_cuentas_no_verificadas()
                    if eliminadas:
                        logger.info('Cuentas pendientes vencidas eliminadas: %s', eliminadas)
                except Exception:
                    cache.delete(clave)
                    logger.exception('No fue posible limpiar las cuentas pendientes vencidas.')
        return self.get_response(request)
