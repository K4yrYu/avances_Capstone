import re
import unicodedata
from decimal import Decimal, ROUND_CEILING

from maestros.chile import COMUNAS_CHOICES
from maestros.services import buscar_maestros
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


ESPECIALIDADES_MAESTRO = {
    'Carpintería': (
        'carpintero', 'carpintera', 'carpinteros', 'carpinteras', 'carpinteria',
        'repisa', 'estante', 'mueble de madera',
    ),
    'Pintura': (
        'pintor', 'pintora', 'pintores', 'pintoras', 'pintura', 'pintar', 'fachada',
    ),
    'Gasfitería': (
        'gasfiter', 'gasfiteres', 'gasfiteria', 'fuga', 'filtracion',
        'llave', 'lavaplatos', 'sanitario',
    ),
    'Electricidad': (
        'electricista', 'electricistas', 'electricidad', 'enchufe',
        'interruptor', 'instalacion electrica',
    ),
    'Cerámica y revestimientos': ('ceramista', 'ceramistas', 'ceramica', 'revestimiento'),
    'Yesería y tabiquería': (
        'yesero', 'yeseros', 'yeseria', 'tabiquero', 'tabiqueros',
        'tabiqueria', 'tabique', 'yeso-carton', 'yeso carton',
    ),
    'Techumbre': ('techumbrista', 'techumbristas', 'techumbre', 'techo'),
    'Jardinería': (
        'jardinero', 'jardinera', 'jardineros', 'jardineras', 'jardineria', 'jardin',
    ),
    'Albañilería': ('albanil', 'albaniles', 'albanileria', 'muro'),
}

ACEPTACIONES_MAESTRO = (
    'si', 'si por favor', 'dale', 'dame uno', 'prefiero un maestro',
    'prefiero una maestra', 'que lo haga alguien', 'buscar uno', 'buscar una',
    'buscar maestro', 'buscar maestra', 'buscar profesional',
)

TODAS_LAS_COMUNAS = '__todas__'


def _texto_normalizado(valor):
    texto = unicodedata.normalize('NFKD', str(valor or '').lower())
    return ''.join(caracter for caracter in texto if not unicodedata.combining(caracter))


def _especialidad_desde_texto(texto):
    normalizado = _texto_normalizado(texto)
    for especialidad, alias in ESPECIALIDADES_MAESTRO.items():
        if any(re.search(rf'\b{re.escape(item)}\b', normalizado) for item in alias):
            return especialidad
    return ''


def _comuna_desde_texto(texto):
    normalizado = f' {_texto_normalizado(texto)} '
    coincidencias = []
    for comuna, _ in COMUNAS_CHOICES:
        clave = _texto_normalizado(comuna)
        if re.search(rf'(?<!\w){re.escape(clave)}(?!\w)', normalizado):
            coincidencias.append((len(clave), comuna))
    return max(coincidencias, default=(0, ''))[1]


def _es_solicitud_directa_maestro(mensaje):
    texto = _texto_normalizado(mensaje)
    if any(frase in texto for frase in (
        'quiero hacer', 'como hacer', 'como instalo', 'como instalar',
        'como arreglo', 'quiero pintar',
    )):
        return False
    referencias_profesionales = (
        'maestro', 'maestra', 'profesional', 'carpintero', 'carpintera',
        'pintor', 'pintora', 'gasfiter', 'electricista', 'ceramista',
        'albanil', 'jardinero', 'jardinera',
    )
    solicitud_persona = any(indicador in texto for indicador in (
        'necesito alguien', 'busco alguien', 'que lo haga alguien',
    ))
    accion_con_profesional = any(indicador in texto for indicador in (
        'necesito un ', 'necesito una ', 'busco un ', 'busco una ',
        'quiero contratar', 'buscar maestro', 'buscar maestra',
        'buscar profesional', 'prefiero un maestro', 'prefiero una maestra',
    )) and any(referencia in texto for referencia in referencias_profesionales)
    return solicitud_persona or accion_con_profesional


def _pide_todas_las_comunas(mensaje):
    texto = ' '.join(
        re.sub(r'[^a-z0-9 ]+', ' ', _texto_normalizado(mensaje)).split()
    )
    respuestas_breves = {
        'cualquiera', 'de cualquiera', 'todas', 'todos',
        'muestrame todos', 'mostrar todos', 'ver todos',
    }
    return texto in respuestas_breves or any(frase in texto for frase in (
        'cualquier comuna', 'todas las comunas', 'sin importar la comuna',
        'no importa la comuna', 'de cualquier parte', 'sin filtrar por comuna',
    ))


