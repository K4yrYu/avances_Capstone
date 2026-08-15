from decimal import Decimal, ROUND_CEILING

from productos.models import Producto


def _redondear(valor, decimales='0.01'):
    return valor.quantize(Decimal(decimales))


def _ambiente_compatible(producto, ambiente):
    compatibilidad = {
        'interior': {'interior', 'interior_exterior'},
        'exterior': {'exterior', 'interior_exterior'},
        'especial': {'especial'},
    }
    return not ambiente or producto.ambiente_uso in compatibilidad.get(ambiente, set())


def _preparacion_para_proyecto(producto, estado_superficie):
    """Adapta la preparacion de la ficha al estado real indicado por el cliente."""
    preparaciones_por_estado = {
        'nueva': {'limpieza', 'sellador', 'imprimante', 'impermeabilizacion'},
        'pintada_buen_estado': {'limpieza', 'lijado'},
        'deteriorada': {'limpieza', 'lijado', 'reparacion', 'sellador', 'imprimante'},
        'humedad': {
            'limpieza', 'lijado', 'reparacion', 'sellador',
            'imprimante', 'impermeabilizacion',
        },
    }
    permitidas = preparaciones_por_estado.get(
        estado_superficie,
        set(producto.preparaciones_recomendadas),
    )
    preparaciones = [
        opcion for opcion in producto.preparaciones_recomendadas
        if opcion in permitidas
    ]
    etiquetas = dict(Producto.PREPARACION_CHOICES)
    advertencia = ''
    if estado_superficie == 'humedad':
        advertencia = (
            'Corrige primero el origen de la humedad y deja secar completamente '
            'la superficie antes de preparar y pintar.'
        )
    return {
        'codigos': preparaciones,
        'etiquetas': [etiquetas[opcion] for opcion in preparaciones],
        'advertencia': advertencia,
    }


