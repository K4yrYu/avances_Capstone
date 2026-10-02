import re

from django.core.exceptions import ValidationError


RUT_CANONICO = re.compile(r'^(\d{7,8})([0-9K])$')


def normalizar_rut(rut):
    """Convierte un RUT con o sin puntos al formato canónico 12345678-5."""
    compacto = re.sub(r'[.\s-]', '', str(rut or '')).upper()
    coincidencia = RUT_CANONICO.fullmatch(compacto)
    if not coincidencia:
        raise ValidationError('El RUT debe tener el formato 12345678-9.')
    cuerpo, digito = coincidencia.groups()
    return f'{cuerpo}-{digito}'


def calcular_digito_verificador_rut(cuerpo):
    """Calcula el dígito verificador chileno mediante módulo 11."""
    cuerpo = str(cuerpo or '')
    if not cuerpo.isdigit() or len(cuerpo) not in (7, 8):
        raise ValidationError('El cuerpo del RUT debe contener 7 u 8 dígitos.')

    suma = 0
    factor = 2
    for digito in reversed(cuerpo):
        suma += int(digito) * factor
        factor = 2 if factor == 7 else factor + 1

    resultado = 11 - (suma % 11)
    if resultado == 11:
        return '0'
    if resultado == 10:
        return 'K'
    return str(resultado)


def validar_rut(rut):
    """Valida formato y dígito verificador, retornando el RUT normalizado."""
    normalizado = normalizar_rut(rut)
    cuerpo, digito = normalizado.split('-')
    if calcular_digito_verificador_rut(cuerpo) != digito:
        raise ValidationError('El RUT ingresado no es válido.')
    return normalizado