def _pide_otra_comuna(mensaje):
    texto = _texto_normalizado(mensaje)
    return any(frase in texto for frase in (
        'otra comuna', 'cambiar comuna', 'comuna especifica',
        'comuna en particular',
    ))


def _pide_listado_especialidad(mensaje):
    texto = _texto_normalizado(mensaje)
    if not _especialidad_desde_texto(texto):
        return False
    return any(frase in texto for frase in (
        'todos los maestros', 'todas las maestras', 'que maestros',
        'cuales maestros', 'maestros disponibles', 'profesionales disponibles',
        'ver maestros', 'mostrar maestros',
    ))


def _contexto_maestro(historial):
    recientes = historial[-6:]
    especialidad = next(
        (
            encontrada
            for item in reversed(recientes)
            if (encontrada := _especialidad_desde_texto(item.get('content')))
        ),
        '',
    )
    comuna = next(
        (
            encontrada
            for item in reversed(recientes)
            if (encontrada := _comuna_desde_texto(item.get('content')))
        ),
        '',
    )
    ultima_respuesta = next(
        (
            _texto_normalizado(item.get('content'))
            for item in reversed(recientes)
            if item.get('role') == 'assistant'
        ),
        '',
    )
    ofrecio_busqueda = (
        ('buscar' in ultima_respuesta or 'busque' in ultima_respuesta)
        and ('maestro' in ultima_respuesta or 'profesional' in ultima_respuesta)
    )
    pidio_comuna = 'comuna' in ultima_respuesta and 'trabajo' in ultima_respuesta
    pidio_especialidad = 'que trabajo necesitas realizar' in ultima_respuesta
    en_flujo_maestro = 'maestro' in ultima_respuesta or 'profesional' in ultima_respuesta
    return (
        especialidad,
        comuna,
        ofrecio_busqueda,
        pidio_comuna,
        pidio_especialidad,
        en_flujo_maestro,
    )


