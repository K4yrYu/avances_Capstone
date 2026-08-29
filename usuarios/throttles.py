from rest_framework.throttling import ScopedRateThrottle


class RegistroRateThrottle(ScopedRateThrottle):
    """Limita el registro a diez solicitudes dentro de tres minutos por IP."""

    VENTANA_SEGUNDOS = 3 * 60

    def parse_rate(self, rate):
        if rate is None:
            return None, None

        solicitudes, _, _periodo = rate.partition('/')
        return int(solicitudes), self.VENTANA_SEGUNDOS
