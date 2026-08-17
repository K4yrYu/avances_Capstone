import re
import unicodedata
from decimal import Decimal, ROUND_CEILING

from productos.models import Producto
from productos.services import calcular_recomendaciones_pintura
from .gemini import GeminiNoDisponible, interpretar_con_gemini
from .recomendacion_colores import (
    color_publico,
    detectar_contexto_pintura,
    pinturas_compatibles,
)


class AsistenteNoDisponible(Exception):
    pass


def _texto_normalizado(valor):
    texto = unicodedata.normalize('NFKD', str(valor or '').lower())
    return ''.join(caracter for caracter in texto if not unicodedata.combining(caracter))


def _normalizar_preferencias_extraidas(datos, mensaje, historial):
    """Impide que la IA invente preferencias que el cliente nunca expresó."""
    texto_usuario = ' '.join(
        [item['content'] for item in historial if item.get('role') == 'user']
        + [mensaje]
    )
    texto_usuario = _texto_normalizado(texto_usuario)

    terminacion = datos.get('terminacion') or 'cualquiera'
    alias_terminacion = {
        'mate': ('mate',),
        'satinado': ('satinado', 'satinada'),
        'semibrillo': ('semibrillo', 'semi brillo'),
        'cascara_huevo': ('cascara de huevo',),
        'lisa_mate': ('lisa mate', 'liso mate', 'lisa y mate', 'liso y mate'),
    }
    if terminacion != 'cualquiera' and not any(
        alias in texto_usuario for alias in alias_terminacion.get(terminacion, ())
    ):
        datos['terminacion'] = 'cualquiera'

    colores_reconocibles = {
        'blanco', 'negro', 'gris', 'azul', 'rojo', 'verde', 'amarillo',
        'beige', 'cafe', 'marron', 'naranjo', 'naranja', 'transparente',
        'blancos', 'negros', 'grises', 'azules', 'rojos', 'verdes', 'amarillos',
        'beiges', 'cafes', 'marrones', 'naranjos', 'naranjas', 'transparentes',
    }
    palabras_usuario = set(re.findall(r'[a-z]+', texto_usuario))
    if datos.get('color') and not (palabras_usuario & colores_reconocibles):
        datos['color'] = ''

    indicadores_presupuesto = (
        '$', 'presupuesto', 'lucas', 'luca', 'pesos', 'clp',
        'mil para', 'dispongo de', 'tengo para gastar',
    )
    presupuesto_expresado = any(
        indicador in texto_usuario for indicador in indicadores_presupuesto
    ) or bool(re.search(r'\b\d[\d.]*\s*(?:mil|lucas?)\b', texto_usuario))
    if datos.get('presupuesto') and not presupuesto_expresado:
        datos['presupuesto'] = 0
    return datos


def _producto_publico(producto):
    return {
        'id': producto.id,
        'sku': producto.sku or '',
        'nombre': producto.nombre,
        'marca': producto.marca,
        'categoria': producto.categoria,
        'precio': producto.precio,
        'stock': producto.stock,
        'presentacion': producto.presentacion,
        'color': producto.color,
        'color_hex': producto.color_hex,
        'ambiente': producto.get_ambiente_uso_display(),
        'terminacion': producto.get_terminacion_display(),
        'imagen': producto.imagen.url if producto.imagen else '',
        'url': f'/productos/{producto.id}/',
    }


def _formatear_clp(valor):
    return f'${int(valor):,}'.replace(',', '.')


def _producto_catalogo(nombre):
    return (
        Producto.objects.filter(activo=True, nombre__icontains=nombre)
        .order_by('precio', 'nombre')
        .first()
    )


def _item_proyecto(producto, cantidad, rol, detalle):
    if not producto or cantidad < 1 or producto.stock < cantidad:
        return None
    item = _producto_publico(producto)
    item.update({
        'rol': rol,
        'cantidad_requerida': cantidad,
        'subtotal': cantidad * producto.precio,
        'detalle_material': detalle,
        'carrito_cantidad': cantidad,
    })
    return item