def _completar_intencion_maestro(datos, mensaje, historial):
    mensaje_normalizado = ' '.join(
        re.sub(r'[^a-z0-9 ]+', ' ', _texto_normalizado(mensaje)).split()
    )
    (
        especialidad_contexto,
        comuna_contexto,
        ofrecio_busqueda,
        pidio_comuna,
        pidio_especialidad,
        en_flujo_maestro,
    ) = _contexto_maestro(historial)
    especialidad_mensaje = _especialidad_desde_texto(mensaje)
    comuna_mensaje = _comuna_desde_texto(mensaje)
    aceptacion = mensaje_normalizado in ACEPTACIONES_MAESTRO
    solicitud_directa = _es_solicitud_directa_maestro(mensaje)
    todas_las_comunas = _pide_todas_las_comunas(mensaje)
    otra_comuna = _pide_otra_comuna(mensaje)
    listado_especialidad = _pide_listado_especialidad(mensaje)
    cambio_especialidad_contextual = bool(especialidad_mensaje and en_flujo_maestro)

    if (
        solicitud_directa
        or listado_especialidad
        or (aceptacion and ofrecio_busqueda)
        or (pidio_comuna and comuna_mensaje)
        or (pidio_especialidad and especialidad_mensaje)
        or ((en_flujo_maestro or pidio_comuna) and (todas_las_comunas or otra_comuna))
        or cambio_especialidad_contextual
    ):
        datos['intencion'] = 'buscar_maestro'

    if datos.get('intencion') != 'buscar_maestro':
        return datos

    especialidad_interpretada = _especialidad_desde_texto(
        datos.get('especialidad_maestro') or ''
    )
    permite_contexto = any((
        aceptacion,
        pidio_comuna,
        pidio_especialidad,
        en_flujo_maestro,
        todas_las_comunas,
        otra_comuna,
    ))
    if solicitud_directa and not especialidad_mensaje:
        datos['especialidad_maestro'] = ''
    else:
        datos['especialidad_maestro'] = especialidad_mensaje or (
            especialidad_contexto if permite_contexto else especialidad_interpretada
        )
    comuna_interpretada = _comuna_desde_texto(datos.get('comuna_maestro') or '')
    if todas_las_comunas or listado_especialidad:
        datos['comuna_maestro'] = TODAS_LAS_COMUNAS
    elif otra_comuna:
        datos['comuna_maestro'] = ''
    elif comuna_mensaje:
        datos['comuna_maestro'] = comuna_mensaje
    elif aceptacion or cambio_especialidad_contextual or pidio_especialidad:
        datos['comuna_maestro'] = comuna_contexto
    elif solicitud_directa:
        datos['comuna_maestro'] = ''
    else:
        datos['comuna_maestro'] = comuna_interpretada
    datos['descripcion_trabajo'] = str(
        datos.get('descripcion_trabajo') or mensaje
    ).strip()[:300]
    return datos


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

    texto_mensaje = _texto_normalizado(mensaje)
    indicadores_excluir_herramientas = (
        'excluir herramientas', 'sin herramientas', 'quitar herramientas',
        'solo materiales', 'sin taladro',
    )
    indicadores_incluir_herramientas = (
        'incluir herramientas', 'herramienta', 'herramientas', 'taladro',
        'cinta metrica', 'wincha', 'metro', 'con herramientas',
    )

    if any(indicador in texto_mensaje for indicador in indicadores_excluir_herramientas):
        datos['incluir_herramientas'] = False
    elif datos.get('incluir_herramientas'):
        if not any(indicador in texto_usuario for indicador in indicadores_incluir_herramientas):
            datos['incluir_herramientas'] = False
    elif any(indicador in texto_mensaje for indicador in indicadores_incluir_herramientas):
        datos['incluir_herramientas'] = True

    proyecto_normalizado = _texto_normalizado(datos.get('proyecto'))
    es_proyecto_bano = (
        datos.get('intencion') == 'planificar_proyecto'
        and ('bano' in proyecto_normalizado or 'bano' in texto_usuario)
    )
    if es_proyecto_bano:
        solicita_completo = any(frase in texto_usuario for frase in (
            'bano completo', 'renovacion completa', 'remodelacion completa',
            'renovar todo', 'remodelar todo', 'cambiar todo',
        ))
        menciona_piso = any(palabra in texto_usuario for palabra in (
            'piso', 'suelo', 'porcelanato',
        ))
        menciona_muros = any(palabra in texto_usuario for palabra in (
            'muro', 'muros', 'pared', 'paredes', 'revestir muro', 'revestir pared',
        ))
        menciona_artefactos = any(palabra in texto_usuario for palabra in (
            'artefacto', 'sanitario', 'inodoro', 'wc', 'lavamanos', 'ducha',
            'griferia',
        ))
        if solicita_completo:
            datos['alcance_bano'] = 'completo'
        elif menciona_piso and menciona_muros:
            datos['alcance_bano'] = 'piso_muros'
        elif menciona_piso:
            datos['alcance_bano'] = 'piso'
        elif menciona_muros:
            datos['alcance_bano'] = 'muros'
        elif menciona_artefactos:
            datos['alcance_bano'] = 'artefactos'
        else:
            datos['alcance_bano'] = ''

        exclusiones = {
            'incluir_sanitario': ('sin sanitario', 'sin inodoro', 'no cambiar el sanitario'),
            'incluir_lavamanos': ('sin lavamanos', 'no cambiar el lavamanos'),
            'incluir_ducha': ('sin ducha', 'no cambiar la ducha'),
        }
        solicitudes = {
            'incluir_sanitario': ('sanitario', 'inodoro', ' wc '),
            'incluir_lavamanos': ('lavamanos', 'vanitorio', 'mueble de bano'),
            'incluir_ducha': ('ducha', 'regadera'),
        }
        texto_delimitado = f' {texto_usuario} '
        for campo, palabras in solicitudes.items():
            incluir = solicita_completo or any(
                palabra in texto_delimitado for palabra in palabras
            )
            if any(frase in texto_usuario for frase in exclusiones[campo]):
                incluir = False
            datos[campo] = incluir

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


def _paquetes_para_unidades(producto, unidades_necesarias):
    """Convierte unidades físicas a envases usando la presentación real del catálogo."""
    if not producto:
        return 0
    contenido = Decimal(producto.contenido or 1)
    if producto.unidad_contenido != 'unidad' or contenido <= 0:
        contenido = Decimal(1)
    return int(
        (Decimal(unidades_necesarias) / contenido).to_integral_value(
            rounding=ROUND_CEILING
        )
    )


