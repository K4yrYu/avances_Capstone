from django.db.models import Q
from django.utils import timezone

from .models import Usuario


def cuentas_no_verificadas_vencidas():
    return Usuario.objects.filter(
        is_active=False,
        email_confirmado=False,
        activacion_expira_en__isnull=False,
        activacion_expira_en__lte=timezone.now(),
    )


def limpiar_cuentas_no_verificadas(*, email='', rut='', username=''):
    cuentas = cuentas_no_verificadas_vencidas()
    identificadores = Q()
    if email:
        identificadores |= Q(email__iexact=email)
    if rut:
        identificadores |= Q(rut__iexact=rut)
    if username:
        identificadores |= Q(username__iexact=username)
    if identificadores:
        cuentas = cuentas.filter(identificadores)
    cantidad = cuentas.count()
    cuentas.delete()
    return cantidad