def _resolver_repisa(datos):
    faltantes_datos = []
    if not datos.get('ancho_cm'):
        faltantes_datos.append('el ancho de la repisa en centímetros')
    if not datos.get('fondo_cm'):
        faltantes_datos.append('el fondo o profundidad en centímetros')
    if not datos.get('tipo_muro'):
        faltantes_datos.append('si el muro es de hormigón, ladrillo, yeso-cartón o madera')
    if faltantes_datos:
        detalle = (
            faltantes_datos[0] if len(faltantes_datos) == 1
            else ', '.join(faltantes_datos[:-1]) + ' y ' + faltantes_datos[-1]
        )
        return {
            'tipo': 'aclaracion',
            'mensaje': (
                f'Para preparar opciones reales para la repisa necesito {detalle}. '
                'También puedes indicar tu presupuesto máximo.'
            ),
            'productos': [],
            'sugerencias': [
                '80 cm de ancho, 25 cm de fondo, muro de hormigón y $30.000',
                '120 cm de ancho, 30 cm de fondo y muro de yeso-cartón',
            ],
        }

    ancho_cm = int(datos['ancho_cm'])
    fondo_cm = int(datos['fondo_cm'])
    cantidad = max(1, int(datos.get('cantidad') or 1))
    if ancho_cm > 300 or fondo_cm > 80 or cantidad > 20:
        return {
            'tipo': 'orientacion',
            'mensaje': (
                'Esas dimensiones requieren una revisión de carga y soporte fuera del '
                'alcance de una repisa básica. Consulta a un carpintero o instalador.'
            ),
            'productos': [],
            'sugerencias': ['Planificar una repisa más pequeña'],
        }

    if ancho_cm > 120 or fondo_cm > 30:
        return {
            'tipo': 'sin_resultados',
            'mensaje': (
                'El tablero de repisa disponible mide 120 × 30 cm y no alcanza para esas '
                'dimensiones sin unir piezas. Para evitar una recomendación insegura, prueba '
                'una medida máxima de 120 × 30 cm o solicita un tablero de mayor formato.'
            ),
            'productos': [],
            'sugerencias': ['120 cm de ancho y 30 cm de fondo', '80 cm de ancho y 25 cm de fondo'],
        }

    tablero = _producto_catalogo('Tablero pino finger joint')
    escuadras = _producto_catalogo('Escuadras metálicas reforzadas')
    tornillos_madera = _producto_catalogo('Tornillos para madera 4 x 40')
    lijas = _producto_catalogo('Lijas para madera')
    barniz = _producto_catalogo('Barniz al agua para madera')
    fijacion_muro = {
        'hormigon': _producto_catalogo('Kit fijación para hormigón'),
        'ladrillo': _producto_catalogo('Kit fijación para hormigón'),
        'yeso_carton': _producto_catalogo('Kit anclajes yeso-cartón'),
        'madera': tornillos_madera,
    }[datos['tipo_muro']]

    paquetes_fijacion = int(
        (Decimal(4 * cantidad) / Decimal('10')).to_integral_value(rounding=ROUND_CEILING)
    )
    paquetes_tornillos = int(
        (Decimal(4 * cantidad) / Decimal('50')).to_integral_value(rounding=ROUND_CEILING)
    )
    if datos['tipo_muro'] == 'madera':
        paquetes_tornillos = int(
            (Decimal(8 * cantidad) / Decimal('50')).to_integral_value(rounding=ROUND_CEILING)
        )
    paquetes_lija = int(
        (Decimal(cantidad) / Decimal('3')).to_integral_value(rounding=ROUND_CEILING)
    )

    definiciones = [
        (tablero, cantidad, 'Superficie de la repisa', f'{cantidad} tablero(s), con corte a {ancho_cm} × {fondo_cm} cm'),
        (escuadras, cantidad, 'Soporte mural', f'{2 * cantidad} escuadra(s), dos por repisa'),
        (
            fijacion_muro,
            paquetes_tornillos if datos['tipo_muro'] == 'madera' else paquetes_fijacion,
            'Fijación al muro',
            f'Fijación compatible con muro de {datos["tipo_muro"].replace("_", "-")}',
        ),
        (lijas, paquetes_lija, 'Preparación de la madera', 'Lijado progresivo antes de la terminación'),
    ]
    if datos['tipo_muro'] != 'madera':
        definiciones.insert(3, (
            tornillos_madera,
            paquetes_tornillos,
            'Unión tablero y escuadras',
            f'Tornillos para sujetar {cantidad} tablero(s) a sus escuadras',
        ))

    nombres_faltantes = []
    productos_kit = []
    for producto, unidades, rol, detalle in definiciones:
        item = _item_proyecto(producto, unidades, rol, detalle)
        if item:
            productos_kit.append(item)
        elif not producto:
            nombres_faltantes.append(rol)
        else:
            nombres_faltantes.append(f'{rol} (stock insuficiente)')

    if nombres_faltantes:
        return {
            'tipo': 'plan_proyecto',
            'mensaje': (
                f'Encontré parte de los materiales para {cantidad} repisa(s) de '
                f'{ancho_cm} × {fondo_cm} cm, pero todavía falta: {"; ".join(nombres_faltantes)}. '
                'No cierro el presupuesto como completo hasta que todos los materiales tengan stock.'
            ),
            'productos': productos_kit,
            'faltantes_catalogo': nombres_faltantes,
            'presupuesto': int(datos.get('presupuesto') or 0),
            'sugerencias': ['Ver productos disponibles', 'Probar otra medida'],
        }

    subtotal_basico = sum(item['subtotal'] for item in productos_kit)
    item_barniz = _item_proyecto(
        barniz,
        1,
        'Terminación opcional',
        'Barniz satinado para proteger la madera en interior',
    )
    total_terminado = subtotal_basico + (item_barniz['subtotal'] if item_barniz else 0)
    if item_barniz:
        productos_kit.append(item_barniz)

    presupuesto = int(datos.get('presupuesto') or 0)
    if presupuesto:
        if item_barniz and presupuesto >= total_terminado:
            saldo = presupuesto - total_terminado
            mensaje_presupuesto = (
                f'Tu presupuesto alcanza para el kit con terminación, cuyo total es '
                f'{_formatear_clp(total_terminado)}, y quedan {_formatear_clp(saldo)}.'
            )
        elif presupuesto >= subtotal_basico:
            saldo = presupuesto - subtotal_basico
            extra = total_terminado - presupuesto if item_barniz else 0
            mensaje_presupuesto = (
                f'Tu presupuesto alcanza para el kit básico de {_formatear_clp(subtotal_basico)} '
                f'y quedan {_formatear_clp(saldo)}.'
            )
            if item_barniz and extra > 0:
                mensaje_presupuesto += f' Para sumar el barniz faltan {_formatear_clp(extra)}.'
        else:
            diferencia = subtotal_basico - presupuesto
            mensaje_presupuesto = (
                f'Tu presupuesto de {_formatear_clp(presupuesto)} no alcanza para el kit '
                f'básico de {_formatear_clp(subtotal_basico)}: faltan {_formatear_clp(diferencia)}.'
            )
    else:
        mensaje_presupuesto = (
            f'El kit básico cuesta {_formatear_clp(subtotal_basico)}.'
        )
        if item_barniz:
            mensaje_presupuesto += f' Con el barniz opcional cuesta {_formatear_clp(total_terminado)}.'

    return {
        'tipo': 'plan_proyecto',
        'mensaje': (
            f'Preparé los materiales para {cantidad} repisa(s) de {ancho_cm} × {fondo_cm} cm '
            f'en muro de {datos["tipo_muro"].replace("_", "-")}. {mensaje_presupuesto} '
            'El barniz es opcional. Antes de instalar, verifica la carga admisible del muro, '
            'la ubicación de instalaciones ocultas y la fijación indicada por el fabricante.'
        ),
        'productos': productos_kit,
        'faltantes_catalogo': [],
        'presupuesto': presupuesto,
        'subtotal_basico': subtotal_basico,
        'total_con_terminacion': total_terminado,
        'sugerencias': ['Incluir también herramientas', 'Cambiar las medidas de la repisa'],
    }


