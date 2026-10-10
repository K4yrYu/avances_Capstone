from datetime import date, timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import (
    ConfiguracionDespacho,
    DespachoVenta,
    DetalleDespacho,
    FechaDespacho,
)


class DespachoInvalidoError(Exception):
    pass


def _fecha_desde_valor(valor):
    try:
        return date.fromisoformat(str(valor or '').strip())
    except (TypeError, ValueError):
        raise DespachoInvalidoError('Selecciona una fecha de despacho válida.')


def _reservas_vigentes():
    ahora = timezone.now()
    return Q(estado__in=[
        DespachoVenta.Estado.PROGRAMADO,
        DespachoVenta.Estado.PREPARACION,
        DespachoVenta.Estado.EN_RUTA,
        DespachoVenta.Estado.ENTREGADO,
    ]) | Q(
        estado=DespachoVenta.Estado.RESERVADO,
        reserva_expira_en__gt=ahora,
    )


def capacidad_fecha(fecha, configuracion=None, bloquear=False):
    configuracion = configuracion or ConfiguracionDespacho.cargar()
    consulta = FechaDespacho.objects
    if bloquear:
        consulta = consulta.select_for_update()
    excepcion, _ = consulta.get_or_create(fecha=fecha)
    capacidad = (
        excepcion.capacidad_override
        if excepcion.capacidad_override is not None
        else configuracion.capacidad_diaria
    )
    ocupados = DespachoVenta.objects.filter(
        _reservas_vigentes(),
        fecha_programada=fecha,
    ).count()
    return {
        'fecha': fecha,
        'capacidad': capacidad,
        'ocupados': ocupados,
        'disponibles': max(capacidad - ocupados, 0),
        'cerrada': excepcion.cerrada,
        'motivo': excepcion.motivo,
    }


def fechas_disponibles():
    configuracion = ConfiguracionDespacho.cargar()
    hoy = timezone.localdate()
    inicio = hoy + timedelta(days=configuracion.dias_anticipacion_minima)
    fin = hoy + timedelta(days=configuracion.dias_horizonte)
    fechas = []
    actual = inicio
    while actual <= fin:
        estado = capacidad_fecha(actual, configuracion=configuracion)
        estado['disponible'] = bool(
            configuracion.despachos_activos
            and not estado['cerrada']
            and estado['disponibles'] > 0
        )
        fechas.append(estado)
        actual += timedelta(days=1)
    return configuracion, fechas


def _validar_fecha(fecha, configuracion):
    hoy = timezone.localdate()
    minimo = hoy + timedelta(days=configuracion.dias_anticipacion_minima)
    maximo = hoy + timedelta(days=configuracion.dias_horizonte)
    if fecha < minimo or fecha > maximo:
        raise DespachoInvalidoError(
            f'La fecha debe estar entre {minimo:%d/%m/%Y} y {maximo:%d/%m/%Y}.'
        )


def _cantidades_por_despacho(detalles, datos, cantidad_despachos):
    if cantidad_despachos == 1:
        return {
            1: {detalle.id: detalle.cantidad_producto for detalle in detalles},
        }

    asignaciones = {1: {}, 2: {}}
    for detalle in detalles:
        clave = f'detalle_{detalle.id}_despacho_1'
        try:
            primera = int(datos.get(clave, -1))
        except (TypeError, ValueError):
            raise DespachoInvalidoError(
                f'Distribuye correctamente las unidades de {detalle.nombre_producto}.'
            )
        if primera < 0 or primera > detalle.cantidad_producto:
            raise DespachoInvalidoError(
                f'La distribución de {detalle.nombre_producto} no es válida.'
            )
        segunda = detalle.cantidad_producto - primera
        if primera:
            asignaciones[1][detalle.id] = primera
        if segunda:
            asignaciones[2][detalle.id] = segunda

    if not asignaciones[1] or not asignaciones[2]:
        raise DespachoInvalidoError(
            'Cada despacho debe contener al menos una unidad de producto.'
        )
    return asignaciones