def _tableros_para_repisas(producto, ancho_cm, fondo_cm, cantidad):
    """Estima cortes rectangulares completos usando las dimensiones registradas."""
    if not producto:
        return cantidad, 1
    dimensiones = str((producto.especificaciones or {}).get('Dimensiones') or '')
    medidas = [
        Decimal(valor.replace(',', '.'))
        for valor in re.findall(r'\d+(?:[.,]\d+)?', dimensiones)[:2]
    ]
    if len(medidas) < 2:
        return cantidad, 1
    largo_tablero, fondo_tablero = medidas
    ancho = Decimal(ancho_cm)
    fondo = Decimal(fondo_cm)
    cortes_directos = int(largo_tablero // ancho) * int(fondo_tablero // fondo)
    cortes_girados = int(largo_tablero // fondo) * int(fondo_tablero // ancho)
    cortes_por_tablero = max(cortes_directos, cortes_girados, 1)
    tableros = int(
        (Decimal(cantidad) / Decimal(cortes_por_tablero)).to_integral_value(
            rounding=ROUND_CEILING
        )
    )
    return tableros, cortes_por_tablero


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
    descripcion_cantidad = '1 repisa' if cantidad == 1 else f'{cantidad} repisas'
    muro_display = {
        'hormigon': 'hormigón',
        'ladrillo': 'ladrillo',
        'yeso_carton': 'yeso-cartón',
        'madera': 'madera',
    }.get(datos['tipo_muro'], datos['tipo_muro'].replace('_', '-'))
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

    incluir_herramientas = bool(datos.get('incluir_herramientas'))

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

    tableros_necesarios, cortes_por_tablero = _tableros_para_repisas(
        tablero, ancho_cm, fondo_cm, cantidad
    )
    paquetes_escuadras = _paquetes_para_unidades(escuadras, 2 * cantidad)
    paquetes_fijacion = _paquetes_para_unidades(fijacion_muro, 4 * cantidad)
    paquetes_tornillos = _paquetes_para_unidades(tornillos_madera, 4 * cantidad)
    if datos['tipo_muro'] == 'madera':
        paquetes_tornillos = _paquetes_para_unidades(tornillos_madera, 8 * cantidad)
    # Cada repisa usa la secuencia completa 120, 180 y 240 registrada en el pack.
    paquetes_lija = _paquetes_para_unidades(lijas, 3 * cantidad)

    definiciones = [
        (
            tablero,
            tableros_necesarios,
            'Superficie de la repisa',
            f'{tableros_necesarios} tablero(s) para obtener {cantidad} corte(s) de '
            f'{ancho_cm} × {fondo_cm} cm; caben hasta {cortes_por_tablero} por tablero',
        ),
        (escuadras, paquetes_escuadras, 'Soporte mural', f'{2 * cantidad} escuadra(s), dos por repisa'),
        (
            fijacion_muro,
            paquetes_tornillos if datos['tipo_muro'] == 'madera' else paquetes_fijacion,
            'Fijación al muro',
            f'Fijación compatible con muro de {muro_display}',
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

    if incluir_herramientas:
        taladro = _producto_catalogo('Taladro percutor')
        cinta_metrica = _producto_catalogo('Cinta métrica')
        if taladro:
            definiciones.append((
                taladro,
                1,
                'Herramienta recomendada: Taladro',
                'Taladro percutor para perforar el muro e instalar fijaciones',
            ))
        if cinta_metrica:
            definiciones.append((
                cinta_metrica,
                1,
                'Herramienta recomendada: Cinta métrica',
                'Cinta métrica para medir y ubicar la repisa',
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
                f'Encontré parte de los materiales para {descripcion_cantidad} de '
                f'{ancho_cm} × {fondo_cm} cm, pero todavía falta: {"; ".join(nombres_faltantes)}. '
                'No cierro el presupuesto como completo hasta que todos los materiales tengan stock.'
            ),
            'productos': productos_kit,
            'faltantes_catalogo': nombres_faltantes,
            'presupuesto': int(datos.get('presupuesto') or 0),
            'sugerencias': ['Ver productos disponibles', 'Probar otra medida'],
        }

    subtotal_herramientas = sum(
        item['subtotal']
        for item in productos_kit
        if str(item['rol']).startswith('Herramienta recomendada')
    )
    subtotal_materiales = sum(item['subtotal'] for item in productos_kit) - subtotal_herramientas
    subtotal_basico = subtotal_materiales + subtotal_herramientas
    item_barniz = _item_proyecto(
        barniz,
        1,
        'Terminación opcional',
        'Barniz satinado para proteger la madera en interior',
    )
    total_terminado = subtotal_basico + (item_barniz['subtotal'] if item_barniz else 0)
    if item_barniz:
        item_barniz['es_opcional'] = True
        item_barniz['incluido_en_total'] = False
        productos_kit.append(item_barniz)

    presupuesto = int(datos.get('presupuesto') or 0)
    resumen_costos = f'Los materiales obligatorios suman {_formatear_clp(subtotal_materiales)}.'
    if subtotal_herramientas:
        resumen_costos += (
            f' Las herramientas seleccionadas suman {_formatear_clp(subtotal_herramientas)}; '
            f'el total seleccionado sin barniz es {_formatear_clp(subtotal_basico)}.'
        )
    if item_barniz:
        resumen_costos += (
            f' El barniz opcional cuesta {_formatear_clp(item_barniz["subtotal"])} y, '
            f'si lo agregas, el total es {_formatear_clp(total_terminado)}.'
        )
    if presupuesto:
        if presupuesto >= subtotal_basico:
            saldo = presupuesto - subtotal_basico
            mensaje_presupuesto = (
                f'Tu presupuesto alcanza para el total seleccionado y quedan '
                f'{_formatear_clp(saldo)}.'
            )
        else:
            diferencia = subtotal_basico - presupuesto
            mensaje_presupuesto = (
                f'Tu presupuesto de {_formatear_clp(presupuesto)} no alcanza para el total '
                f'seleccionado de {_formatear_clp(subtotal_basico)}: faltan '
                f'{_formatear_clp(diferencia)}.'
            )
        if item_barniz and presupuesto >= total_terminado:
            saldo = presupuesto - total_terminado
            mensaje_presupuesto += (
                f' También alcanza incluyendo el barniz y quedarían '
                f'{_formatear_clp(saldo)}.'
            )
    else:
        mensaje_presupuesto = ''

    texto_materiales = 'materiales y herramientas recomendadas' if incluir_herramientas else 'materiales'
    sugerencia_herramientas = (
        'Excluir herramientas' if incluir_herramientas else 'Incluir también herramientas'
    )

    return {
        'tipo': 'plan_proyecto',
        'mensaje': (
            f'Preparé los {texto_materiales} para {descripcion_cantidad} de {ancho_cm} × {fondo_cm} cm '
            f'en muro de {muro_display}. {resumen_costos} '
            f'{mensaje_presupuesto} Antes de instalar, verifica la carga admisible del muro, '
            'la ubicación de instalaciones ocultas y la fijación indicada por el fabricante. '
            'Si prefieres no instalarla tú mismo, también puedo buscar un maestro carpintero '
            'para realizar el trabajo.'
        ),
        'productos': productos_kit,
        'faltantes_catalogo': [],
        'presupuesto': presupuesto,
        'subtotal_materiales': subtotal_materiales,
        'subtotal_herramientas': subtotal_herramientas,
        'subtotal_basico': subtotal_basico,
        'subtotal_opcionales': item_barniz['subtotal'] if item_barniz else 0,
        'total_con_terminacion': total_terminado,
        'sugerencias': [
            'Buscar maestro carpintero',
            sugerencia_herramientas,
            'Cambiar las medidas de la repisa',
        ],
    }


def _cantidad_por_cobertura(producto, superficie_m2, aplicar_desperdicio=True):
    """Convierte una superficie en envases usando solo la ficha técnica del producto."""
    if not producto or not producto.rendimiento or superficie_m2 <= 0:
        return 0
    cobertura = Decimal(producto.rendimiento)
    if cobertura <= 0:
        return 0
    superficie = Decimal(str(superficie_m2))
    if aplicar_desperdicio:
        desperdicio = Decimal(producto.porcentaje_desperdicio or 0) / Decimal('100')
        superficie *= Decimal('1') + desperdicio
    return int(
        (superficie / cobertura).to_integral_value(rounding=ROUND_CEILING)
    )


def _resolver_bano(datos):
    alcance = str(datos.get('alcance_bano') or '').strip()
    alcances_validos = {'piso', 'muros', 'piso_muros', 'artefactos', 'completo'}
    if alcance not in alcances_validos:
        return {
            'tipo': 'aclaracion',
            'mensaje': (
                '¿Qué parte del baño quieres renovar: piso, muros, artefactos sanitarios '
                'o una renovación completa? Con eso te pediré solamente las medidas necesarias.'
            ),
            'productos': [],
            'sugerencias': [
                'Solo el piso del baño',
                'Piso y muros del baño',
                'Baño completo con sanitario, lavamanos y ducha',
            ],
        }

    incluye_piso = alcance in {'piso', 'piso_muros', 'completo'}
    incluye_muros = alcance in {'muros', 'piso_muros', 'completo'}
    incluye_sanitario = bool(datos.get('incluir_sanitario')) or alcance == 'completo'
    incluye_lavamanos = bool(datos.get('incluir_lavamanos')) or alcance == 'completo'
    incluye_ducha = bool(datos.get('incluir_ducha')) or alcance == 'completo'
    superficie_piso = max(0, int(datos.get('superficie') or 0))
    superficie_muros = max(0, int(datos.get('superficie_muros') or 0))

    faltantes_medidas = []
    if incluye_piso and not superficie_piso:
        faltantes_medidas.append('los metros cuadrados del piso')
    if incluye_muros and not superficie_muros:
        faltantes_medidas.append('los metros cuadrados de muros que revestirás')
    if alcance == 'artefactos' and not any((
        incluye_sanitario, incluye_lavamanos, incluye_ducha,
    )):
        return {
            'tipo': 'aclaracion',
            'mensaje': '¿Qué quieres cambiar: sanitario, lavamanos, ducha o los tres?',
            'productos': [],
            'sugerencias': [
                'Cambiar sanitario',
                'Cambiar lavamanos y grifería',
                'Cambiar sanitario, lavamanos y ducha',
            ],
        }
    if faltantes_medidas:
        detalle = (
            faltantes_medidas[0]
            if len(faltantes_medidas) == 1
            else ' y '.join(faltantes_medidas)
        )
        return {
            'tipo': 'aclaracion',
            'mensaje': (
                f'Para calcular materiales reales necesito {detalle}. '
                'Indica superficies completas; agregaré el desperdicio de instalación desde '
                'la ficha técnica de cada producto.'
            ),
            'productos': [],
            'sugerencias': [
                'El piso tiene 6 m² y los muros 20 m²',
                'Solo el piso tiene 5 m²',
            ],
        }

    superficie_total = superficie_piso + superficie_muros
    if superficie_piso > 200 or superficie_muros > 500:
        return {
            'tipo': 'orientacion',
            'mensaje': (
                'Las superficies indicadas superan el alcance de una renovación residencial '
                'básica. Conviene validar medidas, soportes, impermeabilización y cubicación '
                'con un profesional antes de comprar.'
            ),
            'productos': [],
            'sugerencias': ['Corregir las medidas', 'Buscar maestro ceramista'],
        }

    porcelanato = _producto_catalogo('Porcelanato piso baño gris')
    ceramica_muro = _producto_catalogo('Cerámica muro baño blanca')
    adhesivo = _producto_catalogo('Adhesivo cerámico zonas húmedas')
    frague = _producto_catalogo('Fragüe impermeable gris')
    membrana = _producto_catalogo('Membrana impermeable flexible')
    separadores = _producto_catalogo('Separadores para cerámica 3 mm')
    silicona = _producto_catalogo('Silicona sanitaria antihongos')
    sanitario = _producto_catalogo('Sanitario dos piezas doble descarga')
    mueble_lavamanos = _producto_catalogo('Mueble lavamanos 60 cm')
    monomando_lavamanos = _producto_catalogo('Monomando cromado para lavamanos')
    conexiones_lavamanos = _producto_catalogo('Kit conexión lavamanos')
    kit_ducha = _producto_catalogo('Kit ducha cromado')

    definiciones = []
    if incluye_piso:
        definiciones.append((
            porcelanato,
            _cantidad_por_cobertura(porcelanato, superficie_piso),
            'Revestimiento de piso',
            f'{superficie_piso} m² de piso más el desperdicio de instalación de la ficha',
        ))
    if incluye_muros:
        definiciones.append((
            ceramica_muro,
            _cantidad_por_cobertura(ceramica_muro, superficie_muros),
            'Revestimiento de muros',
            f'{superficie_muros} m² de muros más el desperdicio de instalación de la ficha',
        ))
    if superficie_total:
        definiciones.extend([
            (
                membrana,
                _cantidad_por_cobertura(membrana, superficie_total),
                'Impermeabilización previa',
                f'Cobertura para {superficie_total} m² antes de instalar revestimientos',
            ),
            (
                adhesivo,
                _cantidad_por_cobertura(adhesivo, superficie_total),
                'Adhesivo para revestimientos',
                f'Instalación de {superficie_total} m² de piso y/o muros',
            ),
            (
                frague,
                _cantidad_por_cobertura(frague, superficie_total),
                'Sellado de juntas',
                f'Fragüe para {superficie_total} m²; el consumo real depende del formato y la junta',
            ),
            (
                separadores,
                _cantidad_por_cobertura(separadores, superficie_total, False),
                'Separación uniforme',
                f'Separadores de 3 mm para aproximadamente {superficie_total} m²',
            ),
        ])

    if superficie_total or any((incluye_sanitario, incluye_lavamanos, incluye_ducha)):
        cartuchos_silicona = max(
            1,
            int(
                (Decimal(max(superficie_total, 1)) / Decimal('20')).to_integral_value(
                    rounding=ROUND_CEILING
                )
            ),
        )
        definiciones.append((
            silicona,
            cartuchos_silicona,
            'Sellado sanitario',
            'Sellado flexible de encuentros y artefactos; no reemplaza la impermeabilización',
        ))
    if incluye_sanitario:
        definiciones.append((
            sanitario, 1, 'Sanitario',
            'Sanitario con doble descarga; verificar salida, distancia al muro y llave de paso',
        ))
    if incluye_lavamanos:
        definiciones.extend([
            (
                mueble_lavamanos, 1, 'Mueble y lavamanos',
                'Mueble de 60 cm con cubierta de loza; verificar espacio disponible',
            ),
            (
                monomando_lavamanos, 1, 'Grifería de lavamanos',
                'Monomando con flexibles para agua fría y caliente',
            ),
            (
                conexiones_lavamanos, 1, 'Conexión de lavamanos',
                'Sifón, desagüe, flexibles y sellos; comprobar diámetros existentes',
            ),
        ])
    if incluye_ducha:
        definiciones.append((
            kit_ducha, 1, 'Grifería y ducha',
            'Conjunto con monomando y ducha teléfono; verificar conexiones y presión',
        ))

    productos_plan = []
    faltantes_catalogo = []
    for producto, cantidad, rol, detalle in definiciones:
        item = _item_proyecto(producto, cantidad, rol, detalle)
        if item:
            productos_plan.append(item)
        elif not producto:
            faltantes_catalogo.append(rol)
        else:
            faltantes_catalogo.append(f'{rol} (stock insuficiente)')

    subtotal = sum(item['subtotal'] for item in productos_plan)
    presupuesto = int(datos.get('presupuesto') or 0)
    alcance_display = {
        'piso': 'el piso del baño',
        'muros': 'los muros del baño',
        'piso_muros': 'el piso y los muros del baño',
        'artefactos': 'los artefactos del baño',
        'completo': 'una renovación completa del baño',
    }[alcance]

    if faltantes_catalogo:
        mensaje_stock = (
            f' Falta completar: {"; ".join(faltantes_catalogo)}. No presento el presupuesto '
            'como completo hasta que todo tenga stock.'
        )
    else:
        mensaje_stock = ' Todos los productos seleccionados tienen stock registrado.'

    mensaje_presupuesto = ''
    if presupuesto:
        if presupuesto >= subtotal and not faltantes_catalogo:
            mensaje_presupuesto = (
                f' Tu presupuesto de {_formatear_clp(presupuesto)} alcanza y quedarían '
                f'{_formatear_clp(presupuesto - subtotal)}.'
            )
        elif subtotal > presupuesto:
            mensaje_presupuesto = (
                f' Tu presupuesto de {_formatear_clp(presupuesto)} no alcanza para los '
                f'productos disponibles: faltan {_formatear_clp(subtotal - presupuesto)}.'
            )

    sugerencias = ['Cambiar superficies o alcance']
    if not incluye_sanitario:
        sugerencias.append('Agregar sanitario al proyecto')
    if not incluye_lavamanos:
        sugerencias.append('Agregar lavamanos al proyecto')
    if not incluye_ducha:
        sugerencias.append('Agregar ducha al proyecto')
    sugerencias.extend(['Buscar maestro ceramista', 'Buscar maestro gasfíter'])

    return {
        'tipo': 'plan_proyecto',
        'mensaje': (
            f'Preparé materiales para {alcance_display}. El total de productos disponibles '
            f'es {_formatear_clp(subtotal)}.{mensaje_stock}{mensaje_presupuesto} '
            'La estimación no incluye mano de obra, retiro de escombros ni reparaciones ocultas. '
            'Antes de intervenir agua, desagües o impermeabilización, verifica medidas y '
            'compatibilidad; para esas conexiones conviene un gasfíter y para revestimientos '
            'un maestro ceramista.'
        ),
        'productos': productos_plan,
        'faltantes_catalogo': faltantes_catalogo,
        'presupuesto': presupuesto,
        'subtotal_materiales': subtotal,
        'subtotal_herramientas': 0,
        'subtotal_basico': subtotal,
        'subtotal_opcionales': 0,
        'total_con_terminacion': subtotal,
        'superficie_piso': superficie_piso,
        'superficie_muros': superficie_muros,
        'sugerencias': sugerencias,
    }


def _resolver_proyecto(datos):
    proyecto = _texto_normalizado(datos.get('proyecto'))
    if 'repisa' in proyecto or 'estante' in proyecto:
        return _resolver_repisa(datos)
    if 'bano' in proyecto or 'sanitario' in proyecto:
        return _resolver_bano(datos)
    orientacion = str(datos.get('respuesta') or '').strip()
    mensaje = (
        f'{orientacion} ' if orientacion else ''
    ) + (
        'Todavía no puedo cerrar una cotización completa y verificable para ese proyecto '
        'con el catálogo actual. Sí puedo planificar una repisa o renovar un baño; para otros proyectos te '
        'indicaré materiales generales y cuáles faltan antes de calcular un presupuesto.'
    )
    return {
        'tipo': 'aclaracion',
        'mensaje': mensaje,
        'productos': [],
        'sugerencias': ['Quiero construir una repisa', 'Quiero renovar mi baño'],
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
            f'{mensaje_presupuesto} Si prefieres que un profesional realice el trabajo, '
            'también puedo buscar un maestro pintor.'
        ),
        'productos': productos,
        'sugerencias': [
            'Buscar maestro pintor',
            'Buscar otra terminación',
            'Ver pinturas de otro color',
        ],
    }


def _resolver_busqueda_maestro(datos):
    especialidad = str(datos.get('especialidad_maestro') or '').strip()
    comuna = str(datos.get('comuna_maestro') or '').strip()
    todas_las_comunas = comuna == TODAS_LAS_COMUNAS
    if not especialidad:
        return {
            'tipo': 'aclaracion_maestro',
            'mensaje': '¿Qué trabajo necesitas realizar?',
            'productos': [],
            'maestros': [],
            'sugerencias': [
                'Necesito un carpintero',
                'Necesito un pintor',
                'Necesito un gasfíter',
            ],
        }
    if not comuna:
        return {
            'tipo': 'aclaracion_maestro',
            'mensaje': 'Claro. ¿En qué comuna necesitas el trabajo?',
            'productos': [],
            'maestros': [],
            'sugerencias': [
                'Maipú',
                'Santiago',
                f'Ver todos los maestros de {especialidad}',
            ],
        }

    comuna_consulta = None if todas_las_comunas else comuna
    maestros = buscar_maestros(especialidad, comuna_consulta, limite=5)
    if not maestros:
        alcance = 'en todas las comunas' if todas_las_comunas else f'en {comuna}'
        return {
            'tipo': 'sin_resultados_maestros',
            'mensaje': (
                'No encontré maestros verificados disponibles para '
                f'{especialidad} {alcance} en este momento.'
            ),
            'productos': [],
            'maestros': [],
            'sugerencias': [
                'Buscar en otra comuna',
                f'Ver todos los maestros de {especialidad}',
                'Buscar otra especialidad',
            ],
        }
    cantidad = len(maestros)
    sustantivo = 'maestro verificado disponible' if cantidad == 1 else 'maestros verificados disponibles'
    alcance = 'sin filtrar por comuna' if todas_las_comunas else f'en {comuna}'
    return {
        'tipo': 'maestros',
        'mensaje': (
            f'Encontré {cantidad} {sustantivo} para {especialidad} {alcance}.'
        ),
        'productos': [],
        'maestros': maestros,
        'sugerencias': [
            'Buscar en otra comuna',
            f'Ver todos los maestros de {especialidad}',
            'Ver otra especialidad',
        ],
    }


def resolver_interpretacion(datos):
    intencion = datos.get('intencion')
    if intencion == 'buscar_maestro':
        return _resolver_busqueda_maestro(datos)
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
    interpretacion = _completar_intencion_maestro(
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