def _resolver_proyecto(datos):
    proyecto = _texto_normalizado(datos.get('proyecto'))
    if 'repisa' in proyecto or 'estante' in proyecto:
        return _resolver_repisa(datos)
    orientacion = str(datos.get('respuesta') or '').strip()
    mensaje = (
        f'{orientacion} ' if orientacion else ''
    ) + (
        'Todavía no puedo cerrar una cotización completa y verificable para ese proyecto '
        'con el catálogo actual. Sí puedo planificar una repisa; para otros proyectos te '
        'indicaré materiales generales y cuáles faltan antes de calcular un presupuesto.'
    )
    return {
        'tipo': 'aclaracion',
        'mensaje': mensaje,
        'productos': [],
        'sugerencias': ['Quiero construir una repisa'],
    }


def _buscar_productos(consulta):
    palabras_omitidas = {
        'para', 'con', 'una', 'uno', 'unos', 'unas', 'por', 'del', 'las', 'los',
        'que', 'quiero', 'necesito', 'busco', 'producto', 'productos',
    }
    palabras = [
        palabra for palabra in re.findall(r'[\wáéíóúñü-]+', _texto_normalizado(consulta))
        if len(palabra) >= 3 and palabra not in palabras_omitidas
    ][:8]
    if not palabras:
        return []
    consulta_normalizada = _texto_normalizado(consulta)
    def contiene(texto, palabra):
        return bool(re.search(rf'\b{re.escape(palabra)}\w*', texto))

    resultados = []
    for producto in Producto.objects.filter(activo=True):
        nombre = _texto_normalizado(producto.nombre)
        identificacion = _texto_normalizado(
            ' '.join([producto.sku or '', producto.marca, producto.categoria, producto.color])
        )
        detalle = _texto_normalizado(
            ' '.join([
                producto.descripcion,
                producto.uso_recomendado,
                str(producto.especificaciones or {}),
            ])
        )
        puntaje = 8 if consulta_normalizada in nombre else 0
        for palabra in palabras:
            if contiene(nombre, palabra):
                puntaje += 5
            elif contiene(identificacion, palabra):
                puntaje += 3
            elif contiene(detalle, palabra):
                puntaje += 1
        coincidencias = sum(
            contiene(f'{nombre} {identificacion} {detalle}', palabra) for palabra in palabras
        )
        if puntaje and coincidencias:
            resultados.append((coincidencias, puntaje, producto))
    resultados.sort(key=lambda item: (
        -item[0], -item[1], item[2].precio, item[2].nombre.casefold(),
    ))
    return [item[2] for item in resultados[:6]]