def crear_reservas_despacho(venta, detalles, datos, direccion):
    try:
        cantidad_despachos = int(datos.get('cantidad_despachos', 1))
    except (TypeError, ValueError):
        cantidad_despachos = 0
    if cantidad_despachos not in {1, 2}:
        raise DespachoInvalidoError('Solo puedes programar uno o dos despachos.')

    configuracion = ConfiguracionDespacho.objects.select_for_update().filter(pk=1).first()
    if configuracion is None:
        configuracion = ConfiguracionDespacho.cargar()
        configuracion = ConfiguracionDespacho.objects.select_for_update().get(pk=1)
    if not configuracion.despachos_activos:
        raise DespachoInvalidoError('Los despachos están temporalmente deshabilitados.')

    fechas = [_fecha_desde_valor(datos.get('fecha_despacho_1'))]
    if cantidad_despachos == 2:
        fechas.append(_fecha_desde_valor(datos.get('fecha_despacho_2')))
        if fechas[0] == fechas[1]:
            raise DespachoInvalidoError(
                'Para dos despachos debes seleccionar fechas diferentes.'
            )
    for fecha in fechas:
        _validar_fecha(fecha, configuracion)

    asignaciones = _cantidades_por_despacho(detalles, datos, cantidad_despachos)
    venta.despachos.all().delete()

    estados = {}
    for fecha in sorted(fechas):
        estados[fecha] = capacidad_fecha(
            fecha,
            configuracion=configuracion,
            bloquear=True,
        )
        if estados[fecha]['cerrada']:
            raise DespachoInvalidoError(
                f'La fecha {fecha:%d/%m/%Y} está cerrada para nuevos despachos.'
            )
        if estados[fecha]['disponibles'] <= 0:
            raise DespachoInvalidoError(
                f'La fecha {fecha:%d/%m/%Y} ya no tiene cupos disponibles.'
            )

    cargo_total = configuracion.cargo_segundo_despacho if cantidad_despachos == 2 else 0
    expira = timezone.now() + timedelta(minutes=15)
    detalles_por_id = {detalle.id: detalle for detalle in detalles}
    for indice, fecha in enumerate(fechas, start=1):
        despacho = DespachoVenta.objects.create(
            venta=venta,
            numero=indice,
            fecha_programada=fecha,
            direccion=direccion,
            estado=DespachoVenta.Estado.RESERVADO,
            cargo=cargo_total if indice == 2 else 0,
            reserva_expira_en=expira,
        )
        DetalleDespacho.objects.bulk_create([
            DetalleDespacho(
                despacho=despacho,
                detalle=detalles_por_id[detalle_id],
                cantidad=cantidad,
            )
            for detalle_id, cantidad in asignaciones[indice].items()
        ])
    return cargo_total


def liberar_reservas_despacho(venta):
    venta.despachos.filter(estado=DespachoVenta.Estado.RESERVADO).delete()
    venta.cargo_despacho = 0


def confirmar_reservas_despacho(venta):
    reservas = list(
        venta.despachos.select_for_update().filter(
            estado=DespachoVenta.Estado.RESERVADO
        ).order_by('fecha_programada')
    )
    if venta.tipo_entrega == 'despacho' and not reservas:
        raise DespachoInvalidoError('La reserva de despacho ya no está disponible.')

    configuracion = ConfiguracionDespacho.objects.select_for_update().get(pk=1)
    ahora = timezone.now()
    for reserva in reservas:
        if reserva.reserva_expira_en and reserva.reserva_expira_en <= ahora:
            estado = capacidad_fecha(
                reserva.fecha_programada,
                configuracion=configuracion,
                bloquear=True,
            )
            if estado['disponibles'] <= 0:
                raise DespachoInvalidoError(
                    f'La fecha {reserva.fecha_programada:%d/%m/%Y} agotó sus cupos.'
                )

    venta.despachos.filter(estado=DespachoVenta.Estado.RESERVADO).update(
        estado=DespachoVenta.Estado.PROGRAMADO,
        reserva_expira_en=None,
    )


def actualizar_estado_general_venta(venta):
    estados = list(venta.despachos.values_list('estado', flat=True))
    if estados and all(estado == DespachoVenta.Estado.ENTREGADO for estado in estados):
        venta.estado_entrega = 'completado'
    else:
        venta.estado_entrega = 'pendiente'
    venta.save(update_fields=['estado_entrega'])