def calcular_producto_pintura(
    producto,
    superficie,
    capas=None,
    desperdicio=None,
    ambiente=None,
    tipo_superficie=None,
    estado_superficie=None,
    terminacion=None,
):
    if not (
        producto.activo
        and producto.tipo_calculo == 'pintura'
        and producto.informacion_tecnica_verificada
        and producto.contenido
        and producto.rendimiento
        and producto.capas_recomendadas
        and producto.ambiente_uso != 'no_aplica'
        and producto.tipo_pintura != 'no_aplica'
        and producto.terminacion != 'no_aplica'
        and producto.propiedades_pintura
        and producto.preparaciones_recomendadas
        and producto.repintado_min_horas is not None
        and producto.unidad_contenido == 'l'
        and producto.unidad_rendimiento == 'm2_l'
        and _ambiente_compatible(producto, ambiente)
        and (not tipo_superficie or tipo_superficie in producto.superficies_compatibles)
        and (
            not terminacion
            or terminacion == 'cualquiera'
            or producto.terminacion == terminacion
        )
    ):
        return None

    superficie = Decimal(superficie)
    capas_aplicadas = int(capas or producto.capas_recomendadas)
    desperdicio_aplicado = Decimal(
        desperdicio if desperdicio is not None else producto.porcentaje_desperdicio
    )
    litros_base_exacto = superficie * Decimal(capas_aplicadas) / producto.rendimiento
    litros_con_margen = litros_base_exacto * (
        Decimal('1') + desperdicio_aplicado / Decimal('100')
    )
    litros_necesarios = litros_con_margen.to_integral_value(rounding=ROUND_CEILING)
    cantidad_envases = int(
        (litros_necesarios / producto.contenido).to_integral_value(rounding=ROUND_CEILING)
    )
    litros_comprados = producto.contenido * cantidad_envases
    sobrante_estimado = max(
        litros_comprados - litros_necesarios, Decimal('0')
    ).to_integral_value(rounding=ROUND_CEILING)
    stock_suficiente = producto.stock >= cantidad_envases
    preparacion_proyecto = _preparacion_para_proyecto(producto, estado_superficie)
    estados_superficie = dict(Producto.ESTADO_SUPERFICIE_CHOICES)

    return {
        'producto_id': producto.id,
        'nombre': producto.nombre,
        'marca': producto.marca,
        'modelo': producto.modelo,
        'color': producto.color,
        'color_hex': producto.color_hex,
        'ambiente_uso': producto.ambiente_uso,
        'ambiente_uso_display': producto.get_ambiente_uso_display(),
        'superficies_compatibles': producto.superficies_compatibles,
        'superficies_compatibles_display': producto.superficies_compatibles_display,
        'tipo_pintura': producto.tipo_pintura,
        'tipo_pintura_display': producto.get_tipo_pintura_display(),
        'terminacion': producto.terminacion,
        'terminacion_display': producto.get_terminacion_display(),
        'propiedades_pintura': producto.propiedades_pintura,
        'propiedades_pintura_display': producto.propiedades_pintura_display,
        'preparaciones_recomendadas': producto.preparaciones_recomendadas,
        'preparaciones_recomendadas_display': producto.preparaciones_recomendadas_display,
        'estado_superficie': estado_superficie or '',
        'estado_superficie_display': estados_superficie.get(estado_superficie, ''),
        'preparacion_proyecto': preparacion_proyecto['codigos'],
        'preparacion_proyecto_display': preparacion_proyecto['etiquetas'],
        'advertencia_preparacion': preparacion_proyecto['advertencia'],
        'secado_tacto_horas': producto.secado_tacto_horas,
        'repintado_min_horas': producto.repintado_min_horas,
        'repintado_max_horas': producto.repintado_max_horas,
        'tiempo_repintado_legible': producto.tiempo_repintado_legible,
        'imagen': producto.imagen.url if producto.imagen else '',
        'presentacion': producto.presentacion,
        'contenido_litros': _redondear(producto.contenido, '0.001'),
        'rendimiento_m2_litro': _redondear(producto.rendimiento, '0.001'),
        'capas': capas_aplicadas,
        'desperdicio_porcentaje': _redondear(desperdicio_aplicado),
        'litros_base': int(litros_base_exacto.to_integral_value(rounding=ROUND_CEILING)),
        'litros_necesarios': int(litros_necesarios),
        'cantidad_envases': cantidad_envases,
        'litros_comprados': _redondear(litros_comprados),
        'sobrante_estimado': int(sobrante_estimado),
        'precio_unitario': producto.precio,
        'presupuesto_total': producto.precio * cantidad_envases,
        'stock_disponible': producto.stock,
        'stock_suficiente': stock_suficiente,
        'envases_faltantes': max(cantidad_envases - producto.stock, 0),
    }


def calcular_recomendaciones_pintura(
    superficie,
    capas=None,
    desperdicio=None,
    color='',
    ambiente=None,
    tipo_superficie=None,
    estado_superficie=None,
    terminacion=None,
):
    """Calcula alternativas reales usando solo fichas tecnicas verificadas."""
    superficie = Decimal(superficie)
    productos = Producto.objects.filter(
        activo=True,
        tipo_calculo='pintura',
        informacion_tecnica_verificada=True,
        contenido__gt=0,
        rendimiento__gt=0,
        capas_recomendadas__isnull=False,
        unidad_contenido='l',
        unidad_rendimiento='m2_l',
    ).exclude(
        ambiente_uso='no_aplica',
    ).exclude(
        superficies_compatibles=[],
    ).exclude(
        tipo_pintura='no_aplica',
    ).exclude(
        terminacion='no_aplica',
    ).exclude(
        propiedades_pintura=[],
    ).exclude(
        preparaciones_recomendadas=[],
    ).exclude(repintado_min_horas__isnull=True)
    if color:
        productos = productos.filter(color__iexact=color.strip())

    recomendaciones = []
    for producto in productos.order_by('precio', 'nombre'):
        calculo = calcular_producto_pintura(
            producto=producto,
            superficie=superficie,
            capas=capas,
            desperdicio=desperdicio,
            ambiente=ambiente,
            tipo_superficie=tipo_superficie,
            estado_superficie=estado_superficie,
            terminacion=terminacion,
        )
        if calculo is not None:
            recomendaciones.append(calculo)

    recomendaciones.sort(key=lambda item: (
        not item['stock_suficiente'],
        item['presupuesto_total'],
        item['nombre'].casefold(),
    ))
    return recomendaciones