def _resolver_recomendacion_color(datos):
    contexto = detectar_contexto_pintura(datos)
    if not contexto:
        return {
            'tipo': 'aclaracion',
            'mensaje': (
                '¿Dónde usarás la pintura? Indica si es un espacio interior, una superficie '
                'exterior o una piscina para recomendar solo colores compatibles.'
            ),
            'productos': [],
            'sugerencias': [
                'Quiero colores para un dormitorio interior',
                'Recomiéndame colores para una fachada exterior',
                'Quiero pintar una piscina',
            ],
        }

    color_solicitado = str(datos.get('color') or '').strip()
    productos = pinturas_compatibles(contexto, color_solicitado)
    if not productos:
        detalle_color = f' en color {color_solicitado}' if color_solicitado else ''
        return {
            'tipo': 'sin_resultados',
            'mensaje': (
                f'No hay pinturas verificadas con stock para {contexto}{detalle_color}. '
                'No recomendaré una pintura de otro ambiente porque podría no ser adecuada.'
            ),
            'productos': [],
            'sugerencias': ['Ver otros colores compatibles', 'Revisar todas las pinturas'],
        }

    recomendaciones = []
    for producto in productos:
        item = _producto_publico(producto)
        item.update(color_publico(producto))
        item['rol'] = f'Color compatible con {contexto}'
        item['carrito_cantidad'] = 1
        recomendaciones.append(item)

    colores = ', '.join(dict.fromkeys(producto.color for producto in productos))
    explicacion = {
        'interior': (
            'Para interior prioricé pinturas indicadas para espacios interiores; los tonos '
            'claros ayudan a reflejar más luz, mientras los intensos funcionan mejor como acento.'
        ),
        'exterior': (
            'Para exterior prioricé productos formulados para exposición exterior. El color '
            'debe elegirse junto con la preparación y protección que exige la superficie.'
        ),
        'piscina': (
            'Para piscina solo recomiendo pintura técnicamente compatible con piscina o estanque; '
            'una pintura común de muro no corresponde para inmersión.'
        ),
    }[contexto]
    return {
        'tipo': 'recomendacion_color',
        'contexto_pintura': contexto,
        'mensaje': (
            f'{explicacion} Colores disponibles encontrados: {colores}. '
            'Puedes probarlos en el visualizador con una fotografía.'
        ),
        'productos': recomendaciones,
        'sugerencias': [
            'Quiero calcular cuánta pintura necesito',
            'Probar un color en mi fotografía',
            'Mostrar otro ambiente',
        ],
    }


def _resolver_calculo(datos):
    faltantes = []
    if not datos.get('superficie'):
        faltantes.append('los metros cuadrados que pintarás')
    if not datos.get('ambiente'):
        faltantes.append('si es interior, exterior o un uso especial')
    if not datos.get('tipo_superficie'):
        faltantes.append('el material de la superficie')
    if not datos.get('estado_superficie'):
        faltantes.append('el estado actual de la superficie')
    if faltantes:
        if len(faltantes) == 1:
            detalle = faltantes[0]
        else:
            detalle = ', '.join(faltantes[:-1]) + ' y ' + faltantes[-1]
        return {
            'tipo': 'aclaracion',
            'mensaje': f'Para calcularlo con precisión necesito saber {detalle}.',
            'productos': [],
            'sugerencias': [
                'Es interior, muro de hormigón y está nuevo',
                'Es exterior, muro de ladrillo y está deteriorado',
            ],
        }

    capas = datos.get('capas') or None
    desperdicio = datos.get('desperdicio', -1)
    desperdicio = None if desperdicio is None or desperdicio < 0 else desperdicio
    recomendaciones = calcular_recomendaciones_pintura(
        superficie=datos['superficie'],
        ambiente=datos['ambiente'],
        tipo_superficie=datos['tipo_superficie'],
        estado_superficie=datos['estado_superficie'],
        terminacion=datos.get('terminacion') or 'cualquiera',
        color=datos.get('color', ''),
        capas=capas,
        desperdicio=desperdicio,
    )
    if not recomendaciones:
        return {
            'tipo': 'sin_resultados',
            'mensaje': (
                'No encontré una pintura verificada que coincida con todos esos datos. '
                'Puedes cambiar el color o la terminación, o revisar el catálogo.'
            ),
            'productos': [],
            'sugerencias': ['Muéstrame cualquier terminación', 'Muéstrame todas las pinturas'],
        }

    presupuesto = int(datos.get('presupuesto') or 0)
    mensaje_presupuesto = ''
    if presupuesto:
        alcanzables = [
            calculo for calculo in recomendaciones
            if calculo['stock_suficiente'] and calculo['presupuesto_total'] <= presupuesto
        ]
        if alcanzables:
            recomendaciones = alcanzables[:3]
            mensaje_presupuesto = (
                f' Encontré {len(recomendaciones)} alternativa(s) dentro de tu '
                f'presupuesto de {_formatear_clp(presupuesto)}.'
            )
        else:
            disponibles = [calculo for calculo in recomendaciones if calculo['stock_suficiente']]
            mejor_disponible = (disponibles or recomendaciones)[0]
            diferencia = mejor_disponible['presupuesto_total'] - presupuesto
            recomendaciones = [mejor_disponible]
            mensaje_presupuesto = (
                f' Tu presupuesto de {_formatear_clp(presupuesto)} no alcanza para '
                f'esta alternativa; faltan {_formatear_clp(max(diferencia, 0))}.'
            )
    else:
        recomendaciones = recomendaciones[:3]

    productos = []
    for calculo in recomendaciones:
        productos.append({
            'id': calculo['producto_id'],
            'nombre': calculo['nombre'],
            'marca': calculo['marca'],
            'precio': calculo['precio_unitario'],
            'stock': calculo['stock_disponible'],
            'imagen': calculo['imagen'],
            'url': f"/productos/{calculo['producto_id']}/",
            'presentacion': calculo['presentacion'],
            'color': calculo['color'],
            'color_hex': calculo['color_hex'],
            'cantidad_envases': calculo['cantidad_envases'],
            'litros_necesarios': calculo['litros_necesarios'],
            'presupuesto_total': calculo['presupuesto_total'],
            'stock_suficiente': calculo['stock_suficiente'],
            'terminacion': calculo['terminacion_display'],
            'preparacion': calculo['preparacion_proyecto_display'],
            'advertencia': calculo['advertencia_preparacion'],
            'calculo_carrito': {
                'producto': calculo['producto_id'],
                'superficie': datos['superficie'],
                'ambiente': datos['ambiente'],
                'tipo_superficie': datos['tipo_superficie'],
                'estado_superficie': datos['estado_superficie'],
                'terminacion': datos.get('terminacion') or 'cualquiera',
                'capas': capas,
                'desperdicio': desperdicio,
            },
        })
    mejor = productos[0]
    return {
        'tipo': 'calculo_pintura',
        'mensaje': (
            f'Para {datos["superficie"]} m² necesitas aproximadamente '
            f'{mejor["litros_necesarios"]} litros. La primera alternativa requiere '
            f'{mejor["cantidad_envases"]} envase(s) y tiene un presupuesto de '
            f'{_formatear_clp(mejor["presupuesto_total"])} CLP.'
            f'{mensaje_presupuesto}'
        ),
        'productos': productos,
        'sugerencias': ['Buscar otra terminación', 'Ver pinturas de otro color'],
    }


def resolver_interpretacion(datos):
    intencion = datos.get('intencion')
    if intencion == 'recomendar_color':
        return _resolver_recomendacion_color(datos)
    if intencion == 'calcular_pintura':
        return _resolver_calculo(datos)
    if intencion == 'planificar_proyecto':
        return _resolver_proyecto(datos)
    if intencion == 'buscar_producto':
        consulta = str(datos.get('consulta_producto') or '').strip()
        productos = _buscar_productos(consulta)
        if not consulta:
            return {
                'tipo': 'aclaracion',
                'mensaje': '¿Qué producto, material, marca o categoría necesitas buscar?',
                'productos': [],
                'sugerencias': ['Busco un taladro', 'Necesito pintura blanca', 'Muéstrame maderas'],
            }
        if not productos:
            return {
                'tipo': 'sin_resultados',
                'mensaje': f'No encontré productos activos relacionados con “{consulta}”.',
                'productos': [],
                'sugerencias': ['Ver pinturas', 'Buscar herramientas', 'Buscar materiales'],
            }
        presupuesto = int(datos.get('presupuesto') or 0)
        if presupuesto:
            alcanzables = [producto for producto in productos if producto.precio <= presupuesto]
            if alcanzables:
                productos = alcanzables
                mensaje = (
                    f'Encontré {len(productos)} opción(es) dentro de tu presupuesto de '
                    f'{_formatear_clp(presupuesto)} para “{consulta}”.'
                )
            else:
                economico = productos[0]
                diferencia = economico.precio - presupuesto
                productos = [economico]
                mensaje = (
                    f'Tu presupuesto de {_formatear_clp(presupuesto)} no alcanza para '
                    f'“{consulta}”. La opción más económica cuesta '
                    f'{_formatear_clp(economico.precio)} y faltan '
                    f'{_formatear_clp(diferencia)}.'
                )
        else:
            mensaje = f'Encontré {len(productos)} producto(s) relacionados con “{consulta}”.'
        productos_publicos = []
        for producto in productos:
            producto_publico = _producto_publico(producto)
            producto_publico['carrito_cantidad'] = 1
            productos_publicos.append(producto_publico)
        return {
            'tipo': 'productos',
            'mensaje': mensaje,
            'productos': productos_publicos,
            'sugerencias': ['¿Cuál es el más económico?', 'Quiero calcular pintura'],
        }
    return {
        'tipo': 'orientacion',
        'mensaje': str(datos.get('respuesta') or 'Cuéntame un poco más sobre tu proyecto.'),
        'productos': [],
        'sugerencias': ['Necesito calcular pintura', 'Busco una herramienta'],
    }


def procesar_consulta(mensaje, historial):
    try:
        interpretacion = interpretar_con_gemini(mensaje, historial)
    except GeminiNoDisponible as exc:
        raise AsistenteNoDisponible(str(exc)) from exc
    interpretacion = _normalizar_preferencias_extraidas(
        interpretacion,
        mensaje,
        historial,
    )
    return resolver_interpretacion(interpretacion)


def procesar_configuracion_foto(mensaje, contexto, historial, producto=None):
    """Completa un proyecto de pintura usando el contexto seguro de una foto."""
    try:
        interpretacion = interpretar_con_gemini(mensaje, historial)
    except GeminiNoDisponible as exc:
        raise AsistenteNoDisponible(str(exc)) from exc
    interpretacion = _normalizar_preferencias_extraidas(
        interpretacion,
        mensaje,
        historial,
    )
    if contexto == 'piscina':
        interpretacion['ambiente'] = 'especial'
        interpretacion['tipo_superficie'] = 'piscina_estanque'
    elif contexto in {'interior', 'exterior'}:
        interpretacion['ambiente'] = contexto
        if interpretacion.get('tipo_superficie') == 'piscina_estanque':
            interpretacion['tipo_superficie'] = ''
    if producto:
        if not interpretacion.get('color'):
            interpretacion['color'] = producto.color
        if interpretacion.get('terminacion') in {'', 'cualquiera'}:
            interpretacion['terminacion'] = producto.terminacion

    texto_actual = _texto_normalizado(mensaje)
    indicadores_calculo = (
        'cuanto', 'cuanta', 'litro', 'litros', 'envase', 'envases',
        'metro cuadrado', 'metros cuadrados', 'm2', 'presupuesto',
        'costo', 'costos', 'precio', 'comprar', 'cantidad',
    )
    solicita_calculo = (
        interpretacion.get('intencion') == 'calcular_pintura'
        and any(indicador in texto_actual for indicador in indicadores_calculo)
    )
    if not solicita_calculo:
        interpretacion['intencion'] = 'recomendar_color'
        if not interpretacion.get('ambiente'):
            return {
                'tipo': 'aclaracion_foto',
                'mensaje': (
                    '¡Claro! Antes de buscar el color, cuéntame si la superficie es '
                    'interior, exterior o una piscina.'
                ),
                'productos': [],
                'sugerencias': ['Es una fachada exterior', 'Es una habitación interior'],
            }
        if not interpretacion.get('color'):
            return {
                'tipo': 'aclaracion_foto',
                'mensaje': (
                    '¡Perfecto! Dime qué color o tono quieres probar. Por ejemplo: '
                    '“quiero verla en azul claro” o “prefiero un rojo colonial”.'
                ),
                'productos': [],
                'sugerencias': ['Quiero verla en azul claro', 'Muéstrame tonos rojos'],
            }
        resultado = _resolver_recomendacion_color(interpretacion)
        if resultado.get('productos'):
            resultado['mensaje'] = (
                f'¡Buena elección! Encontré {len(resultado["productos"])} opción(es) '
                'compatibles. Aparecieron arriba en Colores recomendados: elige una y '
                'haz clic sobre la parte de la foto que quieras pintar. Si luego quieres '
                'saber cuánto comprar, pregúntame por cantidades o costos.'
            )
        else:
            resultado['mensaje'] = (
                f'Todavía no encontré una pintura {interpretacion.get("color")} compatible '
                'con esta superficie y con stock. Prefiero no mostrarte una pintura que no '
                'corresponda. Puedes pedirme otro tono y revisaré las opciones disponibles.'
            )
        return resultado

    interpretacion['intencion'] = 'calcular_pintura'
    faltantes = []
    if not interpretacion.get('color'):
        faltantes.append('el color o estilo que quieres probar')
    if not interpretacion.get('ambiente'):
        faltantes.append('si el proyecto es interior, exterior o piscina')
    if not interpretacion.get('superficie'):
        faltantes.append('los metros cuadrados que pintarás')
    if not interpretacion.get('tipo_superficie'):
        faltantes.append('el material de la superficie')
    if not interpretacion.get('estado_superficie'):
        faltantes.append('su estado actual')
    if faltantes:
        detalle = faltantes[0] if len(faltantes) == 1 else ', '.join(faltantes[:-1]) + ' y ' + faltantes[-1]
        if producto:
            referencia_eleccion = (
                f'Basado en tu elección de arriba, {producto.nombre} en color '
                f'{producto.color}, '
            )
        elif interpretacion.get('color'):
            referencia_eleccion = (
                f'Basado en el color {interpretacion["color"]} que elegiste arriba, '
            )
        else:
            referencia_eleccion = ''
        return {
            'tipo': 'aclaracion_foto',
            'mensaje': (
                f'{referencia_eleccion}¡Con gusto te ayudo a calcularlo! '
                'Para recomendarte la cantidad correcta, '
                f'por favor indícame {detalle}. Con esos datos podré mostrarte opciones '
                'reales, cantidades y costos para tu proyecto.'
            ),
            'productos': [],
            'sugerencias': [
                'Quiero rojo, son 45 m², hormigón y está en buen estado',
                'Quiero mantener el color seleccionado y pintar 30 m²',
            ],
        }
    return resolver_interpretacion(interpretacion)
