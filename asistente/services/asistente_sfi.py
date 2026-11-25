import re
import unicodedata
from decimal import Decimal, ROUND_CEILING

from django.db.models import Case, IntegerField, Q, Value, When

from maestros.chile import COMUNAS_CHOICES
from maestros.services import buscar_maestros
from productos.models import Producto
from productos.services import calcular_producto_pintura, calcular_recomendaciones_pintura
from .gemini import GeminiNoDisponible, interpretar_con_gemini
from .recomendacion_colores import (
    color_publico,
    detectar_contexto_pintura,
    pinturas_compatibles,
)
from .sinonimos_ferreteros import (
    anclas_semanticas, corregir_terminos, expandir_consulta,
)
from .planificador_proyectos import resolver_proyecto_generico, resolver_proyecto_techumbre
from .situaciones_cotidianas import detectar_situacion_cotidiana


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
    texto = ''.join(
        caracter for caracter in texto if not unicodedata.combining(caracter)
    )
    # Correcciones pequeñas y seguras para palabras que expresan la acción.
    # No se corrigen nombres de productos ni materiales por aproximación.
    correcciones_accion = {
        'neceisto': 'necesito',
        'nesecito': 'necesito',
        'quje': 'que',
        'quieor': 'quiero',
        'maetsro': 'maestro',
        'profecional': 'profesional',
        'herrameintas': 'herramientas',
        'heramientas': 'herramientas',
        'prodcutos': 'productos',
        'econimico': 'economico',
        'preico': 'precio',
        'cantdiad': 'cantidad',
        'eligue': 'elige',
        'necesrto': 'necesito',
        'nesesito': 'necesito',
        'necesrta': 'necesita',
        'instalcion': 'instalacion',
        'instalacionnes': 'instalaciones',
        'cainerias': 'canerias',
        'lavapaltos': 'lavaplatos',
    }
    return re.sub(
        r'\b(?:' + '|'.join(map(re.escape, correcciones_accion)) + r')\b',
        lambda coincidencia: correcciones_accion[coincidencia.group(0)],
        texto,
    )


def _aplicar_contexto_calculo_pintura(datos, mensaje, historial):
    """Enruta cálculos de pintura explícitos sin afectar otros proyectos."""
    texto_actual = _texto_normalizado(mensaje)
    usuarios = ' '.join(
        str(item.get('content') or '')
        for item in historial
        if item.get('role') == 'user'
    )
    texto_usuario = _texto_normalizado(f'{usuarios} {mensaje}')
    ultimo_asistente = next((
        _texto_normalizado(item.get('content'))
        for item in reversed(historial)
        if item.get('role') == 'assistant'
    ), '')

    menciona_pintura = bool(re.search(
        r'\b(?:pintura|pintar|latex|esmalte|barniz)\b', texto_actual,
    ))
    pide_cantidad = bool(re.search(
        r'\b(?:cuanto|cuanta|cuantos|cuantas|litros?|envases?|tarros?|'
        r'cantidad|necesito|comprar|rinde|rendimiento)\b', texto_actual,
    ))
    informa_superficie = bool(re.search(
        r'\b\d+(?:[.,]\d+)?\s*(?:m2|m²|metros? cuadrados?)\b|'
        r'\b\d+(?:[.,]\d+)?\s*(?:x|por)\s*\d+(?:[.,]\d+)?\s*'
        r'(?:m|mts?|metros?)\b',
        texto_actual,
    ))
    seguimiento_pintura = (
        'pintura' in ultimo_asistente
        and not re.search(
            r'\b(?:quincho|techo|techumbre|ceramica|piso flotante|mueble|'
            r'cobertizo|bodega|radier)\b',
            texto_actual,
        )
    )
    pide_similar = bool(re.search(
        r'\b(?:alguna|alguno|otra|otro|tono|color)\b.{0,20}\b'
        r'(?:parecid[oa]|similar|cercan[oa])\b|\b(?:parecid[oa]|similar)\b',
        texto_actual,
    ))
    es_calculo = (
        (menciona_pintura and (pide_cantidad or informa_superficie))
        or (seguimiento_pintura and (informa_superficie or pide_similar))
        or datos.get('intencion') == 'calcular_pintura'
    )
    if not es_calculo:
        return datos

    datos['intencion'] = 'calcular_pintura'

    superficies = re.findall(
        r'\b(\d+(?:[.,]\d+)?)\s*(?:m2|m²|metros? cuadrados?)\b',
        texto_usuario,
    )
    if superficies:
        datos['superficie'] = float(superficies[-1].replace(',', '.'))
    else:
        ancho_cm, largo_cm = _dimensiones_rectangulares_cm(texto_usuario)
        if ancho_cm and largo_cm:
            datos['superficie'] = round((ancho_cm * largo_cm) / 10000, 3)

    if not datos.get('ambiente'):
        if re.search(r'\b(?:piscina|estanque)\b', texto_usuario):
            datos['ambiente'] = 'especial'
        elif re.search(r'\b(?:exterior|fachada|afuera)\b', texto_usuario):
            datos['ambiente'] = 'exterior'
        elif re.search(
            r'\b(?:interior|habitacion|pieza|dormitorio|living|comedor|pasillo)\b',
            texto_usuario,
        ):
            datos['ambiente'] = 'interior'

    if not datos.get('tipo_superficie'):
        superficies_conocidas = (
            ('piscina_estanque', r'\b(?:piscina|estanque)\b'),
            ('yeso_carton', r'\b(?:yeso carton|volcanita)\b'),
            ('hormigon', r'\b(?:hormigon|cemento|concreto)\b'),
            ('ladrillo', r'\bladrillos?\b'),
            ('madera', r'\bmadera\b'),
            ('metal', r'\b(?:metal|fierro|acero)\b'),
        )
        for codigo, patron in superficies_conocidas:
            if re.search(patron, texto_usuario):
                datos['tipo_superficie'] = codigo
                break

    if not datos.get('estado_superficie'):
        if re.search(r'\b(?:nueva|nuevo|sin pintar)\b', texto_usuario):
            datos['estado_superficie'] = 'nueva'
        elif re.search(r'\b(?:humedad|humeda|humedo|moho)\b', texto_usuario):
            datos['estado_superficie'] = 'humedad'
        elif re.search(r'\b(?:deteriorada|deteriorado|grietas?|descascarad[oa])\b', texto_usuario):
            datos['estado_superficie'] = 'deteriorada'
        elif re.search(r'\b(?:buen estado|pintada|pintado|esta bien)\b', texto_usuario):
            datos['estado_superficie'] = 'pintada_buen_estado'

    if pide_similar:
        datos['_permitir_color_alternativo'] = True
    return datos


def _usuario_delega_eleccion(texto):
    """Reconoce formas naturales de pedir que el asistente decida."""
    normalizado = _texto_normalizado(texto)
    return bool(re.search(
        r'\belige(?:lo|la|los|las)?\s+tu\b|\btu\s+elige(?:lo|la|los|las)?\b|'
        r'\bque\s+(?:\w+\s+){0,3}me\s+recomiendas\b|'
        r'\bcual\s+(?:\w+\s+){0,3}(?:conviene|recomiendas)\b',
        normalizado,
    )) or any(frase in normalizado for frase in (
        'elige tu', 'tu elige', 'elige por mi', 'damelo tu', 'dame tu',
        'decide tu', 'tu decide', 'recomiendame', 'recomienda tu',
        'que me recomiendas', 'cual me recomiendas', 'lo que recomiendes',
        'la que recomiendes', 'el que recomiendes',
        'lo dejo a tu criterio',
    ))


def _presupuesto_desde_texto(texto):
    """Obtiene un presupuesto explícito sin depender de la interpretación externa."""
    normalizado = _texto_normalizado(texto)
    coincidencia = re.search(r'\b(\d+(?:[.,]\d+)?)\s*(?:lucas?|mil|k)\b', normalizado)
    if coincidencia:
        return int(float(coincidencia.group(1).replace(',', '.')) * 1000)

    coincidencia = re.search(r'\$\s*([\d.]+)', normalizado)
    if not coincidencia:
        coincidencia = re.search(r'\b([\d.]+)\s*(?:pesos|clp)\b', normalizado)
    if coincidencia:
        return int(coincidencia.group(1).replace('.', ''))
    return 0


def _medidas_desde_texto(texto):
    """Detecta medidas consultadas para no mezclar formatos incompatibles."""
    patron = r'(?<!\w)(\d+(?:[.,]\d+)?)\s*(mm|cm|m|mts?|metros?|w|v|oz|kg|galones?|litros?|l|lts?)\b'
    return [
        f'{numero.replace(",", ".")}{unidad}'
        for numero, unidad in re.findall(patron, _texto_normalizado(texto))
    ]


def _dimensiones_rectangulares_cm(texto):
    """Extrae ancho y largo explícitos como 3 x 5 m, sin estimarlos."""
    normalizado = _texto_normalizado(texto)
    numero = r'(\d+(?:[.,]\d+)?)'
    # En lenguaje cotidiano es frecuente escribir "3 x 6 m2" aunque cada
    # cifra sea una longitud. Dentro de una expresión rectangular se interpreta
    # como metros; fuera de ella, m² conserva su significado de superficie.
    unidad = r'(mm|cm|m2|m²|m|mts?|metros?)'
    coincidencia = re.search(
        rf'(?<!\w){numero}\s*(?:x|por)\s*{numero}\s*{unidad}\b',
        normalizado,
    )
    if not coincidencia:
        coincidencia = re.search(
            rf'(?<!\w){numero}\s*{unidad}\s*(?:x|por)\s*{numero}\s*\2\b',
            normalizado,
        )
        if coincidencia:
            ancho, unidad_detectada, largo = coincidencia.groups()
            valores = ancho, largo, unidad_detectada
        else:
            valores = None
    else:
        valores = coincidencia.groups()
    if not coincidencia:
        return 0, 0
    ancho, largo, unidad_detectada = valores
    factor = 0.1 if unidad_detectada == 'mm' else (100 if unidad_detectada.startswith('m') else 1)
    return (
        round(float(ancho.replace(',', '.')) * factor),
        round(float(largo.replace(',', '.')) * factor),
    )


def _contiene_medida(texto, medida):
    numero = re.match(r'\d+(?:\.\d+)?', medida)
    unidad = medida[len(numero.group(0)):]
    # La consulta normaliza decimales a punto, pero las fichas pueden haber
    # sido cargadas con coma. Ambas formas representan la misma medida.
    patron_numero = re.escape(numero.group(0)).replace(r'\.', r'[.,]')
    unidades_equivalentes = {
        'm': ('m', 'mt', 'mts', 'metro', 'metros'),
        'mt': ('m', 'mt', 'mts', 'metro', 'metros'),
        'mts': ('m', 'mt', 'mts', 'metro', 'metros'),
        'litro': ('l', 'lt', 'lts', 'litro', 'litros'),
        'litros': ('l', 'lt', 'lts', 'litro', 'litros'),
        'lts': ('l', 'lt', 'lts', 'litro', 'litros'),
        'galon': ('galon', 'galones'),
        'galones': ('galon', 'galones'),
    }
    opciones = unidades_equivalentes.get(unidad, (unidad,))
    return any(
        re.search(rf'(?<!\w){patron_numero}\s*{re.escape(opcion)}\b', texto)
        for opcion in opciones
    )


def _especialidad_desde_texto(texto):
    normalizado = _texto_normalizado(texto)
    for especialidad, alias in ESPECIALIDADES_MAESTRO.items():
        if any(re.search(rf'\b{re.escape(item)}\b', normalizado) for item in alias):
            return especialidad
    return ''


def _comuna_desde_texto(texto):
    normalizado_limpio = ' '.join(_texto_normalizado(texto).split())
    normalizado = f' {normalizado_limpio} '
    coincidencias = []
    for comuna, _ in COMUNAS_CHOICES:
        clave = _texto_normalizado(comuna)
        if clave == 'retiro' and not (
            normalizado_limpio == 'retiro'
            or re.search(r'\b(?:en|de|comuna(?:\s+de)?)\s+retiro\b', normalizado_limpio)
        ):
            continue
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
        'algun maestro', 'alguna maestra', 'un maestro que me ayude',
        'una maestra que me ayude', 'profesional que me ayude',
        'necesito maestros', 'necesito maestras', 'necesito profesionales',
        'busco maestros', 'busco maestras', 'busco profesionales',
    ))
    accion_con_profesional = any(indicador in texto for indicador in (
        'necesito un ', 'necesito una ', 'busco un ', 'busco una ',
        'quiero contratar', 'buscar maestro', 'buscar maestra',
        'buscar profesional', 'prefiero un maestro', 'prefiero una maestra',
        'muestrame ', 'muestra ', 'ver maestro', 'ver maestra',
        'ver profesional',
    )) and any(referencia in texto for referencia in referencias_profesionales)
    return solicitud_persona or accion_con_profesional


def _pide_todas_las_comunas(mensaje):
    texto = ' '.join(
        re.sub(r'[^a-z0-9 ]+', ' ', _texto_normalizado(mensaje)).split()
    )
    respuestas_breves = {
        'cualquiera', 'de cualquiera', 'todas', 'todos',
        'muestrame todos', 'mostrar todos', 'ver todos',
        'todos los disponibles', 'ver todos los disponibles',
        'muestrame todos los disponibles',
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
        'ver maestros', 'mostrar maestros', 'muestrame los maestros',
        'muestrame maestros', 'muestra los maestros', 'muestra maestros',
    ))


def _historial_autoriza_flujo_maestro(historial):
    """Solo conserva el flujo si el cliente lo inició o aceptó expresamente."""
    ofrecio_busqueda = False
    for item in historial[-6:]:
        contenido = str(item.get('content') or '')
        if item.get('role') == 'assistant':
            normalizado = _texto_normalizado(contenido)
            menciona_profesional = (
                'maestro' in normalizado or 'profesional' in normalizado
            )
            if menciona_profesional and (
                'no encontre' in normalizado or 'encontre maestro' in normalizado
                or 'encontre profesional' in normalizado
            ):
                return True
            ofrecio_busqueda = (
                ('buscar' in normalizado or 'busque' in normalizado)
                and menciona_profesional
            )
            continue
        if item.get('role') != 'user':
            continue
        normalizado = ' '.join(
            re.sub(r'[^a-z0-9 ]+', ' ', _texto_normalizado(contenido)).split()
        )
        if _es_solicitud_directa_maestro(contenido) or _pide_listado_especialidad(contenido):
            return True
        if normalizado in ACEPTACIONES_MAESTRO and ofrecio_busqueda:
            return True
    return False


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
            if item.get('role') == 'user'
            if (encontrada := _comuna_desde_texto(item.get('content')))
        ),
        '',
    )
    if not comuna:
        comuna = next(
            (
                encontrada
                for item in reversed(recientes)
                if item.get('role') == 'assistant'
                if any(
                    referencia in _texto_normalizado(item.get('content'))
                    for referencia in ('maestro', 'maestra', 'profesional')
                )
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
    solicitud_contextual_generica = any(frase in mensaje_normalizado for frase in (
        'algun maestro', 'alguna maestra', 'un maestro que me ayude',
        'una maestra que me ayude', 'profesional que me ayude',
    ))
    todas_las_comunas = _pide_todas_las_comunas(mensaje)
    otra_comuna = _pide_otra_comuna(mensaje)
    buscar_por_comuna = any(frase in mensaje_normalizado for frase in (
        'buscar por comuna', 'filtrar por comuna', 'elegir comuna',
    ))
    listado_especialidad = _pide_listado_especialidad(mensaje)
    flujo_autorizado = _historial_autoriza_flujo_maestro(historial)
    acepto_oferta_actual = aceptacion and ofrecio_busqueda
    contexto_autorizado = flujo_autorizado or acepto_oferta_actual
    resultados_producto = []
    if not solicitud_directa and not listado_especialidad:
        resultados_producto = _buscar_productos(mensaje)
    consulta_producto_evidente = bool(resultados_producto)
    cambio_especialidad_contextual = bool(
        especialidad_mensaje and en_flujo_maestro and contexto_autorizado
        and not consulta_producto_evidente
    )

    activar_busqueda_maestro = (
        solicitud_directa
        or listado_especialidad
        or acepto_oferta_actual
        or (contexto_autorizado and pidio_comuna and comuna_mensaje)
        or (
            contexto_autorizado and pidio_especialidad and especialidad_mensaje
            and not consulta_producto_evidente
        )
        or (contexto_autorizado and (en_flujo_maestro or pidio_comuna) and (
            todas_las_comunas or otra_comuna or buscar_por_comuna
        ))
        or cambio_especialidad_contextual
    )
    if activar_busqueda_maestro:
        datos['intencion'] = 'buscar_maestro'
    elif datos.get('intencion') == 'buscar_maestro':
        # Gemini puede confundir un producto con un oficio (pintura/pintor).
        # Sin una petición expresa del cliente nunca se muestran maestros.
        datos['especialidad_maestro'] = ''
        datos['comuna_maestro'] = ''
        if resultados_producto or _buscar_productos(mensaje):
            datos['intencion'] = 'buscar_producto'
            datos['consulta_producto'] = mensaje
        else:
            datos['intencion'] = 'orientacion_general'
            datos['respuesta'] = (
                'Puedo ayudarte a buscar productos o analizar tu proyecto. '
                'Solo buscaré maestros cuando me lo pidas expresamente.'
            )

    if datos.get('intencion') != 'buscar_maestro':
        return datos

    especialidad_interpretada = _especialidad_desde_texto(
        datos.get('especialidad_maestro') or ''
    )
    permite_contexto = any((
        aceptacion,
        pidio_comuna,
        pidio_especialidad,
        contexto_autorizado,
        todas_las_comunas,
        otra_comuna,
    ))
    if solicitud_directa and not especialidad_mensaje:
        datos['especialidad_maestro'] = especialidad_contexto
    else:
        datos['especialidad_maestro'] = especialidad_mensaje or (
            especialidad_contexto if permite_contexto else especialidad_interpretada
        )
    comuna_interpretada = _comuna_desde_texto(datos.get('comuna_maestro') or '')
    if todas_las_comunas or listado_especialidad:
        datos['comuna_maestro'] = TODAS_LAS_COMUNAS
    elif otra_comuna or buscar_por_comuna:
        datos['comuna_maestro'] = ''
        datos['_preguntar_comuna_maestro'] = True
    elif comuna_mensaje:
        datos['comuna_maestro'] = comuna_mensaje
    elif solicitud_contextual_generica and especialidad_contexto:
        datos['comuna_maestro'] = comuna_contexto
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
    # El planificador determinístico utiliza este resumen solo para conservar
    # requisitos explícitos del cliente que Gemini pudo omitir al estructurar
    # su respuesta (por ejemplo, una luz interior en una bodega).
    # Los cuestionarios de proyectos suelen responderse en varios mensajes.
    # Una ventana amplia conserva ubicación, base y medidas hasta completar
    # el último dato solicitado.
    datos['_contexto_usuario'] = texto_usuario[:3000]

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
    elif presupuesto_expresado:
        presupuesto_detectado = _presupuesto_desde_texto(texto_usuario)
        if presupuesto_detectado:
            datos['presupuesto'] = presupuesto_detectado

    texto_mensaje = _texto_normalizado(mensaje)
    delega_eleccion = _usuario_delega_eleccion(texto_usuario)
    datos['_delega_eleccion'] = delega_eleccion

    # Regla transversal: las medidas expresadas por el cliente pertenecen al
    # proyecto completo, aunque Gemini no las repita en una respuesta breve.
    ancho_cm, fondo_cm = _dimensiones_rectangulares_cm(texto_usuario)
    if ancho_cm and fondo_cm:
        datos['ancho_cm'] = ancho_cm
        datos['fondo_cm'] = fondo_cm

    # "Elige tú" resuelve preferencias comerciales o estéticas, pero nunca
    # omite datos que afectan cálculo, compatibilidad o seguridad.
    if delega_eleccion:
        preferencias_delegables = (
            'preferencia', 'formato', 'espesor', 'color', 'estilo',
            'terminacion', 'acabado', 'marca', 'modelo', 'diseno',
            'tipo de piso', 'tipo de cubierta', 'tipo de revestimiento',
        )
        patron_datos_criticos = re.compile(
            r'\b(?:medidas?|ancho|largo|fondo|alto|altura|area|estado|base|'
            r'soporte|estructura|pendiente|drenaje|capacidad|peso|voltaje|'
            r'electrica?|electrico|gas)\b'
        )
        datos['datos_faltantes_proyecto'] = [
            faltante
            for faltante in (datos.get('datos_faltantes_proyecto') or [])
            if not (
                any(
                    termino in _texto_normalizado(faltante)
                    for termino in preferencias_delegables
                )
                and not patron_datos_criticos.search(
                    _texto_normalizado(faltante)
                )
            )
        ]
    ultimo_asistente = next((
        _texto_normalizado(item.get('content'))
        for item in reversed(historial)
        if item.get('role') == 'assistant'
    ), '')
    if (
        'estado' in ultimo_asistente
        and ('superficie' in ultimo_asistente or 'muro' in ultimo_asistente)
    ):
        if re.search(r'\b(?:nuevo|nueva|sin pintar)\b', texto_mensaje):
            datos['estado_superficie'] = 'nueva'
        elif re.search(r'\b(?:bueno|buena|buen estado|esta bien)\b', texto_mensaje):
            datos['estado_superficie'] = 'pintada_buen_estado'
        elif re.search(r'\b(?:deteriorado|deteriorada|grietas?|mal estado)\b', texto_mensaje):
            datos['estado_superficie'] = 'deteriorada'
        elif re.search(r'\b(?:humedad|humedo|humeda|manchas?)\b', texto_mensaje):
            datos['estado_superficie'] = 'humedad'
    proyecto_estandar_explicito = bool(re.search(
        r'\b(?:estandar|basico|basica)\b|\b(?:de|como) referencia\b',
        texto_usuario,
    ))
    # Una construcción completa no debe depender de que el cliente conozca la
    # expresión "propuesta estándar". Detectamos solamente obras reconocibles y
    # dejamos fuera instalaciones, cambios y reparaciones puntuales para no
    # convertir una solicitud acotada en una obra completa.
    tipos_proyecto_integral = (
        'bodega', 'quincho', 'pergola', 'invernadero', 'cobertizo',
        'terraza', 'caseta', 'galpon',
    )
    menciona_proyecto_integral = any(
        tipo in texto_usuario for tipo in tipos_proyecto_integral
    )
    accion_construccion = bool(re.search(
        r'\b(?:construir|construccion|levantar|armar|fabricar)\b|'
        r'\bhacer\b.{0,35}\b(?:bodega|quincho|pergola|invernadero|'
        r'cobertizo|terraza|caseta|galpon)\b',
        texto_usuario,
    ))
    alcance_completo = bool(re.search(
        r'\b(?:desde cero|complet[oa]|entero|entera|no hay nada construido|'
        r'part(?:o|ir) de cero)\b',
        texto_usuario,
    ))
    intervencion_acotada = bool(re.search(
        r'\b(?:instalar|reparar|cambiar|reemplazar|arreglar)\b',
        texto_usuario,
    )) and not accion_construccion and not alcance_completo
    datos['_proyecto_integral'] = bool(
        menciona_proyecto_integral
        and (accion_construccion or alcance_completo)
        and not intervencion_acotada
    )
    datos['_proyecto_estandar'] = proyecto_estandar_explicito
    # Gemini puede sugerir una orientacion estandar, pero esa decision cambia
    # el flujo: omite preguntas y aplica supuestos. Solo el texto real del
    # cliente puede autorizarla. Los proyectos integrales conservan sus etapas
    # completas, aunque se presentan como propuesta directa si el usuario no
    # escribio "estandar", "basico" o un equivalente.
    if proyecto_estandar_explicito:
        datos['modo_orientacion'] = 'propuesta_estandar'
    elif datos.get('modo_orientacion') == 'propuesta_estandar':
        datos['modo_orientacion'] = 'propuesta_directa'
    # "No tengo nada" cambia el alcance: se parte desde el terreno o la base,
    # no desde una estructura o radier existente.
    datos['_parte_desde_cero'] = bool(re.search(
        r'\b(?:no tengo nada|part(?:o|ir) de cero|desde cero|no hay nada construido)\b',
        texto_usuario,
    ))
    # Requisitos estructurados que el planificador determinístico debe
    # respetar aunque Gemini omita una etapa en su JSON.
    datos['_requisitos_explicitos'] = {
        'parte_desde_cero': datos['_parte_desde_cero'],
        'iluminacion_interior': bool(re.search(
            r'\b(?:luz|iluminacion|lampara|ampolleta)s?\s+interior(?:es)?\b|'
            r'\binterior\b.{0,20}\b(?:luz|iluminacion|lampara|ampolleta)s?\b',
            texto_usuario,
        )),
        'proyecto_integral': datos['_proyecto_integral'],
    }
    indicadores_excluir_herramientas = (
        'excluir herramientas', 'sin herramientas', 'quitar herramientas',
        'solo materiales', 'sin taladro',
    )
    indicadores_incluir_herramientas = (
        'incluir herramientas', 'herramienta', 'herramientas', 'taladro',
        'cinta metrica', 'wincha', 'con herramientas',
    )

    if any(indicador in texto_mensaje for indicador in indicadores_excluir_herramientas):
        datos['incluir_herramientas'] = False
    elif datos.get('incluir_herramientas'):
        if not any(indicador in texto_usuario for indicador in indicadores_incluir_herramientas):
            datos['incluir_herramientas'] = False
    elif any(indicador in texto_mensaje for indicador in indicadores_incluir_herramientas):
        datos['incluir_herramientas'] = True

    datos['_consulta_solo_herramientas'] = bool(
        re.search(
            r'\b(?:que|cuales|dime|indica).*\bherramientas?\b|'
            r'\bherramientas?\s+se\s+usan\b',
            texto_mensaje,
        )
        and not re.search(
            r'\b(?:material(?:es)?|producto(?:s)?|insumo(?:s)?)\b',
            texto_mensaje,
        )
    )

    contexto_techumbre = f" {_texto_normalizado(datos.get('proyecto'))} {texto_usuario} "
    es_techumbre = any(termino in contexto_techumbre for termino in (
        ' techo ', ' techumbre ', ' cubierta ', ' policarbonato ',
    ))
    es_trabajo_techumbre = es_techumbre and any(accion in contexto_techumbre for accion in (
        'cambiar', 'cambio', 'reemplazar', 'reemplazo', 'instalar',
        'instalacion', 'reparar', 'reparacion', 'renovar', 'renovacion',
        'hacer', 'construir', 'construccion',
    ))
    if es_trabajo_techumbre:
        datos['intencion'] = 'planificar_proyecto'
        if not _texto_normalizado(datos.get('proyecto')):
            datos['proyecto'] = mensaje.strip()[:120] or 'Proyecto de techumbre'

        ancho_cm, largo_cm = _dimensiones_rectangulares_cm(texto_usuario)
        pidio_medidas_antes = any(
            item.get('role') == 'assistant' and any(
                frase in _texto_normalizado(item.get('content'))
                for frase in (
                    'largo y ancho', 'medidas del techo', 'area a cubrir',
                    'indica medidas', 'ancho x largo', 'ancho y largo',
                )
            )
            for item in historial
        )
        if not (ancho_cm and largo_cm) and pidio_medidas_antes:
            medidas_sin_unidad = re.search(
                r'(?<!\w)(\d+(?:[.,]\d+)?)\s*(?:x|por)\s*(\d+(?:[.,]\d+)?)(?!\w)',
                texto_mensaje,
            )
            if medidas_sin_unidad:
                ancho_cm, largo_cm = (
                    round(float(valor.replace(',', '.')) * 100)
                    for valor in medidas_sin_unidad.groups()
                )
        if ancho_cm and largo_cm:
            datos['ancho_cm'] = ancho_cm
            datos['fondo_cm'] = largo_cm

        enlace_material = r'\s+(?:(?:es|esta)\s+)?(?:de\s+)?'
        if re.search(rf'\b(?:estructura|soporte){enlace_material}madera\b', texto_usuario) or (
            'madera' in texto_mensaje
        ):
            datos['material_estructura'] = 'madera'
        elif re.search(rf'\b(?:estructura|soporte){enlace_material}(?:metal|acero|metalica)\b', texto_usuario) or any(
            material in texto_mensaje for material in ('metal', 'acero', 'metalica')
        ):
            datos['material_estructura'] = 'metal'
        elif re.search(rf'\b(?:estructura|soporte){enlace_material}(?:hormigon|concreto)\b', texto_usuario) or any(
            material in texto_mensaje for material in ('hormigon', 'concreto')
        ):
            datos['material_estructura'] = 'hormigon'
        elif datos.get('material_estructura') not in {'madera', 'metal', 'hormigon', 'otra'}:
            datos['material_estructura'] = ''

        estructura_en_buen_estado = bool(re.search(
            r'\bestructura\b.{0,35}\b(?:esta\s+)?en buen estado\b',
            texto_usuario,
        ))
        respuesta_estado_favorable = any(frase in texto_mensaje for frase in (
            'en buen estado', 'esta buena', 'esta bien', 'en buena forma',
            'se puede reutilizar', 'sirve todavia', 'reutilizable',
            'estructura buena', 'estructura firme',
        ))
        respuesta_breve_favorable = bool(re.search(
            r'\b(?:bueno|buena|firme)\b', texto_mensaje,
        )) and not any(frase in texto_mensaje for frase in (
            'no esta bueno', 'no esta buena', 'no esta firme',
        ))
        if estructura_en_buen_estado or respuesta_estado_favorable or respuesta_breve_favorable or any(frase in texto_usuario for frase in (
            'reutilizar la estructura', 'mantener la estructura',
        )):
            datos['estado_estructura'] = 'reutilizable'
        elif re.search(
            r'\bestructura\b.{0,20}\b(?:sera|quedara)\b',
            texto_usuario,
        ) or any(frase in texto_usuario for frase in (
            'construir la estructura', 'estructura nueva', 'nuevo cobertizo',
        )):
            datos['estado_estructura'] = 'nueva'
        elif any(frase in texto_usuario for frase in (
            'reparar la estructura', 'estructura danada', 'estructura deteriorada',
        )):
            datos['estado_estructura'] = 'reparar'
        elif any(frase in texto_usuario for frase in (
            'reemplazar la estructura', 'cambiar la estructura',
        )):
            datos['estado_estructura'] = 'reemplazar'
        elif datos.get('estado_estructura') not in {'nueva', 'reutilizable', 'reparar', 'reemplazar'}:
            datos['estado_estructura'] = ''

        estructura_nueva_explicita = any(frase in texto_usuario for frase in (
            'estructura nueva', 'nueva estructura', 'construir la estructura',
            'hacer la estructura', 'reemplazar la estructura',
        ))
        proyecto_con_soporte_nuevo_explicito = bool(re.search(
            r'\b(?:construir|hacer|armar|levantar)\b.{0,35}'
            r'\b(?:cobertizo|quincho|pergola|estructura|soporte)\b',
            texto_usuario,
        ))
        if (
            datos.get('estado_estructura') == 'nueva'
            and not estructura_nueva_explicita
            and not proyecto_con_soporte_nuevo_explicito
        ):
            # Cambiar la cubierta no significa construir automáticamente una
            # estructura nueva. Se debe confirmar el estado de la existente.
            datos['estado_estructura'] = ''

        autoriza_recomendacion_cubierta = delega_eleccion or any(
            frase in texto_mensaje for frase in (
                'recomiendame tu', 'recomiendamelo tu', 'tu recomiendame',
                'lo demas recomienda',
            )
        )
        cubierta = ''
        if 'policarbonato' in texto_usuario:
            coincidencias_cubierta = list(re.finditer(
                r'policarbonato(?:\s+(alveolar|ondulad[oa]|compact[oa]))?'
                r'(?:\s+(?:de\s+)?(\d+(?:[.,]\d+)?\s*mm))?',
                texto_usuario,
            ))
            # Puede existir una mención antigua sin detalles. Se privilegia la
            # coincidencia más completa y, ante empate, la más reciente.
            detalles = max(
                enumerate(coincidencias_cubierta),
                key=lambda item: (
                    sum(bool(valor) for valor in item[1].groups()),
                    item[0],
                ),
                default=(0, None),
            )[1]
            partes = ['policarbonato']
            if detalles:
                partes.extend(valor for valor in detalles.groups() if valor)
            cubierta = ' '.join(partes)
        elif re.search(r'\btejas?\s+asfaltic[ao]s?\b', texto_usuario):
            cubierta = 'teja asfaltica'
        elif re.search(r'\btejas?\b', texto_usuario):
            cubierta = 'tejas'
        elif re.search(r'\bzinc\b', texto_usuario):
            cubierta = 'zinc'
        if cubierta:
            datos['tipo_cubierta'] = cubierta
            # Una cubierta indicada expresamente por el cliente no puede ser
            # sustituida silenciosamente por otra familia de productos.
            datos['material_principal_proyecto'] = cubierta
        elif not autoriza_recomendacion_cubierta:
            datos['tipo_cubierta'] = ''
            datos['material_principal_proyecto'] = ''

        datos['_autoriza_recomendacion_cubierta'] = autoriza_recomendacion_cubierta
        datos['_consulta_solo_herramientas'] = bool(
            re.search(
                r'\b(?:que|cuales|dime|indica).*\bherramientas?\b|'
                r'\bherramientas?\s+se\s+usan\b',
                texto_mensaje,
            )
            and not re.search(
                r'\b(?:material(?:es)?|producto(?:s)?|insumo(?:s)?)\b',
                texto_mensaje,
            )
        )

    if datos.get('intencion') == 'buscar_producto':
        orden_precio = ''
        if any(frase in texto_mensaje for frase in (
            'mas caro', 'mayor precio', 'precio mas alto',
        )):
            orden_precio = 'precio_desc'
        elif any(frase in texto_mensaje for frase in (
            'mas barato', 'mas economico', 'menor precio', 'precio mas bajo',
        )):
            orden_precio = 'precio_asc'
        consulta_precio = bool(orden_precio) or any(
            frase in texto_mensaje for frase in (
                'cuanto cuesta', 'cuanto cuestan', 'cuanto vale', 'cuanto valen',
                'que valor', 'que precio', 'valor tiene', 'valor tienen',
                'precio tiene', 'precio tienen', 'cuanto sale', 'cuanto salen',
            )
        )
        if consulta_precio:
            datos['consulta_precio'] = True
        if orden_precio:
            datos['orden_producto'] = orden_precio
        if consulta_precio:
            descartadas = {
                'cual', 'cuales', 'dame', 'muestra', 'muestrame', 'quiero',
                'necesito', 'busco', 'producto', 'productos', 'opcion', 'opciones',
                'el', 'la', 'los', 'las', 'un', 'una', 'mas', 'caro', 'cara',
                'caros', 'caras', 'barato', 'barata', 'baratos', 'baratas',
                'economico', 'economica', 'precio', 'precios', 'mayor', 'menor',
                'alto', 'bajo', 'que', 'cuanto', 'cuantos', 'cuanta', 'cuantas',
                'cuesta', 'cuestan', 'vale', 'valen', 'valor', 'valores', 'tiene',
                'tienen', 'sale', 'salen', 'costo', 'costos', 'saber',
            }
            terminos = [
                palabra for palabra in re.findall(r'[a-z0-9-]+', texto_mensaje)
                if len(palabra) >= 3 and palabra not in descartadas
            ]
            if terminos:
                datos['consulta_producto'] = ' '.join(terminos[:8])

    proyecto_normalizado = _texto_normalizado(datos.get('proyecto'))
    terminos_bano = (
        'bano', 'lavamanos', 'vanitorio', 'sanitario', 'inodoro',
        ' wc ', 'ducha', 'regadera',
    )
    es_proyecto_bano = (
        datos.get('intencion') == 'planificar_proyecto'
        and any(
            termino in f' {proyecto_normalizado} {texto_usuario} '
            for termino in terminos_bano
        )
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

    # Para labores manuales de jardín, convertir una búsqueda amplia en
    # herramientas concretas del catálogo. No hay una lista genérica: esta
    # regla sólo se activa cuando la acción descrita es mover o excavar tierra.
    # Para movimiento manual de tierra, una etiqueta amplia como
    # "herramientas manuales" no encuentra productos. Conservamos lo que
    # interpretó Gemini y añadimos términos de catálogo según la acción.
    es_movimiento_tierra = bool(re.search(
        r'\b(?:sacar|retirar|mover|excavar|cavar|remover)\b.{0,42}'
        r'\b(?:tierra|suelo|piedras?|ripio)\b',
        texto_mensaje,
    ))
    if datos.get('_consulta_solo_herramientas') and es_movimiento_tierra:
        datos['herramientas_proyecto'] = list(dict.fromkeys([
            *(datos.get('herramientas_proyecto') or []),
            'pala punta', 'picota', 'carretilla', 'guantes de trabajo',
        ]))
        datos['incluir_herramientas'] = True
    return datos


def _plan_estandar_incompleto(datos):
    """Detecta propuestas estándar abreviadas antes de buscar inventario."""
    if not (
        datos.get('_proyecto_estandar') is True
        or datos.get('_proyecto_integral') is True
    ):
        return False
    tareas = [
        tarea for tarea in (datos.get('tareas_proyecto') or [])
        if isinstance(tarea, dict)
    ]
    busquedas = {
        _texto_normalizado(busqueda)
        for tarea in tareas
        for busqueda in (tarea.get('busquedas') or [])
        if str(busqueda or '').strip()
    }
    proyecto = _texto_normalizado(datos.get('proyecto'))
    es_intervencion_acotada = bool(re.search(
        r'\b(?:instalar|instalacion|reparar|reparacion|cambiar|cambio|reemplazar|reemplazo)\b',
        proyecto,
    )) and not any(expresion in proyecto for expresion in (
        'construccion completa', 'obra completa', 'renovacion completa',
        'remodelacion completa', 'hacer un quincho', 'construir un quincho',
    ))
    # Una instalación puntual no debe inflarse artificialmente hasta parecer
    # una obra completa. Para una construcción sí se conserva el umbral amplio.
    if es_intervencion_acotada:
        return len(tareas) < 1 or len(busquedas) < 2
    return len(tareas) < 5 or len(busquedas) < 12


def _producto_publico(producto):
    return {
        'id': producto.id,
        'sku': producto.sku or '',
        'nombre': producto.nombre,
        'marca': producto.marca,
        'categoria': producto.categoria,
        'precio': producto.precio,
        'stock': producto.stock,
        'unidad_venta': producto.unidad_venta,
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


def _formatear_decimal(valor):
    """Muestra decimales sin notación científica ni ceros innecesarios."""
    numero = Decimal(str(valor))
    texto = format(numero, 'f')
    return texto.rstrip('0').rstrip('.') if '.' in texto else texto


def _etiqueta_unidad_venta(producto, cantidad):
    etiquetas = {
        'unidad': ('unidad', 'unidades'),
        'envase': ('envase', 'envases'),
        'paquete': ('paquete', 'paquetes'),
        'caja': ('caja', 'cajas'),
        'saco': ('saco', 'sacos'),
        'rollo': ('rollo', 'rollos'),
        'juego': ('juego', 'juegos'),
    }
    singular, plural = etiquetas.get(
        producto.unidad_venta,
        (producto.unidad_venta, producto.unidad_venta),
    )
    return singular if cantidad == 1 else plural


def _producto_catalogo(nombre):
    return (
        Producto.objects.filter(activo=True, nombre__icontains=nombre)
        .annotate(
            prioridad_catalogo=Case(
                When(sku__startswith='BAN-', then=Value(0)),
                When(sku__startswith='TEST-', then=Value(2)),
                default=Value(1),
                output_field=IntegerField(),
            )
        )
        .order_by('prioridad_catalogo', 'precio', 'nombre')
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


def _resolver_piso_flotante(datos):
    """Guía y recomienda laminados usando requisitos reales del ambiente."""
    contexto = _texto_normalizado(' '.join(filter(None, (
        datos.get('proyecto'),
        datos.get('_contexto_usuario'),
    ))))
    habitaciones = (
        ('cocina', ('cocina',)),
        ('bano', ('bano', 'baño')),
        ('lavadero', ('lavadero', 'logia', 'logía')),
        ('exterior', ('exterior', 'terraza', 'balcon', 'balcón', 'patio')),
        ('pasillo', ('pasillo', 'hall', 'entrada')),
        ('oficina', ('oficina', 'escritorio', 'home office')),
        ('living_comedor', ('living', 'comedor', 'sala de estar')),
        ('dormitorio', ('dormitorio', 'habitacion', 'habitación', 'pieza')),
    )
    habitacion = next((
        clave for clave, terminos in habitaciones
        if any(_texto_normalizado(termino) in contexto for termino in terminos)
    ), '')

    superficie = Decimal(str(datos.get('superficie') or 0))
    if superficie <= 0:
        ancho = Decimal(str(datos.get('ancho_cm') or 0))
        fondo = Decimal(str(datos.get('fondo_cm') or 0))
        if ancho <= 0 or fondo <= 0:
            ancho_detectado, fondo_detectado = _dimensiones_rectangulares_cm(contexto)
            ancho = Decimal(ancho_detectado)
            fondo = Decimal(fondo_detectado)
        if ancho > 0 and fondo > 0:
            superficie = (ancho * fondo / Decimal('10000')).quantize(Decimal('0.01'))
        else:
            area_explicita = re.search(
                r'(?<![\dx])\b(\d+(?:[.,]\d+)?)\s*(?:m2|m²|metros cuadrados)\b',
                contexto,
            )
            if area_explicita:
                superficie = Decimal(area_explicita.group(1).replace(',', '.'))
    superficie_texto = format(superficie.normalize(), 'f') if superficie > 0 else '0'

    if any(termino in contexto for termino in ('madera', 'osb')):
        base = 'madera u OSB'
    elif 'ceramica' in contexto:
        base = 'cerámica existente'
    elif any(termino in contexto for termino in (
        'hormigon', 'radier', 'losa', 'mortero', 'sobrelosa',
        'gris dura', 'gris y dura',
    )):
        base = 'base cementicia (hormigón, radier o mortero)'
    else:
        base = ''

    if 'alfombra' in contexto and not base:
        detalles = []
        if habitacion:
            detalles.append(f'Habitación: {habitacion.replace("_", " y ")}.')
        if superficie > 0:
            detalles.append(f'Superficie informada: {superficie_texto} m².')
        return {
            'tipo': 'orientacion',
            'mensaje': (
                'Entiendo que actualmente hay alfombra. ' + ' '.join(detalles) + '\n\n'
                'La alfombra es el revestimiento visible; aún no sabemos qué base hay '
                'debajo. Aunque se vea firme o sin humedad, esas observaciones no '
                'confirman el estado de la base oculta.\n\n'
                'Normalmente se retiran la alfombra y su bajoalfombra para revisar '
                'si la base está firme, seca y nivelada antes de instalar la manta '
                'y el piso. Confirma los requisitos del fabricante y, si no puedes '
                'revisarla con seguridad, solicita ayuda de un instalador. Las '
                'cantidades y la compatibilidad quedan pendientes de verificar.'
            ),
            'productos': [], 'maestros': [],
            'sugerencias': ['Qué materiales se usan para piso flotante', 'Buscar maestro de pisos'],
        }

    def condicion_base(campo, patron_positivo, patron_negativo):
        valor = datos.get(campo)
        if valor in ('si', 'no', 'desconocido'):
            return valor == 'si'
        # Compatibilidad con interpretaciones anteriores sin campos estructurados.
        # Una negación explícita prevalece sobre palabras positivas del historial.
        return not re.search(patron_negativo, contexto) and bool(re.search(patron_positivo, contexto))

    base_firme = condicion_base('base_firme', r'\b(?:firme|buen estado|solida)\b',
                                 r'\b(?:no|poco)\s+(?:esta\s+)?firme\b')
    base_seca = condicion_base('base_seca', r'\b(?:seca|seco|sin humedad|libre de humedad)\b',
                               r'\b(?:con humedad|humeda|humedo|no esta seca)\b')
    base_nivelada = condicion_base('base_nivelada', r'\b(?:nivelada|nivelado|sin desnivel)\b',
                                   r'\b(?:no esta nivelad[oa]|no nivelad[oa]|desnivelad[oa])\b')

    faltantes = []
    if not habitacion:
        faltantes.append('Habitación donde se instalará')
    if superficie <= 0:
        faltantes.append('Dimensiones o metros cuadrados del piso')
    if not base:
        faltantes.append('Base o superficie actual')
    estados_faltantes = []
    if not base_firme:
        estados_faltantes.append('firme')
    if not base_seca:
        estados_faltantes.append('seca')
    if not base_nivelada:
        estados_faltantes.append('nivelada')
    if estados_faltantes:
        faltantes.append('Estado de la base: ' + ', '.join(estados_faltantes))

    if faltantes:
        lineas = [
            'PROYECTO',
            'Instalación de piso flotante laminado',
            '',
            'ANTES DE RECOMENDAR PRODUCTOS',
            'Necesito estos datos para elegir una resistencia y una base compatibles:',
        ]
        reconocidos = []
        if habitacion:
            reconocidos.append(f'habitación: {habitacion.replace("_", " y ")}')
        if superficie > 0:
            reconocidos.append(f'superficie: {superficie_texto} m²')
        if base:
            reconocidos.append(f'base: {base}')
        if reconocidos:
            lineas.extend(['', 'DATOS RECONOCIDOS', '• ' + '\n• '.join(reconocidos)])
        if 'Habitación donde se instalará' in faltantes:
            lineas.extend([
                '', 'UBICACIÓN DEL PISO',
                '• Dormitorio: tránsito residencial moderado.',
                '• Living o comedor: uso residencial frecuente.',
                '• Pasillo u oficina: requiere mayor resistencia al desgaste.',
                '• Cocina: solamente laminados con resistencia al agua documentada.',
                '• Baño, logia, lavadero o exterior: un laminado convencional no es adecuado.',
            ])
        if 'Dimensiones o metros cuadrados del piso' in faltantes:
            lineas.extend(['', 'SUPERFICIE', '• Indica largo × ancho en metros o los m² totales.'])
        if 'Base o superficie actual' in faltantes:
            lineas.extend([
                '', 'BASE ACTUAL',
                '• Hormigón, radier, losa o mortero.',
                '• Cerámica existente.',
                '• Madera u OSB.',
                '• Si no la reconoces, describe su color, textura y juntas.',
            ])
        if estados_faltantes:
            lineas.extend([
                '', 'ESTADO DE LA BASE',
                f'• Solo falta confirmar si está {", ".join(estados_faltantes)}.',
                '• Si presenta humedad o desniveles, deben corregirse antes de instalar.',
            ])
        lineas.extend([
            '', 'RESPONDE TODO EN UN MENSAJE',
            'Ejemplo: “Es para un living de 4 × 5 m, sobre radier firme, seco y nivelado. '
            'Prefiero un tono roble natural”.',
        ])
        sugerencias = []
        if not habitacion:
            sugerencias.extend(['Es para un dormitorio', 'Es para el living', 'Es para la cocina'])
        if superficie <= 0:
            sugerencias.append('El piso mide 4 x 5 metros')
        if not base:
            sugerencias.append('La base es un radier de hormigón')
        if estados_faltantes:
            sugerencias.append('La base está ' + ', '.join(estados_faltantes))
        return {
            'tipo': 'aclaracion_proyecto',
            'mensaje': '\n'.join(lineas),
            'productos': [],
            'maestros': [],
            'sugerencias': sugerencias[:4],
        }

    if habitacion in {'bano', 'lavadero', 'exterior'}:
        nombres = {
            'bano': 'baño', 'lavadero': 'logia o lavadero', 'exterior': 'exterior',
        }
        return {
            'tipo': 'proyecto_no_recomendado',
            'mensaje': (
                'PROYECTO\nInstalación de piso flotante laminado\n\n'
                f'No recomiendo un laminado convencional para {nombres[habitacion]}, porque '
                'la exposición frecuente al agua puede dañar su núcleo y sus uniones. '
                'Puedo ayudarte a buscar una alternativa impermeable compatible, como piso SPC '
                'o porcelanato, sin sustituir el material sin tu confirmación.\n\n'
                'Antes de comprar o instalar, consulta con un profesional para revisar humedad, '
                'nivelación y compatibilidad de la base.'
            ),
            'productos': [],
            'maestros': [],
            'sugerencias': ['Buscar piso SPC', 'Buscar porcelanato', 'Cambiar la habitación'],
        }

    candidatos = list(Producto.objects.filter(
        activo=True,
        stock__gt=0,
        sku__startswith='SFI-PFL-',
    ).order_by('precio', 'nombre'))
    compatibles = []
    for producto in candidatos:
        ficha = producto.especificaciones if isinstance(producto.especificaciones, dict) else {}
        if _texto_normalizado(ficha.get('tipo_piso')) != 'laminado':
            continue
        ambientes = [_texto_normalizado(valor) for valor in ficha.get('ambientes_recomendados', [])]
        if habitacion == 'cocina' and not ficha.get('resistencia_agua_horas'):
            continue
        if ambientes and _texto_normalizado(habitacion) not in ambientes:
            continue
        compatibles.append(producto)

    # Presenta una selección variada: económica, tono natural/resistente al agua
    # y una alternativa superior, evitando que cuatro productos casi idénticos
    # aparenten ser una lista que deba comprarse completa.
    candidatos_ordenados = []
    if compatibles:
        candidatos_ordenados.append(compatibles[0])
        candidato_natural = next((
            producto for producto in compatibles
            if isinstance(producto.especificaciones, dict)
            and producto.especificaciones.get('resistencia_agua_horas')
        ), None) or next((
            producto for producto in compatibles
            if 'natural' in _texto_normalizado(producto.color)
        ), None)
        if candidato_natural:
            candidatos_ordenados.append(candidato_natural)
        candidatos_ordenados.extend(reversed(compatibles))
        candidatos_ordenados.extend(compatibles)

    alternativas = []
    colores_usados = set()
    ids_usados = set()
    for producto in candidatos_ordenados:
        if producto.id in ids_usados:
            continue
        color = _texto_normalizado(producto.color)
        if color in colores_usados and len(alternativas) < 3:
            continue
        cantidad = _cantidad_por_cobertura(producto, superficie)
        if not cantidad or producto.stock < cantidad:
            continue
        item = _producto_publico(producto)
        numero_alternativa = len(alternativas) + 1
        cobertura_comprada = Decimal(str(producto.rendimiento)) * cantidad
        unidad_cantidad = _etiqueta_unidad_venta(producto, cantidad)
        item.update({
            'rol': f'Alternativa {numero_alternativa} de piso flotante',
            'cantidad_requerida': cantidad,
            'carrito_cantidad': cantidad,
            'subtotal': cantidad * producto.precio,
            'detalle_material': (
                f'{cantidad} {unidad_cantidad} para {superficie_texto} m², considerando '
                f'{producto.porcentaje_desperdicio:g}% de margen. Cobertura adquirida: '
                f'{_formatear_decimal(cobertura_comprada)} m².'
            ),
            'es_alternativa': True,
            'incluido_en_total': False,
            'etiqueta_cantidad': unidad_cantidad,
        })
        alternativas.append(item)
        colores_usados.add(color)
        ids_usados.add(producto.id)
        if len(alternativas) >= 4:
            break

    if not alternativas:
        return {
            'tipo': 'sin_resultados',
            'mensaje': (
                f'No encontré piso flotante compatible con {habitacion.replace("_", " ")} '
                'y stock suficiente para la superficie indicada. No sustituiré el material '
                'por otro sin tu confirmación.'
            ),
            'productos': [],
            'maestros': [],
            'sugerencias': ['Ver otras terminaciones', 'Buscar maestro instalador'],
        }

    if habitacion == 'living_comedor':
        menciona_living = 'living' in contexto or 'sala de estar' in contexto
        menciona_comedor = 'comedor' in contexto
        habitacion_texto = (
            'living y comedor' if menciona_living and menciona_comedor
            else 'comedor' if menciona_comedor
            else 'living'
        )
    else:
        habitacion_texto = habitacion.replace('_', ' ')

    complementos = []
    subtotal_complementos = 0
    productos_complementarios = (
        ('TEST-PIS-MAN-15', 'Manta de apoyo estimada', True),
        ('SFI-PFL-VAP-AQUA-40', 'Barrera de vapor estimada para base cementicia', True),
    )
    for sku, rol, calcular in productos_complementarios:
        producto = Producto.objects.filter(sku=sku, activo=True, stock__gt=0).first()
        cantidad = _cantidad_por_cobertura(producto, superficie) if calcular else 0
        if not producto or not cantidad or producto.stock < cantidad:
            continue
        item = _producto_publico(producto)
        cobertura_comprada = Decimal(str(producto.rendimiento)) * cantidad
        unidad_cantidad = _etiqueta_unidad_venta(producto, cantidad)
        item.update({
            'rol': rol,
            'cantidad_requerida': cantidad,
            'carrito_cantidad': cantidad,
            'subtotal': cantidad * producto.precio,
            'detalle_material': (
                f'{cantidad} {unidad_cantidad} para {superficie_texto} m². Cobertura adquirida: '
                f'{_formatear_decimal(cobertura_comprada)} m². '
                'Confirmar compatibilidad con el piso elegido.'
            ),
            'es_opcional': True,
            'incluido_en_total': False,
        })
        complementos.append(item)
        subtotal_complementos += item['subtotal']

    for sku, rol in (
        ('SFI-PFL-PER-T-200', 'Perfil de transición opcional'),
        ('TEST-EXT-PIS-GUA-240', 'Guardapolvo opcional'),
        ('SFI-PFL-KIT-INST', 'Herramientas de instalación opcionales'),
    ):
        producto = Producto.objects.filter(sku=sku, activo=True, stock__gt=0).first()
        if not producto:
            continue
        item = _producto_publico(producto)
        item.update({
            'rol': rol,
            'cantidad_pendiente': True,
            'detalle_material': (
                'La cantidad depende del perímetro, puertas, encuentros y condiciones reales del lugar.'
            ),
            'es_opcional': True,
            'incluido_en_total': False,
        })
        complementos.append(item)
    lineas_opciones = [
        f'• {item["nombre"]}: {_formatear_clp(item["subtotal"])} '
        f'por {item["cantidad_requerida"]} {item["etiqueta_cantidad"]}.'
        for item in alternativas
    ]
    mensaje = (
        'PROPUESTA DE PISO FLOTANTE PARA TU ESPACIO\n'
        f'Para {superficie_texto} m² de {habitacion_texto}, sobre {base} firme, seca y nivelada, '
        'encontré estas alternativas reales. Cada alternativa reemplaza a las demás; '
        'no deben sumarse entre sí.\n\n'
        'ALTERNATIVAS DISPONIBLES\n' + '\n'.join(lineas_opciones) + '\n\n'
        'COMPLEMENTOS DE INSTALACIÓN\n'
        + (
            f'La manta y la barrera de vapor suman {_formatear_clp(subtotal_complementos)} '
            'como estimación separada. No se agregan al valor de cada piso hasta confirmar '
            'su compatibilidad. Perfiles, guardapolvos y herramientas requieren medidas adicionales.\n\n'
            if complementos else
            'Deben confirmarse manta, barrera de vapor, perfiles, guardapolvos y herramientas '
            'según la alternativa escogida y las condiciones del lugar.\n\n'
        )
        + 'ANTES DE INSTALAR\n'
        '• La manta y la barrera de vapor deben elegirse según la base y la ficha del piso.\n'
        '• Deben respetarse las juntas perimetrales y condiciones de humedad del fabricante.\n'
        '• Los perfiles de transición y guardapolvos dependen del perímetro y de los encuentros.\n\n'
        'IMPORTANTE\n'
        'Esta propuesta no es un presupuesto definitivo ni reemplaza instrucciones de instalación. '
        'Es una estimación orientativa basada en el catálogo actual. Antes de comprar o instalar, '
        'comprueba medidas, humedad, nivelación, compatibilidad y condiciones reales con un '
        'profesional calificado.'
    )
    return {
        'tipo': 'propuesta_piso_flotante',
        'mensaje': mensaje,
        'productos': alternativas + complementos,
        'maestros': [],
        'sugerencias': [
            '¿Cuál es el más económico?',
            'Comparar resistencia y colores',
            '¿Qué herramientas necesito?',
        ],
    }


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
            ' No pude completar toda la propuesta porque falta disponibilidad de: '
            f'{"; ".join(faltantes_catalogo)}.'
        )
    else:
        mensaje_stock = ''

    mensaje_presupuesto = ''
    if presupuesto:
        if presupuesto >= subtotal and not faltantes_catalogo:
            mensaje_presupuesto += (
                f' Tu presupuesto de {_formatear_clp(presupuesto)} alcanza y quedarían '
                f'{_formatear_clp(presupuesto - subtotal)}.'
            )
        elif subtotal > presupuesto:
            mensaje_presupuesto += (
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
            f'Para {alcance_display} encontré estas opciones en nuestro catálogo, '
            f'con un presupuesto estimado de {_formatear_clp(subtotal)}.'
            f'{mensaje_stock}{mensaje_presupuesto} '
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


def _respuesta_proyecto_fuera_de_alcance(
    motivo, limite='', profesionales='arquitecto, constructor o especialista competente',
):
    detalle_limite = f' {limite}' if limite else ''
    return {
        'tipo': 'proyecto_fuera_de_alcance',
        'mensaje': (
            'PROYECTO FUERA DEL ALCANCE ORIENTATIVO DE SFI\n\n'
            f'{motivo}{detalle_limite}\n\n'
            'Por su magnitud o riesgo, este trabajo requiere evaluación, diseño y '
            'supervisión profesional. '
            f'Consulta con: {profesionales}. SFI no calculará cantidades ni '
            'generará una compra para la obra completa. Puedes reformular la consulta '
            'para revisar una parte menor y concreta o buscar productos específicos.'
        ),
        'productos': [],
        'maestros': [],
        'sugerencias': [
            'Buscar un profesional para evaluar el proyecto',
            'Calcular solo una parte menor del proyecto',
            'Buscar productos específicos',
        ],
    }


def _evaluar_alcance_proyecto(datos):
    """Detiene obras mayores o dimensiones impropias antes de cotizar.

    Los valores son límites internos del asistente y no sustituyen normas,
    permisos ni evaluación profesional.
    """
    texto_original = ' '.join(filter(None, (
        str(datos.get('proyecto') or ''),
        str(datos.get('_contexto_usuario') or ''),
    )))
    contexto = _texto_normalizado(texto_original)
    es_proyecto_mueble = any(termino in contexto for termino in (
        'mueble', 'closet', 'ropero', 'armario', 'escritorio', 'estante',
        'repisero', 'biblioteca', 'rack', 'zapatero', 'velador', 'cajonera',
        'comoda', 'despensa', 'vanitorio', 'meson',
    ))

    medidas_con_unidad = list(re.finditer(
        r'\b(\d+(?:[.,]\d+)?)\s*(?:x|por|×)\s*'
        r'(\d+(?:[.,]\d+)?)\s*'
        r'(kilometros?|kms?|km|metros?|mts?|m)\b',
        contexto,
    ))
    ultima_medida = medidas_con_unidad[-1] if medidas_con_unidad else None
    unidad_ultima = ultima_medida.group(3) if ultima_medida else ''
    unidad_improbable = unidad_ultima in {'km', 'kms', 'kilometro', 'kilometros'}
    if not ultima_medida:
        unidad_improbable = bool(re.search(
            r'\b\d+(?:[.,]\d+)?\s*(?:kilometros?|kms?|km)\b', contexto,
        ))
    if unidad_improbable:
        correccion_sugerida = (
            f'Quise decir {ultima_medida.group(1)} x '
            f'{ultima_medida.group(2)} metros'
            if ultima_medida else 'Indicar nuevamente las medidas en metros'
        )
        return {
            'tipo': 'confirmar_unidad_proyecto',
            'mensaje': (
                'UNIDAD A CONFIRMAR\n\n'
                'La medida fue indicada en kilómetros y supera el alcance de una obra '
                'menor. ¿Te referías a metros? Confirma las medidas y su unidad antes de '
                'que SFI calcule materiales.'
            ),
            'productos': [],
            'maestros': [],
            'sugerencias': [
                correccion_sugerida,
                'Corregir las medidas del proyecto',
            ],
        }

    es_casa_pequena_no_habitable = bool(re.search(
        r'\b(?:casa|casita)\s+(?:para|de)\s+'
        r'(?:perro|gato|mascota|pajaro|aves?|munecas?)\b',
        contexto,
    ))
    obra_mayor = not es_casa_pequena_no_habitable and any((
        re.search(
            r'\b(?:quiero|necesito|proyecto\s+de)\s+'
            r'(?:(?:hacer|construir)\s+)?(?:una\s+)?(?:casa|vivienda)\b',
            contexto,
        ),
        re.search(
            r'\b(?:construir|construccion|hacer|levantar|fabricar)\b.{0,45}'
            r'\b(?:casa|vivienda|edificio)\b',
            contexto,
        ),
        re.search(r'\b(?:casa|vivienda|edificio)\s+complet[oa]\b', contexto),
        re.search(r'\b(?:segundo|tercer)\s+piso\b', contexto),
        re.search(
            r'\bampliaci(?:on|ones)\b.{0,45}'
            r'\b(?:casa|vivienda|habitacion|dormitorio|cocina|bano)\b',
            contexto,
        ),
        re.search(r'\bampliaci(?:on|ones)\s+habitable', contexto),
        re.search(
            r'\b(?:fundacion|fundaciones|cimientos?)\b.{0,45}'
            r'\b(?:casa|vivienda|edificio)\b',
            contexto,
        ),
        re.search(
            r'\b(?:demoler|demolicion|modificar|eliminar|abrir)\b.{0,45}'
            r'\b(?:muro|pared)\s+(?:soportante|estructural)\b',
            contexto,
        ),
        re.search(
            r'\b(?:red|instalacion)\s+completa\b.{0,35}'
            r'\b(?:electrica|electricidad|gas)\b',
            contexto,
        ),
        re.search(
            r'\b(?:instalacion|red)\s+(?:electrica|de\s+gas)\s+completa\b',
            contexto,
        ),
        re.search(
            r'\b(?:obra|proyecto|construccion)\s+(?:industrial|comercial)\b',
            contexto,
        ),
    ))
    if obra_mayor:
        if re.search(r'\b(?:electrica|electricidad)\b', contexto):
            profesionales = 'un electricista autorizado y el profesional responsable del proyecto'
        elif re.search(r'\bgas\b', contexto):
            profesionales = 'un instalador de gas autorizado y el profesional responsable del proyecto'
        else:
            profesionales = 'un arquitecto, un ingeniero estructural y un constructor competente'
        return _respuesta_proyecto_fuera_de_alcance(
            'La solicitud corresponde a una obra mayor o estructural.',
            profesionales=profesionales,
        )

    try:
        ancho_cm = max(0, int(datos.get('ancho_cm') or 0))
        fondo_cm = max(0, int(datos.get('fondo_cm') or 0))
        alto_cm = max(0, int(datos.get('alto_cm') or 0))
        superficie = max(0, float(datos.get('superficie') or 0))
        superficie_muros = max(0, float(datos.get('superficie_muros') or 0))
    except (TypeError, ValueError):
        return None

    superficie_planta = (
        (ancho_cm * fondo_cm) / 10000 if ancho_cm and fondo_cm else 0
    )
    superficie_principal = max(superficie, superficie_planta)
    es_lineal = any(termino in contexto for termino in (
        'cerco', 'cierre perimetral', 'reja', 'muro perimetral',
    ))
    lado_mayor = max(ancho_cm, fondo_cm) / 100

    # Un mueble se dimensiona por frente, altura y profundidad, no como una
    # obra que ocupa esa superficie de terreno. Aplicarle los topes de una
    # techumbre o una vivienda bloqueaba clósets murales grandes pero viables.
    if es_proyecto_mueble:
        dimension_mayor = max(ancho_cm, fondo_cm, alto_cm) / 100
        superficie_frontal = (
            (ancho_cm * alto_cm) / 10000
            if ancho_cm and alto_cm else superficie_principal
        )
        if dimension_mayor > 15 or alto_cm > 600 or superficie_frontal > 60:
            return _respuesta_proyecto_fuera_de_alcance(
                'Las dimensiones superan el alcance orientativo para mobiliario a medida.',
                'SFI admite como referencia muebles de hasta 15 m de desarrollo, '
                '6 m de altura y 60 m² de frente.',
                'un carpintero o fabricante de mobiliario y, si corresponde, un '
                'profesional que verifique anclajes y soporte',
            )
        return None

    if alto_cm > 400:
        return _respuesta_proyecto_fuera_de_alcance(
            'La altura indicada supera el límite absoluto de seguridad de SFI.',
            'Las estructuras de más de 4 m requieren evaluación profesional.',
        )
    if alto_cm > 350:
        return _respuesta_proyecto_fuera_de_alcance(
            'La estructura supera el alcance orientativo por altura.',
            'SFI limita estas propuestas a 3,5 m.',
        )
    if es_lineal:
        if lado_mayor > 60:
            return _respuesta_proyecto_fuera_de_alcance(
                'El trabajo lineal supera el alcance orientativo.',
                'El límite para cercos y trabajos lineales es 60 m.',
            )
    elif lado_mayor > 30:
        return _respuesta_proyecto_fuera_de_alcance(
            'Uno de los lados supera el límite absoluto de una obra menor.',
            'SFI admite lados de hasta 30 m.',
        )

    if max(superficie_principal, superficie_muros) > 200:
        return _respuesta_proyecto_fuera_de_alcance(
            'La superficie supera el límite absoluto de una obra menor.',
            'SFI no calcula proyectos sobre 200 m².',
        )

    limites = (
        (('radier', 'piso', 'terraza'), 60, superficie_principal,
         'radieres, pisos y terrazas', 'un constructor y el especialista del revestimiento o radier'),
        (('cobertizo', 'quincho', 'pergola', 'bodega'), 50,
         superficie_principal, 'cobertizos, quinchos, pérgolas y bodegas',
         'un arquitecto o constructor y un especialista estructural'),
        (('techo', 'techumbre', 'cubierta'), 80, superficie_principal,
         'techumbres y cubiertas', 'un especialista en techumbre y un profesional estructural'),
        (('revestimiento de muro', 'revestir muro', 'muros'), 150,
         superficie_muros or superficie_principal, 'revestimientos de muros',
         'un constructor y un especialista en revestimientos'),
    )
    for terminos, maximo, medida, etiqueta, profesionales in limites:
        if medida > maximo and any(termino in contexto for termino in terminos):
            return _respuesta_proyecto_fuera_de_alcance(
                f'La superficie indicada supera el alcance orientativo para {etiqueta}.',
                f'El límite interno de SFI es {maximo} m².',
                profesionales,
            )

    if superficie_principal > 80:
        return _respuesta_proyecto_fuera_de_alcance(
            'La superficie indicada supera el alcance de un proyecto general menor.',
            'Para proyectos no clasificados, SFI admite hasta 80 m².',
        )
    return None


def _resolver_proyecto(datos):
    alcance = _evaluar_alcance_proyecto(datos)
    if alcance:
        return alcance
    proyecto = _texto_normalizado(datos.get('proyecto'))
    contexto_proyecto = _texto_normalizado(' '.join(filter(None, (
        datos.get('proyecto'),
        datos.get('_contexto_usuario'),
    ))))
    if any(termino in contexto_proyecto for termino in (
        'piso flotante', 'piso laminado', 'fotolaminado',
    )):
        return _resolver_piso_flotante(datos)
    # Un revestimiento de piso conserva el flujo estándar de proyectos aunque
    # esté ubicado en un baño. El planificador sanitario queda reservado para
    # remodelaciones integrales y artefactos; así no cambia silenciosamente una
    # cerámica por porcelanato ni omite la revisión de la base.
    solicitud_solo_piso = (
        datos.get('alcance_bano') == 'piso'
        or (
            'piso' in proyecto
            and datos.get('alcance_bano') not in {'piso_muros', 'completo'}
        )
    )
    es_piso_revestimiento = (
        solicitud_solo_piso
        and not any(termino in contexto_proyecto for termino in (
            'piso de hormigon', 'piso hormigon', 'radier',
        ))
    )
    material_piso_informado = any(
        termino in contexto_proyecto
        for termino in (
            'ceramica', 'porcelanato', 'piso vinilico', 'vinilico spc',
            'piso flotante', 'piso laminado',
        )
    )
    if es_piso_revestimiento and not material_piso_informado:
        return {
            'tipo': 'aclaracion_proyecto',
            'mensaje': (
                'PROYECTO\nRevestimiento de piso\n\n'
                'ANTES DE RECOMENDAR PRODUCTOS\n'
                'Indica qué tipo de piso quieres instalar. Si no lo sabes, '
                'cuéntame en qué habitación se usará y si estará expuesto '
                'a humedad para orientarte sin asumir un material.'
            ),
            'productos': [],
            'maestros': [],
            'sugerencias': [
                'Quiero piso de cerámica',
                'Quiero piso de porcelanato',
                'No lo sé; es para una zona húmeda',
            ],
        }
    if es_piso_revestimiento and material_piso_informado:
        return resolver_proyecto_generico(
            datos,
            buscar_productos=lambda consulta: _buscar_productos(consulta, limite=60),
            producto_publico=_producto_publico,
            buscar_maestros=buscar_maestros,
            resolver_especialidad=_especialidad_desde_texto,
        )
    # Techumbre posee plantillas deterministas por material. Debe resolverse
    # antes del plan generico para que una solicitud "estandar" no permita que
    # Gemini omita la cubierta principal o mezcle fijaciones incompatibles.
    if any(termino in f' {proyecto} ' for termino in (
        'techo', 'techumbre', 'cubierta', 'policarbonato',
    )):
        return resolver_proyecto_techumbre(
            datos,
            buscar_productos=lambda consulta: _buscar_productos(consulta, limite=60),
            producto_publico=_producto_publico,
            buscar_maestros=buscar_maestros,
            resolver_especialidad=_especialidad_desde_texto,
        )
    if (
        datos.get('_proyecto_estandar') is True
        or datos.get('_proyecto_integral') is True
    ):
        return resolver_proyecto_generico(
            datos,
            buscar_productos=lambda consulta: _buscar_productos(consulta, limite=60),
            producto_publico=_producto_publico,
            buscar_maestros=buscar_maestros,
            resolver_especialidad=_especialidad_desde_texto,
        )
    if 'repisa' in proyecto or 'estante' in proyecto:
        return _resolver_repisa(datos)
    if any(termino in f' {proyecto} ' for termino in (
        'bano', 'sanitario', 'inodoro', ' wc ', 'lavamanos',
        'vanitorio', 'ducha', 'regadera',
    )):
        return _resolver_bano(datos)
    return resolver_proyecto_generico(
        datos,
        buscar_productos=lambda consulta: _buscar_productos(consulta, limite=60),
        producto_publico=_producto_publico,
        buscar_maestros=buscar_maestros,
        resolver_especialidad=_especialidad_desde_texto,
    )


COLORES_BUSQUEDA = {
    'blanco': ('blanco', 'blanca', 'white'),
    'negro': ('negro', 'negra', 'black'),
    'gris': ('gris', 'gray', 'grey'),
    'azul': ('azul', 'blue'),
    'rojo': ('rojo', 'roja', 'red'),
    'verde': ('verde', 'green'),
    'amarillo': ('amarillo', 'amarilla', 'yellow'),
    'beige': ('beige',),
    'cafe': ('cafe', 'marron', 'brown'),
    'naranjo': ('naranjo', 'naranja', 'orange'),
    'transparente': ('transparente', 'incoloro', 'clear'),
}

FAMILIAS_ESTRICTAS_BUSQUEDA = {
    'sanitario': ('sanitario', 'inodoro', 'excusado', 'wc'),
    'piscina': ('piscina', 'estanque'),
    'mazo': ('mazo',),
    'combo': ('combo',),
    'maceta': ('maceta',),
    'atornillador': ('atornillador',),
    'destornillador': ('destornillador',),
    'broca': ('broca',),
    'serrucho': ('serrucho',),
    'disco': ('disco',),
    'tina': ('tina',),
    'perno': ('perno', 'bulon'),
    'latex': ('latex',),
    'oleo': ('oleo',),
    # Cuando se pregunta por el material, la cubierta es prioritaria frente a
    # sus perfiles, sellos, tornillos o elementos de protección.
    'policarbonato': ('policarbonato',),
}

ACCESORIOS_POR_FAMILIA = {
    # Al pedir un sanitario/inodoro se debe priorizar el artefacto. Estos
    # productos siguen siendo resultados válidos, pero no deben desplazarlo.
    'sanitario': (
        'tubo', 'codo', 'tee', 'sifon', 'adhesivo', 'valvula', 'flexible',
        'conexion', 'fitting', 'manguito', 'reduccion', 'cemento',
    ),
    'policarbonato': (
        'perfil', 'sellador', 'silicona', 'tornillo', 'golilla', 'lente',
        'visor', 'cinta', 'remate',
    ),
}


def _filtros_explicitos_busqueda(consulta):
    texto = f' {_texto_normalizado(consulta)} '
    color_solicitado = ''
    alias_color = ()
    for color, alias in COLORES_BUSQUEDA.items():
        if any(re.search(rf'\b{re.escape(item)}s?\b', texto) for item in alias):
            color_solicitado = color
            alias_color = alias
            break

    familia_solicitada = ''
    alias_familia = ()
    for familia, alias in FAMILIAS_ESTRICTAS_BUSQUEDA.items():
        if any(re.search(rf'\b{re.escape(item)}s?\b', texto) for item in alias):
            familia_solicitada = familia
            alias_familia = alias
            break
    return color_solicitado, alias_color, familia_solicitada, alias_familia


def _mensaje_busqueda_precisa(consulta, cantidad):
    color, _, familia, _ = _filtros_explicitos_busqueda(consulta)
    if color and any(termino in _texto_normalizado(consulta) for termino in (
        'pintura', 'latex', 'esmalte',
    )):
        sustantivo = 'pintura disponible' if cantidad == 1 else 'pinturas disponibles'
        return f'Encontré {cantidad} {sustantivo} en color {color}.'
    if familia == 'sanitario':
        sustantivo = 'sanitario disponible' if cantidad == 1 else 'sanitarios disponibles'
        return f'Encontré {cantidad} {sustantivo} que coincide con tu búsqueda.'
    if familia == 'piscina':
        sustantivo = 'pintura formulada' if cantidad == 1 else 'pinturas formuladas'
        return f'Encontré {cantidad} {sustantivo} para piscina.'
    return f'Encontré {cantidad} producto(s) relacionados con “{consulta}”.'


def _consulta_pide_adhesivo(consulta):
    texto = _texto_normalizado(consulta)
    return bool(re.search(
        r'\b(?:adhesiv\w*|ashediv\w*|pegament\w*|cola fria|pegar|encolar)\b',
        texto,
    ))


def _es_producto_adhesivo(producto):
    especificaciones = (
        producto.especificaciones
        if isinstance(producto.especificaciones, dict) else {}
    )
    identidad = _texto_normalizado(
        f'{producto.nombre} {producto.categoria} {producto.descripcion}'
    )
    return (
        _texto_normalizado(producto.categoria) == 'adhesivos'
        or bool(especificaciones.get('familia_adhesivo'))
        or bool(re.search(
            r'\b(?:adhesiv\w*|pegament\w*|cola fria|epoxi\w*|poxipol|poxilina)\b',
            identidad,
        ))
    )


def _aclarar_reparacion_mueble_con_adhesivo(mensaje, historial=None):
    """Aclara reparaciones con adhesivo sin limitarse a una pata o un mueble."""
    texto = _texto_normalizado(mensaje)
    historial = historial or []
    # Si la persona pide explorar adhesivos de forma expresa, no la obligamos
    # a describir una reparación. El flujo normal de búsqueda mostrará las
    # alternativas y permitirá pedir orientación después.
    if re.search(
        r'\b(?:solo\s+)?(?:quiero|necesito|muestrame|ver)\s+(?:ver\s+)?'
        r'(?:opciones\s+de\s+|alternativas\s+de\s+)?adhesiv\w*\s+para\s+madera\b',
        texto,
    ):
        return None
    viene_de_aclaracion_adhesivo = any(
        item.get('role') == 'assistant'
        and 'antes de recomendar un adhesivo' in _texto_normalizado(item.get('content'))
        for item in historial[-4:]
        if isinstance(item, dict)
    )
    if not (_consulta_pide_adhesivo(texto) or viene_de_aclaracion_adhesivo):
        return None
    contexto = _texto_normalizado(' '.join(
        str(item.get('content') or '')
        for item in historial[-4:]
        if isinstance(item, dict)
    ))
    contexto_actual = f'{contexto} {texto}'.strip()
    if not viene_de_aclaracion_adhesivo and not re.search(
        r'\b(?:mesa|mueble|silla|estante|repis\w*|velador|puerta|marco|'
        r'cajon\w*|moldura|tabla|tablero|juguete|madera)\b',
        contexto_actual,
    ):
        return None
    if viene_de_aclaracion_adhesivo and not re.search(
        r'\b(?:mesa|mueble|silla|estante|repis\w*|velador|puerta|marco|'
        r'cajon\w*|moldura|tabla|tablero|juguete|madera|pata\w*)\b',
        contexto_actual,
    ):
        return None
    tiene_material = bool(re.search(
        r'\b(?:madera|melamina|mdf|osb|vidrio|cristal|metal|acero|plastico|pvc)\b',
        contexto_actual,
    ))
    tiene_parte = bool(re.search(
        r'\b(?:pata\w*|cubierta|tablero|borde|tapacanto|union|junta|respaldo|'
        r'repisa|puerta|marco|cajon\w*|moldura|tabla|asiento|pelda\w*)\b',
        contexto_actual,
    ))
    tiene_estado_dano = bool(re.search(
        r'\b(?:despeg\w*|solt\w*|floja|flojo|quebrad\w*|rot\w*|fisura\w*|'
        r'grieta\w*|levantad\w*|desgastad\w*|tornill\w*|fijacion\w*)\b',
        texto,
    ))
    if tiene_material and tiene_parte and tiene_estado_dano:
        return None

    faltantes = []
    if not tiene_material:
        faltantes.append('el material de la pieza u objeto')
    if not tiene_parte:
        faltantes.append('qué parte está dañada')
    if not tiene_estado_dano:
        faltantes.append(
            'si esa parte está suelta, despegada, quebrada o tiene las fijaciones dañadas'
        )
    detalle = faltantes[0] if len(faltantes) == 1 else ' y '.join(faltantes)
    return {
        'tipo': 'aclaracion',
        'mensaje': (
            'ANTES DE RECOMENDAR UN ADHESIVO\n\n'
            f'Necesito confirmar {detalle}. El adhesivo y la preparación cambian según '
            'el material, el ambiente y el tipo de daño; una unión despegada, una pieza '
            'quebrada y un tapacanto levantado requieren soluciones diferentes.\n\n'
            'RESPONDE TODO EN UN MENSAJE\n'
            'Ejemplo: “Es una silla de madera de interior y una unión se despegó”.'
        ),
        'productos': [],
        'maestros': [],
        'sugerencias': [
            'Es de madera, se usa en interior y una unión se despegó',
            'Es de melamina y se levantó el tapacanto',
            'Es de vidrio y una pieza se soltó',
            'Solo quiero ver adhesivos para madera',
        ],
    }


def _resolver_seguimiento_reparacion_mueble_adhesivo(mensaje, historial=None):
    """Cierra el cuestionario de adhesivos sin reinterpretarlo como otro proyecto."""
    historial = historial or []
    viene_de_aclaracion = any(
        item.get('role') == 'assistant'
        and 'antes de recomendar un adhesivo' in _texto_normalizado(item.get('content'))
        for item in historial[-6:]
        if isinstance(item, dict)
    )
    if not viene_de_aclaracion:
        return None

    mensajes_usuario = [
        str(item.get('content') or '')
        for item in historial[-8:]
        if isinstance(item, dict) and item.get('role') == 'user'
    ]
    contexto = _texto_normalizado(' '.join([*mensajes_usuario, mensaje]))
    if not (
        re.search(r'\b(?:mesa|mueble|silla|estante|repis\w*|velador)\b', contexto)
        and re.search(r'\bmadera\b', contexto)
        and re.search(r'\bpata\w*\b', contexto)
        and re.search(r'\b(?:despeg\w*|solt\w*|floja|flojo)\b', contexto)
    ):
        return None

    return resolver_interpretacion({
        'intencion': 'planificar_proyecto',
        'proyecto': 'Reparación de pata de mesa de madera suelta o despegada',
        '_proyecto_estandar': True,
        '_contexto_usuario': contexto,
        'tareas_proyecto': [{
            'nombre': 'Alternativas de adhesivo para madera (elige una)',
            'busquedas': [
                'adhesivo cola fría para madera Waltek 250 g',
                'cola fría Afix madera pintable 500 g',
                'SikaBond-232 cola fría profesional para madera 500 g',
            ],
            'usos_materiales': [{
                'busqueda': 'adhesivo cola fría para madera Waltek 250 g',
                'uso': (
                    'Alternativa económica y de formato pequeño para una reparación '
                    'interior de madera limpia y con buen encaje.'
                ),
            }, {
                'busqueda': 'cola fría Afix madera pintable 500 g',
                'uso': (
                    'Alternativa económica de mayor contenido y terminación pintable '
                    'para uniones interiores compatibles.'
                ),
            }, {
                'busqueda': 'SikaBond-232 cola fría profesional para madera 500 g',
                'uso': (
                    'Alternativa profesional de curado rápido para ensambles interiores '
                    'que puedan mantenerse prensados.'
                ),
            }],
        }],
        'datos_faltantes_proyecto': [],
    })


def _buscar_productos(consulta, limite=6):
    texto_portalampara = _texto_normalizado(consulta)
    if (re.search(r'\b(?:portalamparas?|soquetes?)\b', texto_portalampara)
            and re.search(r'\b(?:techo|cielo)\b', texto_portalampara)):
        # Mostrar solo fichas que identifican una base fija/sobrepuesta;
        # un portalámpara colgante no se presenta como equivalente de techo.
        candidatos = []
        for producto in Producto.objects.filter(activo=True, stock__gt=0):
            nombre = _texto_normalizado(producto.nombre)
            if (re.search(r'\b(?:portalampara|soquete)\w*\b', nombre)
                    and re.search(r'\b(?:sobrepuest[oa]|base recta|plafon|cielo|techo)\b', nombre)):
                candidatos.append(producto)
        candidatos.sort(key=lambda producto: (producto.precio, producto.pk))
        return candidatos[:max(1, min(int(limite), 60))]
    palabras_omitidas = {
        'para', 'con', 'una', 'uno', 'unos', 'unas', 'por', 'del', 'las', 'los',
        'que', 'quiero', 'necesito', 'busco', 'producto', 'productos',
        'muestra', 'muestrame', 'muestreme', 'mostrar', 'ver', 'dame',
        'algo', 'como', 'mas', 'caro', 'cara', 'caros', 'caras', 'barato', 'barata',
        'baratos', 'baratas', 'economico', 'economica', 'precio', 'precios',
        'cuanto', 'cuantos', 'cuesta', 'cuestan', 'vale', 'valen', 'valor',
        'valores', 'tiene', 'tienen', 'sale', 'salen', 'costo', 'costos',
        'bajo', 'hasta', 'menos', 'maximo', 'maxima', 'luca', 'lucas',
        'mil', 'pesos', 'clp', 'quiero', 'necesito',
        # Conectores propios de una pregunta por función. Se descartan para
        # que la búsqueda se concentre en la necesidad real: "qué sirve para
        # tapar grietas" debe consultar "tapar grietas", no la palabra sirve.
        'sirve', 'sirven', 'sirva', 'funcion', 'funciona', 'funcionan',
        'uso', 'usar', 'utiliza', 'utilizar', 'puedo', 'podria',
    }
    singulares_busqueda = {
        'pinturas': 'pintura',
        'piscinas': 'piscina',
        'sanitarios': 'sanitario',
        'inodoros': 'inodoro',
        'taladros': 'taladro',
        'sierras': 'sierra',
        'martillos': 'martillo',
    }
    palabras_originales = []
    for palabra in re.findall(r'[\wáéíóúñü-]+', _texto_normalizado(consulta)):
        if len(palabra) < 3 or palabra in palabras_omitidas:
            continue
        palabras_originales.append(singulares_busqueda.get(palabra, palabra))
        if len(palabras_originales) == 8:
            break
    if not palabras_originales:
        return []

    # «Tope» puede indicar un límite de precio o un producto físico. En este
    # último caso es la palabra principal y no debe perderse frente a «puerta».
    es_tope_producto = 'tope' in palabras_originales and not re.search(
        r'\btope\s+(?:de\s+)?\$?\s*\d', _texto_normalizado(consulta),
    )
    es_conector_electrico = (
        any(palabra.startswith(('conector', 'bornera')) for palabra in palabras_originales)
        and any(palabra.startswith(('electric', 'cable', 'conductor'))
                for palabra in palabras_originales)
    )
    solicita_gas = bool(re.search(r'\bgas\b', _texto_normalizado(consulta)))

    # "Corta tubos PVC" es una intención específica: una sierra circular no
    # es una alternativa equivalente para ese material. El catálogo puede
    # llamar al artículo "cortatubo plástico", por lo que priorizamos esa
    # familia antes de ampliar la búsqueda con la palabra genérica "cortar".
    es_corte_tubo_pvc = (
        any(palabra.startswith('cort') for palabra in palabras_originales)
        and any(palabra.startswith('tubo') for palabra in palabras_originales)
        and any(palabra in ('pvc', 'plastico') for palabra in palabras_originales)
    )

    productos_activos = list(Producto.objects.filter(activo=True))
    vocabulario_catalogo = set()
    for producto in productos_activos:
        vocabulario_catalogo.update(re.findall(
            r'[\wáéíóúñü-]+',
            _texto_normalizado(
                f'{producto.nombre} {producto.marca} {producto.modelo} {producto.categoria}'
            ),
        ))

    palabras_corregidas = corregir_terminos(
        palabras_originales, vocabulario_catalogo,
    )
    # Expandir con sinónimos ferreteros después de corregir un error inequívoco.
    palabras_expandidas, sinonimos_agregados = expandir_consulta(palabras_corregidas)
    sinonimos_agregados.update(
        corregida for original, corregida in zip(palabras_originales, palabras_corregidas)
        if original != corregida
    )
    anclas_requeridas = anclas_semanticas(palabras_corregidas)

    consulta_normalizada = _texto_normalizado(consulta)
    medidas_solicitadas = _medidas_desde_texto(consulta)
    (
        color_solicitado,
        alias_color,
        familia_solicitada,
        alias_familia,
    ) = _filtros_explicitos_busqueda(consulta)

    def contiene(texto, palabra):
        # "metro" es una medida coloquial para cinta métrica, pero no debe
        # coincidir con adjetivos como "métrico" en pernos o tornillos.
        if palabra == 'metro':
            return bool(re.search(r'\bmetros?\b', texto))
        return bool(re.search(rf'\b{re.escape(palabra)}\w*', texto))

    resultados = []
    for producto in productos_activos:
        nombre = _texto_normalizado(producto.nombre)
        identificacion = _texto_normalizado(
            ' '.join([producto.sku or '', producto.marca, producto.categoria, producto.color])
        )
        detalle = _texto_normalizado(
            ' '.join([
                producto.descripcion,
                producto.uso_recomendado,
                str(producto.especificaciones or {}),
                producto.ambiente_uso,
                str(producto.superficies_compatibles or []),
                producto.tipo_pintura,
                producto.terminacion,
                str(producto.propiedades_pintura or []),
            ])
        )
        texto_identidad = f'{nombre} {identificacion}'
        texto_filtrado = f'{texto_identidad} {detalle}'
        if solicita_gas and not re.search(r'\bgas\b', nombre):
            continue
        if es_tope_producto and not re.search(r'\btopes?\b', texto_identidad):
            continue
        if es_conector_electrico and not re.search(
            r'\b(?:conector\w*|bornera\w*|terminal\w*|regleta\w*)\b', nombre,
        ):
            continue
        if es_corte_tubo_pvc and 'cortatubo' not in texto_filtrado:
            continue
        if anclas_requeridas and not all(
            re.search(rf'\b{re.escape(ancla)}\w*', texto_identidad)
            for ancla in anclas_requeridas
        ):
            continue
        if medidas_solicitadas and not all(
            _contiene_medida(texto_filtrado, medida)
            for medida in medidas_solicitadas
        ):
            continue
        if color_solicitado and not any(
            contiene(texto_filtrado, alias) for alias in alias_color
        ):
            continue
        texto_familia = texto_filtrado if familia_solicitada == 'piscina' else texto_identidad
        if familia_solicitada and not any(
            contiene(texto_familia, alias) for alias in alias_familia
        ):
            continue
        puntaje = 8 if consulta_normalizada in nombre else 0
        texto_completo = f'{nombre} {identificacion} {detalle}'

        for palabra in palabras_expandidas:
            es_sinonimo = palabra in sinonimos_agregados
            if contiene(nombre, palabra):
                puntaje += 4 if es_sinonimo else 5
            elif contiene(identificacion, palabra):
                puntaje += 2 if es_sinonimo else 3
            elif contiene(detalle, palabra):
                puntaje += 1

        if familia_solicitada:
            accesorios = ACCESORIOS_POR_FAMILIA.get(familia_solicitada, ())
            if any(contiene(nombre, accesorio) for accesorio in accesorios):
                puntaje -= 8

        coincidencias = sum(
            contiene(texto_completo, palabra) for palabra in palabras_expandidas
        )
        # Una consulta compuesta debe conservar su tipo: "kit de ducha" no
        # puede resolverse con cualquier otro kit ni con cualquier producto de baño.
        coincidencias_minimas = min(len(palabras_originales), 3)
        if puntaje and coincidencias >= coincidencias_minimas:
            # Si el catálogo tiene una coincidencia directa por nombre o
            # identidad, no debemos mezclar productos encontrados sólo por
            # una palabra expandida. Ej.: "picota" expande a "jardinera",
            # pero un macetero jardinera no es una picota.
            coincidencia_directa = any(
                contiene(texto_identidad, palabra)
                for palabra in palabras_corregidas
            )
            resultados.append((coincidencias, puntaje, producto, coincidencia_directa))
    if any(item[3] for item in resultados):
        resultados = [item for item in resultados if item[3]]
    resultados.sort(key=lambda item: (
        -item[0], -item[1], item[2].precio, item[2].nombre.casefold(),
    ))
    try:
        limite = max(1, min(int(limite), 60))
    except (TypeError, ValueError):
        limite = 6
    return [item[2] for item in resultados[:limite]]


def _aplicar_contexto_productos(datos, mensaje, productos_contexto):
    ids = list(dict.fromkeys(productos_contexto or []))
    if not ids:
        return datos
    productos = {
        producto.pk: producto
        for producto in Producto.objects.filter(pk__in=ids, activo=True)
    }
    ordenados = [productos[producto_id] for producto_id in ids if producto_id in productos]
    if not ordenados:
        return datos

    texto = _texto_normalizado(mensaje)
    referencia_proyecto = bool(re.search(
        r'\b(?:este|esta|estos|estas|ese|esa|esos|esas|mi|el|la)\s+'
        r'(?:proyecto|trabajo|obra|instalacion|materiales|herramientas)\b',
        texto,
    ))
    if referencia_proyecto:
        return datos
    referencia_contextual = bool(re.search(
        r'\b(?:este|esta|ese|esa|estos|estas|esos|esas|anterior|anteriores|'
        r'similar|similares|parecido|parecida|mismo|misma|primero|primera|'
        r'segundo|segunda|tercero|tercera)\b',
        texto,
    )) or any(frase in texto for frase in (
        'de los que mostraste', 'de esas opciones',
    ))
    comparacion_contextual = any(frase in texto for frase in (
        'mas barato', 'mas economico', 'menor precio',
        'mas caro', 'mayor precio', 'precio mas alto',
    ))
    if not referencia_contextual and not comparacion_contextual:
        return datos

    posicion = None
    for indice, nombres in enumerate((
        ('primero', 'primera'), ('segundo', 'segunda'), ('tercero', 'tercera'),
    )):
        if any(nombre in texto for nombre in nombres):
            posicion = indice
            break
    if posicion is not None and posicion < len(ordenados):
        referencia = ordenados[posicion]
    elif len(ordenados) == 1:
        referencia = ordenados[0]
    else:
        referencia = None

    datos['intencion'] = 'buscar_producto'
    if comparacion_contextual and referencia is None:
        datos['_productos_contexto_ids'] = [producto.pk for producto in ordenados]
        datos['consulta_producto'] = 'productos mostrados anteriormente'
    elif referencia is not None:
        datos['consulta_producto'] = referencia.nombre
        if not any(frase in texto for frase in ('similar', 'similares', 'parecido', 'parecida')):
            datos['_productos_contexto_ids'] = [referencia.pk]
    elif referencia_contextual:
        datos['_contexto_ambiguo'] = True
    return datos


def _continuar_dato_pendiente_proyecto(datos, mensaje, historial):
    """Prioriza una respuesta del proyecto sobre referencias a tarjetas mostradas."""
    ultimo_asistente = next((
        _texto_normalizado(item.get('content'))
        for item in reversed(historial)
        if item.get('role') == 'assistant'
    ), '')
    texto = _texto_normalizado(mensaje)
    pide_estado = (
        'estado' in ultimo_asistente
        and any(frase in ultimo_asistente for frase in (
            'todavia necesito', 'necesito:', 'indica', 'confirmar',
        ))
    )
    responde_estado = any(frase in texto for frase in (
        'buen estado', 'perfecto estado', 'mal estado', 'estado regular',
        'esta bueno', 'esta buena', 'esta bien', 'esta malo', 'esta mala',
        'es nuevo', 'es nueva', 'esta nivelado', 'esta nivelada',
    ))
    if not (pide_estado and responde_estado):
        return False

    faltantes = datos.get('datos_faltantes_proyecto') or []
    datos['datos_faltantes_proyecto'] = [
        item for item in faltantes if 'estado' not in _texto_normalizado(item)
    ]
    if not datos.get('proyecto'):
        proyecto_anterior = re.search(r'analice\s+[“\"]([^”\"]+)', ultimo_asistente)
        if proyecto_anterior:
            datos['proyecto'] = proyecto_anterior.group(1)
    if datos.get('proyecto'):
        datos['intencion'] = 'planificar_proyecto'

    es_piso = any(termino in _texto_normalizado(datos.get('proyecto')) for termino in (
        'piso flotante', 'piso laminado',
    ))
    if es_piso:
        tareas_limpias = []
        for tarea in datos.get('tareas_proyecto') or []:
            if not isinstance(tarea, dict):
                continue
            busquedas = [
                busqueda for busqueda in tarea.get('busquedas', [])
                if 'demolicion' not in _texto_normalizado(busqueda)
            ]
            nombre = _texto_normalizado(tarea.get('nombre'))
            if busquedas and 'demolicion' not in nombre:
                tareas_limpias.append({**tarea, 'busquedas': busquedas})
        datos['tareas_proyecto'] = tareas_limpias
        datos['herramientas_proyecto'] = [
            herramienta for herramienta in datos.get('herramientas_proyecto') or []
            if 'demolicion' not in _texto_normalizado(herramienta)
        ]
    return True


def _mantener_cuestionario_antes_de_recomendar(mensaje, historial):
    """Evita que una petición de recomendación reinicie un proyecto incompleto."""
    ultimo_asistente = next((
        str(item.get('content') or '')
        for item in reversed(historial)
        if item.get('role') == 'assistant'
    ), '')
    if 'ANTES DE RECOMENDAR PRODUCTOS' not in ultimo_asistente:
        return None

    texto = _texto_normalizado(mensaje)
    delega_eleccion = _usuario_delega_eleccion(texto)
    if not delega_eleccion:
        return None

    preguntas = [
        coincidencia.group(1).strip().rstrip('?.')
        for coincidencia in re.finditer(
            r'(?m)^\s*\d+[.)]\s*(.+?)\s*$', ultimo_asistente
        )
    ]
    if not preguntas:
        preguntas = [
            coincidencia.group(1).strip().rstrip('?.')
            for coincidencia in re.finditer(
                r'(?m)^\s*(?:\u2022|\u00e2\u20ac\u00a2|[-*])\s*(.+?)\s*$',
                ultimo_asistente,
            )
        ]
    es_mueble_pendiente = any(
        termino in _texto_normalizado(ultimo_asistente)
        for termino in ('mueble', 'gabinete')
    )
    preferencias_delegables = (
        'tipo de piso', 'estilo', 'terminacion', 'acabado', 'color',
        'formato', 'espesor', 'cubierta', 'policarbonato', 'teja',
    ) + (
        ('material principal deseado', 'material del mueble')
        if es_mueble_pendiente else ()
    )
    responde_medidas = bool(re.search(
        r'\b\d+(?:[.,]\d+)?\s*(?:x|por|×)\s*\d+(?:[.,]\d+)?\b',
        texto,
    ))
    responde_material = bool(re.search(
        r'\b(?:madera|osb|metal|acero|hormigon|concreto|ceramica|ladrillo|'
        r'melamina|mdf|terciado|pino)\b',
        texto,
    ))
    responde_tipo_mueble = bool(re.search(
        r'\b(?:closet|ropero|armario|escritorio|estante|repisero|biblioteca|'
        r'rack|zapatero|velador|cajonera|comoda|despensa|vanitorio)\b|'
        r'\bmueble\s+(?:de\s+)?(?:cocina|bano|lavamanos)\b|'
        r'\b(?:guardar ropa|guardar zapatos|guardar libros|trabajar|estudiar)\b',
        texto,
    ))
    responde_estado = bool(re.search(
        r'\b(?:bueno|buena|firme|reutilizable|regular|malo|mala|danad[oa]|'
        r'deteriorad[oa]|reparar|reemplazar|nuevo|nueva)\b',
        texto,
    ))

    def ya_respondida(pregunta):
        clave = _texto_normalizado(pregunta)
        if (
            responde_tipo_mueble
            and 'tipo' in clave
            and 'mueble' in clave
        ):
            return True
        if responde_medidas and any(
            termino in clave for termino in ('medida', 'ancho', 'largo', 'alto', 'area')
        ):
            return True
        if responde_material and any(
            termino in clave for termino in ('material', 'base', 'soporte', 'estructura')
        ) and 'estado' not in clave:
            return True
        if responde_estado and 'estado' in clave:
            return True
        return False

    pendientes = [
        pregunta for pregunta in preguntas
        if not any(
            preferencia in _texto_normalizado(pregunta)
            for preferencia in preferencias_delegables
        )
        and not ya_respondida(pregunta)
    ]
    if not pendientes:
        return None

    proyecto = ''
    lineas = [linea.strip() for linea in ultimo_asistente.splitlines()]
    if 'PROYECTO' in lineas:
        indice = lineas.index('PROYECTO')
        if indice + 1 < len(lineas):
            proyecto = lineas[indice + 1]

    proyecto_normalizado = _texto_normalizado(proyecto)
    if any(termino in proyecto_normalizado for termino in (
        'techo', 'techumbre', 'cubierta', 'policarbonato',
    )):
        ejemplo = 'Ejemplo: “Mide 3 × 4 m y la estructura es de madera y está firme”.'
        sugerencias = [
            'Mide 3 × 4 m; la estructura es de madera y está firme',
            'La estructura es de metal y está en buen estado',
            'No sé evaluarla; veo la estructura firme y sin daños visibles',
        ]
    elif any(termino in proyecto_normalizado for termino in ('mueble', 'gabinete')):
        ejemplo = (
            'Ejemplo: “Necesito un clóset para ropa; el espacio mide '
            '120 × 200 × 55 cm; elige tú el material”.'
        )
        sugerencias = [
            'Necesito un clóset para ropa; mide 120 × 200 × 55 cm',
            'Quiero un escritorio; mide 120 × 75 × 60 cm',
            'Necesito un estante para libros; elige tú el material',
        ]
    else:
        ejemplo = 'Ejemplo: “La base es de hormigón y está en buen estado”.'
        sugerencias = [
            'La base es de hormigón y está en buen estado',
            'La base es de madera/OSB y está en buen estado',
            'No sé identificar la base; describiré su color, textura y estado',
        ]

    return {
        'tipo': 'aclaracion_proyecto',
        'mensaje': '\n'.join([
            'SIGAMOS CON TU PROYECTO',
            proyecto or 'Proyecto en preparación',
            '',
            'Entendido: yo elegiré la opción más conveniente entre los productos reales de SFI.',
            'Antes necesito estos datos para asegurar compatibilidad:',
            *(f'• {pendiente}' for pendiente in pendientes),
            '',
            'RESPONDE TODO EN UN MENSAJE',
            ejemplo,
        ]),
        'productos': [],
        'maestros': [],
        'sugerencias': sugerencias,
    }


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
        'mensaje': f'{explicacion} Colores disponibles encontrados: {colores}.',
        'productos': recomendaciones,
        'sugerencias': [
            'Quiero calcular cuánta pintura necesito',
            'Mostrar otros colores disponibles',
            'Mostrar otro ambiente',
        ],
    }


def _orientacion_complementos_pintura(datos, calculo):
    """Resume preparación y herramientas reales sin sumarlas al presupuesto."""
    preparaciones = [
        str(item).strip() for item in (calculo.get('preparacion') or [])
        if str(item).strip()
    ]
    advertencia = str(calculo.get('advertencia') or '').strip()

    herramientas_solicitadas = [
        ('rodillo', 'Aplicar pintura uniformemente en superficies amplias.'),
        ('brocha', 'Trabajar bordes, esquinas, encuentros y zonas de detalle.'),
        ('bandeja', 'Cargar y descargar el rodillo de forma controlada.'),
    ]
    tipo_superficie = str(datos.get('tipo_superficie') or '')
    estado = str(datos.get('estado_superficie') or '')
    if estado in {'pintada_buen_estado', 'deteriorada', 'humedad'}:
        if tipo_superficie == 'madera':
            herramientas_solicitadas.append((
                'lija para madera',
                'Suavizar la madera o retirar pintura suelta sin dañar la base.',
            ))
        elif tipo_superficie in {'hormigon', 'ladrillo', 'yeso_carton'}:
            herramientas_solicitadas.append((
                'lija madera y muro',
                'Regularizar reparaciones y retirar material superficial suelto.',
            ))
    if estado in {'deteriorada', 'humedad'} and tipo_superficie in {
        'hormigon', 'ladrillo', 'yeso_carton',
    }:
        herramientas_solicitadas.append((
            'espatula',
            'Retirar material suelto y aplicar reparaciones compatibles.',
        ))

    herramientas = []
    usadas = set()
    base = Producto.objects.filter(activo=True, stock__gt=0)
    for termino, uso in herramientas_solicitadas:
        candidatas = list(base.filter(
            nombre__icontains=termino,
        ).order_by('precio', 'nombre', 'pk')[:6])
        producto = next((
            candidata for candidata in candidatas if candidata.pk not in usadas
        ), None)
        if not producto:
            continue
        usadas.add(producto.pk)
        herramientas.append(f'• {producto.nombre}: {uso}')

    secciones = []
    if preparaciones or advertencia:
        secciones.extend(['PREPARACIÓN SEGÚN LA FICHA'])
        secciones.extend(f'• {preparacion}' for preparacion in preparaciones)
        if advertencia:
            secciones.append(f'• {advertencia}')
    if herramientas:
        if secciones:
            secciones.append('')
        secciones.extend([
            'HERRAMIENTAS OPCIONALES DISPONIBLES EN SFI',
            *herramientas,
            'Estas herramientas no están incluidas en el presupuesto de pintura.',
        ])
    return secciones


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
            'mensaje': (
                f'Para calcularlo con precisión necesito saber {detalle}.'
                '\n\nRESPONDE TODO EN UN MENSAJE\n'
                'Ejemplo de respuesta válida:\n'
                '“Son 20 m², la pared es de madera y está seca y en buen estado”.'
            ),
            'productos': [],
            'sugerencias': [
                'Son 20 m², es madera y está seca y en buen estado',
                'Son 35 m², es hormigón interior y está nuevo',
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
    color_sin_coincidencia = ''
    if (
        not recomendaciones
        and datos.get('color')
        and datos.get('_permitir_color_alternativo')
    ):
        color_sin_coincidencia = str(datos['color']).strip()
        recomendaciones = calcular_recomendaciones_pintura(
            superficie=datos['superficie'],
            ambiente=datos['ambiente'],
            tipo_superficie=datos['tipo_superficie'],
            estado_superficie=datos['estado_superficie'],
            terminacion=datos.get('terminacion') or 'cualquiera',
            color='',
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
            'contenido_litros': calculo['contenido_litros'],
            'litros_comprados': calculo['litros_comprados'],
            'sobrante_estimado': calculo['sobrante_estimado'],
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
    orientacion_complementos = _orientacion_complementos_pintura(datos, mejor)
    mensaje_color = (
        f' No encontré el tono exacto “{color_sin_coincidencia}”; estas opciones son '
        'alternativas compatibles de otros colores.'
        if color_sin_coincidencia else ''
    )
    return {
        'tipo': 'calculo_pintura',
        'mensaje': (
            f'Para {_formatear_decimal(datos["superficie"])} m² necesitas aproximadamente '
            f'{_formatear_decimal(mejor["litros_necesarios"])} litros. Como '
            f'{mejor["nombre"]} se vende en envases de '
            f'{_formatear_decimal(mejor["contenido_litros"])} L, la primera alternativa '
            f'requiere {mejor["cantidad_envases"]} envase(s), equivalentes a '
            f'{_formatear_decimal(mejor["litros_comprados"])} L en total, y tiene un presupuesto de '
            f'{_formatear_clp(mejor["presupuesto_total"])} CLP.'
            f'{mensaje_color}'
            f'{mensaje_presupuesto}'
            + ('\n\n' + '\n'.join(orientacion_complementos)
               if orientacion_complementos else '')
            + ('\n\nLa estimación debe comprobarse con la ficha y las condiciones reales de '
               'la superficie. Si prefieres que un profesional ejecute el trabajo, '
               'puedo buscar opcionalmente un maestro pintor según su disponibilidad.')
        ),
        'productos': productos,
        'sugerencias': [
            '¿Qué herramientas necesito para pintar?',
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
        if datos.get('_preguntar_comuna_maestro'):
            return {
                'tipo': 'aclaracion_maestro',
                'mensaje': 'Perfecto. ¿En qué comuna necesitas el trabajo?',
                'productos': [],
                'maestros': [],
                'sugerencias': ['Maipú', 'Santiago', 'Providencia'],
            }
        return {
            'tipo': 'aclaracion_maestro',
            'mensaje': (
                f'Puedo buscar profesionales de {especialidad}. '
                '¿Prefieres buscar por comuna o ver todos los disponibles?'
            ),
            'productos': [],
            'maestros': [],
            'sugerencias': [
                'Buscar por comuna',
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
    especialidad_normalizada = _texto_normalizado(especialidad)
    nombres_oficio = {
        'gasfiteria': ('gasfíter', 'gasfíteres'),
        'pintura': ('maestro pintor', 'maestros pintores'),
        'ceramica y revestimientos': ('maestro ceramista', 'maestros ceramistas'),
        'electricidad': ('electricista', 'electricistas'),
        'carpinteria': ('carpintero', 'carpinteros'),
    }
    singular, plural = nombres_oficio.get(
        especialidad_normalizada,
        (f'profesional de {especialidad}', f'profesionales de {especialidad}'),
    )
    sustantivo = singular if cantidad == 1 else plural
    alcance = '' if todas_las_comunas else f' en {comuna}'
    return {
        'tipo': 'maestros',
        'mensaje': (
            f'Encontré {cantidad} {sustantivo} '
            f'{"disponibles" if cantidad != 1 else "disponible"}{alcance}. Te dejo '
            f'{"sus perfiles" if cantidad != 1 else "su perfil"} para que puedas revisarlo.'
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
    if intencion == 'orientacion_general' and str(datos.get('consulta_producto') or '').strip():
        # Gemini aporta orientación; la disponibilidad siempre la resuelve Django.
        busqueda = resolver_interpretacion({**datos, 'intencion': 'buscar_producto'})
        orientacion = str(datos.get('respuesta') or '').strip()
        if orientacion:
            busqueda['mensaje'] = orientacion + '\n\n' + busqueda['mensaje']
        return busqueda
    if intencion == 'buscar_maestro':
        return _resolver_busqueda_maestro(datos)
    if intencion == 'recomendar_color':
        return _resolver_recomendacion_color(datos)
    if intencion == 'calcular_pintura':
        return _resolver_calculo(datos)
    if intencion == 'planificar_proyecto':
        return _resolver_proyecto(datos)
    if intencion == 'buscar_producto':
        if datos.get('_contexto_ambiguo'):
            return {
                'tipo': 'aclaracion',
                'mensaje': '¿A cuál de los productos mostrados te refieres? Puedes indicar primero, segundo o tercero.',
                'productos': [],
                'sugerencias': ['El primero', 'El segundo', 'Muéstrame opciones similares'],
            }
        consulta = str(datos.get('consulta_producto') or '').strip()
        ids_contexto = datos.get('_productos_contexto_ids') or []
        partes = re.split(r'\s+y\s+', consulta, flags=re.IGNORECASE)
        herramientas = ('espatula', 'llana', 'brocha', 'rodillo', 'martillo',
                        'taladro', 'sierra', 'alicate', 'destornillador')
        # Solo dividir si Gemini identificó explícitamente una herramienta y
        # otro componente: no separar nombres de kits o productos compuestos.
        if (not ids_contexto and len(partes) == 2
                and any(re.search(rf'\b{herramienta}\w*\b', _texto_normalizado(parte))
                        for parte in partes for herramienta in herramientas)
                and not any(re.search(r'\b(?:kit|juego|set)\b', _texto_normalizado(parte))
                            for parte in partes)):
            resultados, faltantes, ids = [], [], set()
            for parte in partes:
                candidatos = [p for p in _buscar_productos(parte, limite=6) if p.stock > 0]
                if not candidatos:
                    faltantes.append(parte.strip())
                for producto in candidatos:
                    if producto.pk not in ids:
                        ids.add(producto.pk)
                        resultados.append(producto)
            lineas = [
                f'• {p.nombre}: {p.uso_recomendado or p.descripcion or "Uso pendiente de confirmar en la ficha."}'
                for p in resultados
            ]
            texto = ('Encontré estas opciones disponibles en SFI:\n' + '\n'.join(lineas)
                     if lineas else 'No encontré productos disponibles para esta solicitud.')
            if faltantes:
                texto += '\n\nNo encontré una opción con stock para: ' + ', '.join(faltantes) + '.'
            return {
                'tipo': 'productos' if resultados else 'sin_resultados',
                'mensaje': texto,
                'productos': [_producto_publico(p) for p in resultados],
                'maestros': [], 'sugerencias': [],
            }
        if ids_contexto:
            encontrados = {
                producto.pk: producto
                for producto in Producto.objects.filter(pk__in=ids_contexto, activo=True)
            }
            productos = [
                encontrados[producto_id]
                for producto_id in ids_contexto if producto_id in encontrados
            ]
        else:
            productos = _buscar_productos(consulta)
        if not consulta:
            return {
                'tipo': 'aclaracion',
                'mensaje': '¿Qué producto, material, marca o categoría necesitas buscar?',
                'productos': [],
                'sugerencias': ['Busco un taladro', 'Necesito pintura blanca', 'Muéstrame maderas'],
            }
        if not productos:
            color_solicitado, _, familia_solicitada, _ = _filtros_explicitos_busqueda(
                consulta
            )
            orientacion = str(datos.get('respuesta') or '').strip()
            detalle_orientacion = (
                f'\n\nORIENTACIÓN GENERAL\n{orientacion}'
                if len(orientacion) >= 12 else ''
            )
            if color_solicitado and any(
                termino in _texto_normalizado(consulta)
                for termino in ('pintura', 'latex', 'esmalte')
            ):
                mensaje_sin_resultados = (
                    f'No encontré pinturas activas en color {color_solicitado}. '
                    'Puedo mostrarte otros colores disponibles.'
                )
            elif familia_solicitada:
                mensaje_sin_resultados = (
                    f'No encontré {familia_solicitada}s activos que coincidan con tu búsqueda.'
                )
            else:
                mensaje_sin_resultados = (
                    f'No encontré productos activos relacionados con “{consulta}”.'
                )
            return {
                'tipo': 'sin_resultados',
                'mensaje': mensaje_sin_resultados + detalle_orientacion,
                'productos': [],
                'sugerencias': ['Ver pinturas', 'Buscar herramientas', 'Buscar materiales'],
            }
        principales = list(productos)
        complementarios = []
        if _consulta_pide_adhesivo(consulta):
            principales = [producto for producto in productos if _es_producto_adhesivo(producto)]
            complementarios = [producto for producto in productos if producto not in principales]
            if principales:
                productos = [*principales, *complementarios[:2]]

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
                economico = min(productos, key=lambda producto: producto.precio)
                diferencia = economico.precio - presupuesto
                productos = [economico]
                mensaje = (
                    f'Tu presupuesto de {_formatear_clp(presupuesto)} no alcanza para '
                    f'“{consulta}”. La opción más económica cuesta '
                    f'{_formatear_clp(economico.precio)} y faltan '
                    f'{_formatear_clp(diferencia)}.'
                )
        else:
            mensaje = _mensaje_busqueda_precisa(consulta, len(productos))
        orden_producto = datos.get('orden_producto')
        if orden_producto == 'precio_desc' and productos:
            productos = [max(productos, key=lambda producto: producto.precio)]
            mensaje = (
                f'La opción de mayor precio para “{consulta}” es '
                f'{productos[0].nombre} a {_formatear_clp(productos[0].precio)}.'
            )
        elif orden_producto == 'precio_asc' and productos:
            productos = [min(productos, key=lambda producto: producto.precio)]
            mensaje = (
                f'La opción más económica para “{consulta}” es '
                f'{productos[0].nombre} a {_formatear_clp(productos[0].precio)}. '
                'No encontré una alternativa compatible más barata disponible en SFI.'
            )
        elif datos.get('consulta_precio') and productos:
            if len(productos) == 1:
                mensaje = (
                    f'{productos[0].nombre} tiene un valor de '
                    f'{_formatear_clp(productos[0].precio)}.'
                )
            else:
                mensaje = (
                    f'Encontré {len(productos)} opciones para “{consulta}”. '
                    'Estos son sus precios actuales registrados en SFI.'
                )
        productos_publicos = []
        ids_principales = {producto.pk for producto in principales}
        for producto in productos:
            producto_publico = _producto_publico(producto)
            producto_publico['carrito_cantidad'] = 1
            if _consulta_pide_adhesivo(consulta):
                producto_publico['rol'] = (
                    'Resultado principal · adhesivo'
                    if producto.pk in ids_principales
                    else 'También podría servirte · complemento'
                )
            productos_publicos.append(producto_publico)
        if complementarios and principales and not presupuesto:
            mensaje = (
                f'Encontré {len(principales)} adhesivo(s) que responden a “{consulta}”. '
                'Los artículos adicionales aparecen separados como complementos; no son '
                'adhesivos equivalentes y solo corresponden si la reparación los requiere.'
            )
        if productos:
            explicaciones = []
            for producto in productos:
                uso = ' '.join(str(producto.uso_recomendado or producto.descripcion or '').split())
                if not uso:
                    uso = 'La ficha no indica su uso; confirma sus características antes de comprar.'
                explicaciones.append(f'• {producto.nombre}: {uso}')
            mensaje += '\n\nPARA QUÉ SIRVE CADA PRODUCTO\n' + '\n'.join(explicaciones)
        sugerencias_productos = (
            ['¿Para qué sirve?', '¿Cómo se utiliza?', '¿Cuál es el más económico?']
            if len(productos_publicos) == 1
            else ['¿Cuál es el más económico?', 'Comparar las opciones mostradas']
        )
        return {
            'tipo': 'productos',
            'mensaje': mensaje,
            'productos': productos_publicos,
            'sugerencias': sugerencias_productos,
        }
    return {
        'tipo': 'orientacion',
        'mensaje': str(datos.get('respuesta') or 'Cuéntame un poco más sobre tu proyecto.'),
        'productos': [],
        'sugerencias': ['Necesito calcular pintura', 'Busco una herramienta'],
    }


def _texto_normalizado_pregunta_uso(texto):
    """Normaliza errores frecuentes sin alterar el nombre del producto."""
    texto = _texto_normalizado(texto)
    # En consultas escritas rápido es frecuente que el demostrativo, el
    # pronombre y el verbo lleguen unidos: «esamesirve» o «estemesirve».
    # La corrección se limita a esta expresión funcional y no modifica nombres.
    texto = re.sub(
        r'\b(esa|ese|esta|este)me(sirve|sirven|sirbe|sirben)\b',
        lambda coincidencia: (
            f'{coincidencia.group(1)} me '
            f'{"sirven" if coincidencia.group(2) in {"sirven", "sirben"} else "sirve"}'
        ),
        texto,
    )
    correcciones = {
        'pa': 'para',
        'pra': 'para',
        'praa': 'para',
        'q': 'que',
        'qe': 'que',
        'ke': 'que',
        'k': 'que',
        'quue': 'que',
        'sirbe': 'sirve',
        'serbe': 'sirve',
        'sirvee': 'sirve',
        'sirben': 'sirven',
        'sirvenn': 'sirven',
        'funsion': 'funcion',
        'funccion': 'funcion',
        'utilisa': 'utiliza',
        'utlilza': 'utiliza',
        'utilza': 'utiliza',
        'utliza': 'utiliza',
        'utilisan': 'utilizan',
    }
    for origen, destino in correcciones.items():
        texto = re.sub(rf'\b{re.escape(origen)}\b', destino, texto)
    return texto


def _pregunta_uso_producto(texto):
    """Detecta consultas sobre la función de una ficha, no una nueva búsqueda."""
    texto = _texto_normalizado_pregunta_uso(texto)
    return bool(re.search(
        r'\b(?:para que sirve(?:n)?|cual es su funcion|cuales son sus funciones|'
        r'que funcion cumple(?:n)?|para que se usa(?:n)?|para que se utiliza(?:n)?|'
        r'como se usa(?:n)?|como se utiliza(?:n)?|cual es el uso|que uso tiene(?:n)?|para que se ocupa(?:n)?|'
        r'(?:este|esta|ese|esa)?\s*me sirve(?:n)?|me funcionaria(?:n)?|'
        r'que es|que hace(?:n)?)\b',
        texto,
    ))


def _consulta_sin_pregunta_de_uso(mensaje):
    """Obtiene el nombre del producto de una pregunta como «X para qué sirve» ."""
    texto = _texto_normalizado_pregunta_uso(mensaje)
    texto = re.sub(
        r'\b(?:para que sirve(?:n)?|cual es su funcion|cuales son sus funciones|'
        r'que funcion cumple(?:n)?|para que se usa(?:n)?|para que se utiliza(?:n)?|'
        r'como se usa(?:n)?|como se utiliza(?:n)?|cual es el uso|que uso tiene(?:n)?|para que se ocupa(?:n)?|'
        r'(?:este|esta|ese|esa)?\s*me sirve(?:n)?|me funcionaria(?:n)?|'
        r'que es|que hace(?:n)?)\b',
        ' ', texto,
    )
    return ' '.join(texto.split(' ?¿.,;:'))


def _respuesta_pintura_para_contexto(producto, historial):
    """Evalúa una pintura concreta usando el proyecto conservado en el chat."""
    if producto.tipo_calculo != 'pintura':
        return None

    datos = _aplicar_contexto_calculo_pintura(
        {
            'intencion': 'calcular_pintura',
            'superficie': 0,
            'ambiente': '',
            'tipo_superficie': '',
            'estado_superficie': '',
        },
        '',
        historial,
    )
    if not all(datos.get(clave) for clave in (
        'superficie', 'ambiente', 'tipo_superficie', 'estado_superficie',
    )):
        return None

    calculo = calcular_producto_pintura(
        producto,
        superficie=datos['superficie'],
        ambiente=datos['ambiente'],
        tipo_superficie=datos['tipo_superficie'],
        estado_superficie=datos['estado_superficie'],
    )
    if not calculo:
        return {
            'tipo': 'compatibilidad_pintura',
            'mensaje': (
                f'{producto.nombre} no tiene una ficha verificada compatible con '
                f'{_formatear_decimal(datos["superficie"])} m² de '
                f'{datos["tipo_superficie"]} en ambiente {datos["ambiente"]}. '
                'Prefiero no recomendarla para esa superficie sin comprobar antes '
                'la ficha del fabricante.'
            ),
            'productos': [],
            'maestros': [],
            'sugerencias': ['Ver pinturas compatibles', 'Buscar otro color'],
        }

    herramientas = []
    usadas = set()
    for termino_nombre, uso in (
        ('rodillo', 'Aplicar la pintura de manera uniforme en las zonas amplias.'),
        ('brocha', 'Pintar bordes, esquinas y encuentros donde no llega el rodillo.'),
        ('bandeja', 'Cargar y descargar el rodillo de forma controlada.'),
    ):
        candidatas = list(Producto.objects.filter(
            activo=True,
            nombre__icontains=termino_nombre,
        ).exclude(pk__in=usadas).order_by('precio', 'pk')[:8])
        herramienta = next((
            candidata for candidata in candidatas
            if _texto_normalizado(candidata.nombre).startswith(termino_nombre)
        ), candidatas[0] if candidatas else None)
        if herramienta:
            usadas.add(herramienta.pk)
            herramientas.append((herramienta, uso))

    lineas_herramientas = [
        f'• {herramienta.nombre}: {uso}'
        for herramienta, uso in herramientas
    ] or [
        '• Rodillo compatible: para las zonas amplias.',
        '• Brocha compatible: para bordes, esquinas y detalles.',
        '• Bandeja de pintura: para cargar el rodillo de forma uniforme.',
    ]

    producto_publico = _producto_publico(producto)
    producto_publico.update({
        'cantidad_envases': calculo['cantidad_envases'],
        'litros_necesarios': calculo['litros_necesarios'],
        'contenido_litros': calculo['contenido_litros'],
        'litros_comprados': calculo['litros_comprados'],
        'presupuesto_total': calculo['presupuesto_total'],
        'stock_suficiente': calculo['stock_suficiente'],
        'calculo_carrito': {
            'producto': producto.pk,
            'superficie': datos['superficie'],
            'ambiente': datos['ambiente'],
            'tipo_superficie': datos['tipo_superficie'],
            'estado_superficie': datos['estado_superficie'],
            'terminacion': producto.terminacion,
        },
    })
    return {
        'tipo': 'compatibilidad_pintura',
        'mensaje': '\n'.join([
            'SÍ, ES COMPATIBLE CON TU PROYECTO',
            '',
            f'{producto.nombre} está indicada para {datos["tipo_superficie"]} en '
            f'ambiente {datos["ambiente"]}, según su ficha verificada.',
            '',
            'CANTIDAD ESTIMADA',
            f'Para {_formatear_decimal(datos["superficie"])} m² necesitas '
            f'aproximadamente {_formatear_decimal(calculo["litros_necesarios"])} L. '
            f'Debes comprar {calculo["cantidad_envases"]} envase(s) de '
            f'{_formatear_decimal(calculo["contenido_litros"])} L, equivalentes a '
            f'{_formatear_decimal(calculo["litros_comprados"])} L en total.',
            '',
            'HERRAMIENTAS QUE PODRÍAS NECESITAR',
            *lineas_herramientas,
            '',
            'Esta es una estimación. Confirma la preparación, el rendimiento y las '
            'condiciones reales de la superficie antes de comprar o aplicar.',
        ]),
        'productos': [producto_publico],
        'maestros': [],
        'sugerencias': [
            '¿Cómo preparo la superficie?',
            'Ver las herramientas recomendadas',
            'Buscar otra pintura compatible',
        ],
    }


def _producto_mencionado_para_uso(consulta, productos):
    """Selecciona una ficha cuando el cliente escribió un nombre reconocible.

    La búsqueda puede traer accesorios de la misma familia (por ejemplo, tubo y
    tee junto a un gotero). Para una pregunta de uso, el nombre expreso del
    cliente debe prevalecer sobre esos resultados relacionados.
    """
    productos = list(productos or [])
    consulta = _texto_normalizado(consulta).strip()
    if not consulta or not productos:
        return productos

    nombres = {
        producto.pk: _texto_normalizado(producto.nombre).strip()
        for producto in productos
    }
    exactos = [producto for producto in productos if nombres[producto.pk] == consulta]
    if len(exactos) == 1:
        return exactos

    contenidos = [
        producto for producto in productos
        if consulta in nombres[producto.pk] or nombres[producto.pk] in consulta
    ]
    if len(contenidos) == 1:
        return contenidos

    # Para una familia de material (p. ej. "policarbonato"), una consulta de
    # uso debe explicar una cubierta real y no un accesorio asociado. Si hay
    # varias cubiertas válidas, la primera ya viene ordenada por la búsqueda
    # local y se usa como representante de la familia.
    _, _, familia, _ = _filtros_explicitos_busqueda(consulta)
    accesorios = ACCESORIOS_POR_FAMILIA.get(familia, ())
    principales = [
        producto for producto in productos
        if familia and not any(
            re.search(rf'\b{re.escape(accesorio)}\w*', nombres[producto.pk])
            for accesorio in accesorios
        )
    ]
    if principales:
        return principales[:1]

    palabras = set(re.findall(r'[a-z0-9]+', consulta))
    if not palabras:
        return productos
    puntajes = []
    for producto in productos:
        palabras_nombre = set(re.findall(r'[a-z0-9]+', nombres[producto.pk]))
        comunes = len(palabras & palabras_nombre)
        cobertura = comunes / len(palabras)
        puntajes.append((cobertura, comunes, producto))
    puntajes.sort(key=lambda item: (item[0], item[1]), reverse=True)
    if not puntajes:
        return productos
    mejor_cobertura, mejor_comunes, mejor_producto = puntajes[0]
    segundo_comunes = puntajes[1][1] if len(puntajes) > 1 else -1
    if mejor_cobertura >= 0.65 and mejor_comunes > segundo_comunes:
        return [mejor_producto]
    return productos


def _productos_mencionados_en_seguimiento(mensaje, productos):
    """Obtiene uno o varios materiales nombrados sin alterar la propuesta."""
    productos = list(productos or [])
    texto = _texto_normalizado(mensaje)
    if not texto or not productos:
        return []

    posiciones = {
        'primero': 0, 'primera': 0, 'primer': 0,
        'segundo': 1, 'segunda': 1,
        'tercero': 2, 'tercera': 2, 'tercer': 2,
        'cuarto': 3, 'cuarta': 3,
        'quinto': 4, 'quinta': 4,
        'sexto': 5, 'sexta': 5,
        'septimo': 6, 'septima': 6,
        'octavo': 7, 'octava': 7,
        'noveno': 8, 'novena': 8,
        'decimo': 9, 'decima': 9,
    }
    seleccionados = []
    for palabra, indice in posiciones.items():
        if re.search(rf'\b{palabra}\b', texto) and indice < len(productos):
            seleccionados.append(productos[indice])

    # En una conversación real es habitual responder «el 2do», «la 2da
    # tarjeta» o simplemente «la 2». Todas esas variantes deben apuntar a la
    # tarjeta correspondiente, sin iniciar una búsqueda nueva.
    for coincidencia in re.finditer(
        r'\b(?:el|la|producto|tarjeta)?\s*'
        r'(?:n(?:umero|ro)\s*)?'
        r'([1-9][0-9]*)(?:er|ro|ra|do|da|to|ta)?\b',
        texto,
    ):
        indice = int(coincidencia.group(1)) - 1
        if indice < len(productos):
            seleccionados.append(productos[indice])

    # Si el cliente escribió el nombre completo de una o varias fichas, esa
    # referencia es más precisa que las coincidencias parciales de marca o
    # familia (por ejemplo, varias pinturas Sipa Esmalte al Agua).
    nombres_expresos = [
        producto for producto in productos
        if _texto_normalizado(producto.nombre) in texto
    ]
    if nombres_expresos:
        ids_expresos = set()
        return [
            producto for producto in nombres_expresos
            if not (producto.pk in ids_expresos or ids_expresos.add(producto.pk))
        ]

    palabras_genericas = {
        'para', 'madera', 'metal', 'interior', 'exterior', 'producto',
        'material', 'unidad', 'pack', 'caja', 'bolsa', 'saco', 'envase',
        'blanco', 'blanca', 'gris', 'negro', 'negra', 'mm', 'cm', 'kg',
    }
    for producto in productos:
        nombre = _texto_normalizado(producto.nombre)
        especificaciones = (
            producto.especificaciones
            if isinstance(producto.especificaciones, dict) else {}
        )
        identidad = _texto_normalizado(' '.join(filter(None, (
            producto.nombre,
            producto.categoria,
            producto.descripcion,
            producto.uso_recomendado,
            str(especificaciones.get('familia_adhesivo') or ''),
            ' '.join(str(valor) for valor in especificaciones.values()),
        ))))
        if nombre and nombre in texto:
            seleccionados.append(producto)
            continue
        palabras_nombre = {
            palabra for palabra in re.findall(r'[a-z][a-z0-9]+', identidad)
            if len(palabra) >= 4 and palabra not in palabras_genericas
        }
        # Palabras funcionales como adhesivo, sellador, tornillo o lija son
        # suficientemente claras dentro de las tarjetas del proyecto. Si dos
        # productos comparten la misma familia, se explican ambos.
        if any(re.search(rf'\b{re.escape(palabra)}\w*', texto)
               for palabra in palabras_nombre):
            seleccionados.append(producto)

    ids = set()
    return [
        producto for producto in seleccionados
        if not (producto.pk in ids or ids.add(producto.pk))
    ]


def _pregunta_informativa_sobre_materiales(mensaje):
    """Distingue una consulta informativa de una orden para cambiar el plan."""
    texto = _texto_normalizado_pregunta_uso(mensaje)
    if re.search(
        r'\b(?:agrega\w*|anade\w*|incluye\w*|incorpora\w*|quita\w*|'
        r'elimina\w*|cambia\w*|reemplaza\w*|sustituye\w*|modifica\w*|'
        r'ajusta\w*)\b',
        texto,
    ):
        return False
    return bool(
        _pregunta_uso_producto(mensaje)
        or re.search(
            r'\b(?:explica(?:me)?|cuenta(?:me)?|habla(?:me)?)\b.{0,45}'
            r'\b(?:material(?:es)?|producto(?:s)?|adhesivo|sellador|tornillo|'
            r'lija|mortero|pintura|barniz|madera|perfil|plancha)\b|'
            r'\b(?:sirve|sirven|funciona|funcionan|es apto|son aptos|'
            r'es compatible|son compatibles)\b',
            texto,
        )
    )


def _orientacion_de_uso_gemini(producto):
    """Obtiene una explicación pedagógica sin reemplazar la ficha SFI.

    Gemini puede orientar sobre el uso general, pero los atributos verificables
    del producto siempre se muestran desde la base de datos local. Si el modelo
    no está disponible, una pregunta simple sobre un producto no debe fallar.
    """
    datos_verificados = {
        'nombre': producto.nombre,
        'categoria': producto.categoria,
        'descripcion': producto.descripcion,
        'uso_recomendado': producto.uso_recomendado,
        'ambiente_uso': producto.get_ambiente_uso_display(),
        'superficies_compatibles': producto.superficies_compatibles_display,
        'especificaciones': producto.especificaciones or {},
    }
    solicitud = (
        'Explica de manera breve y útil para un cliente el uso general del '
        'siguiente producto. Complementa la ficha, pero no inventes propiedades, '
        'compatibilidades, rendimiento, precios, stock, normas ni instrucciones '
        'de instalación. Si falta un dato, indica que debe verificarse. No '
        'recomiendes productos distintos.\n\n'
        f'FICHA VERIFICADA SFI: {datos_verificados}'
    )
    try:
        respuesta = interpretar_con_gemini(solicitud, [], [producto.pk])
    except GeminiNoDisponible:
        return ''
    orientacion = ' '.join(str((respuesta or {}).get('respuesta') or '').split())
    # Evita agregar salidas vacías o respuestas de clasificación que no ayudan
    # a entender el artículo.
    return orientacion[:520] if len(orientacion) >= 20 else ''


def _respuesta_uso_producto(productos):
    """Forma una respuesta de uso desde fichas reales, sin repetir tarjetas."""
    productos = list(productos or [])
    if len(productos) != 1:
        return None

    producto = productos[0]
    uso = ' '.join(
        str(producto.uso_recomendado or producto.descripcion or '').split()
    )[:360]
    if not uso:
        uso = (
            f'Es un producto de {producto.categoria}. Revisa su ficha técnica y '
            'compatibilidad antes de usarlo.'
        )
    detalle_ficha = [f'• Categoría: {producto.categoria}.']
    if producto.marca:
        detalle_ficha.append(f'• Marca: {producto.marca}.')
    if producto.modelo and _texto_normalizado(producto.modelo) != _texto_normalizado(producto.sku):
        detalle_ficha.append(f'• Modelo: {producto.modelo}.')
    if producto.sku:
        detalle_ficha.append(f'• SKU: {producto.sku}.')
    if producto.presentacion:
        detalle_ficha.append(f'• Presentación: {producto.presentacion}.')

    descripcion = ' '.join(str(producto.descripcion or '').split())[:300]
    if descripcion and descripcion.casefold() != uso.casefold():
        detalle_ficha.append(f'• Descripción: {descripcion}')

    ambiente = producto.get_ambiente_uso_display()
    if producto.ambiente_uso and producto.ambiente_uso != 'no_aplica':
        detalle_ficha.append(f'• Ambiente de uso: {ambiente}.')

    superficies = producto.superficies_compatibles_display
    if superficies:
        detalle_ficha.append(
            f'• Superficies compatibles: {", ".join(superficies)}.'
        )

    preparaciones = producto.preparaciones_recomendadas_display
    if preparaciones:
        detalle_ficha.append(
            f'• Preparación indicada: {"; ".join(preparaciones[:3])}.'
        )

    if producto.rendimiento_legible:
        detalle_ficha.append(f'• Rendimiento: {producto.rendimiento_legible}.')
    if producto.capas_recomendadas:
        detalle_ficha.append(f'• Capas recomendadas: {producto.capas_recomendadas}.')
    if producto.propiedades_pintura_display:
        detalle_ficha.append(
            f'• Propiedades: {", ".join(producto.propiedades_pintura_display)}.'
        )

    especificaciones = producto.especificaciones or {}
    es_adhesivo = (
        _texto_normalizado(producto.categoria) == 'adhesivos'
        or bool(especificaciones.get('familia_adhesivo'))
    )
    detalle_adhesivo = []
    if es_adhesivo and isinstance(especificaciones, dict):
        materiales = especificaciones.get('materiales_compatibles') or []
        if materiales:
            detalle_adhesivo.append(
                '• Materiales compatibles: '
                + ', '.join(str(valor) for valor in materiales)
                + '.'
            )
        no_compatible = especificaciones.get('no_compatible') or []
        if no_compatible:
            detalle_adhesivo.append(
                '• No usar sobre: '
                + ', '.join(str(valor) for valor in no_compatible)
                + '.'
            )
        for clave, etiqueta in (
            ('preparacion', 'Preparación'),
            ('aplicacion_recomendada', 'Aplicación'),
            ('cantidad_orientativa', 'Cantidad orientativa'),
            ('advertencia', 'Advertencia'),
        ):
            valor = especificaciones.get(clave)
            if valor:
                detalle_adhesivo.append(f'• {etiqueta}: {str(valor).rstrip(".")}.')
    datos_tecnicos = []
    claves_internas = {
        'datos tecnicos', 'ficha tecnica', 'uso recomendado',
        'rol en el proyecto', 'rol en proyecto', 'origen del registro',
        'proyectos sugeridos', 'materiales compatibles', 'no compatible',
        'preparacion', 'aplicacion recomendada', 'cantidad orientativa',
        'advertencia', 'fuente tecnica', 'fuente precio',
        'fecha consulta fuente',
    }
    if isinstance(especificaciones, dict):
        for clave, valor in especificaciones.items():
            if valor in (None, '', [], {}):
                continue
            clave_normalizada = _texto_normalizado(clave)
            es_metadato_interno = any(
                termino in clave_normalizada
                for termino in (
                    'fuente', 'imagen', 'image', 'url', 'enlace', 'link',
                )
            )
            if clave_normalizada in claves_internas or es_metadato_interno:
                continue
            valor_normalizado = _texto_normalizado(valor)
            if any(marca in valor_normalizado for marca in (
                'origen del registro', 'rol en el proyecto',
                'proyectos sugeridos',
            )):
                continue
            if isinstance(valor, (list, tuple)):
                valor = ', '.join(str(item) for item in valor)
            valor_limpio = str(valor).strip().rstrip('.')
            datos_tecnicos.append(f'• {clave}: {valor_limpio}.')
            if len(datos_tecnicos) == 6:
                break
    if datos_tecnicos:
        detalle_ficha.extend(datos_tecnicos)
    detalle_ficha.append(
        '• Estado de la ficha: '
        + ('información técnica verificada.' if producto.informacion_tecnica_verificada
           else 'información referencial del catálogo; confirma con el fabricante.')
    )
    orientacion_gemini = _orientacion_de_uso_gemini(producto)
    return {
        'tipo': 'uso_producto',
        'mensaje': '\n'.join([
            'PARA QUÉ SIRVE',
            '',
            producto.nombre,
            '',
            'USO RECOMENDADO',
            uso,
            '',
            'FICHA TÉCNICA',
            *detalle_ficha,
            *(['', 'COMPATIBILIDAD Y APLICACIÓN', *detalle_adhesivo]
              if detalle_adhesivo else []),
            *(['', 'ORIENTACIÓN DEL ASISTENTE', orientacion_gemini]
              if orientacion_gemini else []),
        ]),
        'productos': [],
        'maestros': [],
        'sugerencias': [
            'Qué herramienta necesito para aplicarlo',
            'Cómo preparo la superficie',
            'Ver productos compatibles',
        ],
    }


def _explicar_productos_mostrados(mensaje, historial, productos_contexto):
    """Explica las tarjetas actuales sin reinterpretar ni reconstruir el proyecto."""
    ids = list(dict.fromkeys(productos_contexto or []))
    if not ids:
        return None

    texto = _texto_normalizado(mensaje)
    pide_motivo = any(frase in texto for frase in (
        'por que estos materiales', 'por que esos materiales',
        'por que elegiste', 'por que seleccionaste', 'por que recomiendas',
        'por que este producto', 'por que ese producto',
    )) or bool(re.search(
        r'\bpor que\b.{0,45}\b(?:materiales?|productos?|eleg\w*|'
        r'seleccion\w*|recomiend\w*)\b',
        texto,
    ))
    ultimo_asistente = next((
        _texto_normalizado(item.get('content'))
        for item in reversed(historial)
        if item.get('role') == 'assistant'
    ), '')
    # Si la respuesta anterior pidió escoger una tarjeta para explicar su uso,
    # una posición como «el primero» debe conservar ese propósito. De otro modo
    # el flujo cae en una nueva búsqueda de catálogo y se pierde la explicación.
    responde_aclaracion_uso = any(frase in ultimo_asistente for frase in (
        'puedo explicarte para que sirve cada producto',
        'indica su nombre o su posicion en las tarjetas mostradas',
    ))
    pide_uso = (
        _pregunta_informativa_sobre_materiales(mensaje)
        or responde_aclaracion_uso
    )
    responde_ambiguedad = 'a cual de los productos mostrados' in ultimo_asistente
    if not pide_motivo and not pide_uso and not responde_ambiguedad:
        return None

    encontrados = {
        producto.pk: producto
        for producto in Producto.objects.filter(pk__in=ids, activo=True)
    }
    productos = [encontrados[pk] for pk in ids if pk in encontrados]
    if pide_uso:
        consulta = _consulta_sin_pregunta_de_uso(mensaje)
        mencionados = _productos_mencionados_en_seguimiento(mensaje, productos)
        productos = mencionados or _producto_mencionado_para_uso(consulta, productos)
        # Una consulta con el nombre expreso de una ficha debe poder resolverse
        # aunque el producto haya quedado fuera del contexto visual de un
        # proyecto extenso. La coincidencia exacta evita reinterpretar o
        # reconstruir la propuesta y conserva el proyecto para el seguimiento.
        consulta_normalizada = _texto_normalizado(consulta).strip()
        if not mencionados and len(productos) != 1 and consulta_normalizada:
            candidatos_catalogo = _buscar_productos(consulta, limite=8)
            coincidencia_exacta = [
                producto for producto in candidatos_catalogo
                if _texto_normalizado(producto.nombre).strip() == consulta_normalizada
                or _texto_normalizado(producto.nombre).strip()
                in _texto_normalizado(mensaje)
            ]
            if len(coincidencia_exacta) == 1:
                productos = coincidencia_exacta
        palabras_consulta = set(re.findall(r'[a-z0-9]+', consulta))
        if not mencionados and palabras_consulta and len(productos) > 1:
            coincidencias = [
                producto for producto in productos
                if palabras_consulta & set(re.findall(
                    r'[a-z0-9]+', _texto_normalizado(producto.nombre),
                ))
            ]
            if len(coincidencias) == 1:
                productos = coincidencias
        if len(productos) == 1:
            respuesta_pintura = _respuesta_pintura_para_contexto(
                productos[0], historial,
            )
            if respuesta_pintura:
                return respuesta_pintura
        respuesta_uso = _respuesta_uso_producto(productos)
        if respuesta_uso:
            return respuesta_uso
        if len(productos) > 1 and mencionados:
            lineas = []
            for producto in productos:
                uso = ' '.join(str(
                    producto.uso_recomendado or producto.descripcion or ''
                ).split())[:300]
                if not uso:
                    uso = (
                        f'Cumple una función de {producto.categoria}; revisa su ficha '
                        'y compatibilidad antes de utilizarlo.'
                    )
                lineas.append(f'• {producto.nombre}: {uso}')
            return {
                'tipo': 'explicacion_materiales',
                'mensaje': '\n'.join([
                    'PARA QUÉ SIRVE CADA MATERIAL',
                    'Estos productos ya pertenecen a la propuesta actual; explicarlos '
                    'no modifica cantidades ni vuelve a generar el proyecto.',
                    '',
                    *lineas,
                    '',
                    'Si quieres añadir, quitar o reemplazar alguno, indícalo '
                    'expresamente y actualizaré la propuesta.',
                ]),
                'productos': [],
                'maestros': [],
                'sugerencias': [
                    'Explicar otro material de la propuesta',
                    'Quiero reemplazar un material',
                    'Volver al resumen del proyecto',
                ],
            }
        return {
            'tipo': 'aclaracion_producto',
            'mensaje': (
                'Puedo explicarte para qué sirve cada producto. Indica su nombre '
                'o su posición en las tarjetas mostradas.'
            ),
            'productos': [],
            'maestros': [],
            'sugerencias': ['El primero', 'El segundo', 'Muéstrame las tarjetas'],
        }
    if responde_ambiguedad and not pide_motivo:
        palabras = set(re.findall(r'[a-z0-9]+', texto))
        coincidencias = [
            producto for producto in productos
            if palabras & set(re.findall(r'[a-z0-9]+', _texto_normalizado(producto.nombre)))
        ]
        if coincidencias:
            productos = coincidencias[:1]
        else:
            return None

    lineas = []
    for producto in productos:
        uso = ' '.join(
            str(producto.uso_recomendado or producto.descripcion or '').split()
        )[:220]
        if not uso:
            uso = f'Se incluyó como una opción disponible de {producto.categoria}.'
        lineas.append(f'• {producto.nombre}: {uso}')

    return {
        'tipo': 'explicacion_proyecto',
        'mensaje': '\n'.join([
            'POR QUÉ SE INCLUYERON',
            'Cada producto cumple una función diferente dentro de la propuesta:',
            *lineas,
            '',
            'No son las únicas alternativas. Se priorizaron opciones disponibles en SFI; '
            'puedo comparar otras si prefieres cambiar material, precio o terminación.',
        ]),
        'productos': [],
        'maestros': [],
        'sugerencias': [
            '¿Qué herramientas necesito para este proyecto?',
            'Muéstrame alternativas más económicas',
            'Volver al resumen del proyecto',
        ],
    }


def _explicar_faltantes_del_proyecto(mensaje, historial, productos_contexto):
    """Recupera materiales no disponibles del proyecto sin reinterpretarlo."""
    texto = _texto_normalizado(mensaje)
    pregunta_faltantes = bool(re.search(
        r'\b(?:falta|faltan|faltaria|faltarian)\b.{0,45}'
        r'\b(?:material|materiales|producto|productos|algo|alguno)\b|'
        r'\b(?:que|cual(?:es)?)\b.{0,20}\b(?:materiales?|productos?)\b'
        r'.{0,25}\b(?:falta|faltan|faltaria|faltarian)\b',
        texto,
    ))
    if not pregunta_faltantes or not productos_contexto:
        return None

    ultimo_plan = next((
        str(item.get('content') or '')
        for item in reversed(historial)
        if item.get('role') == 'assistant'
        and (
            'PRODUCTOS POR ETAPA' in str(item.get('content') or '')
            or 'MATERIALES POR ETAPA' in str(item.get('content') or '')
            or 'NO DISPONIBLE EN EL CATÁLOGO' in str(item.get('content') or '')
        )
    ), '')
    marcador = 'NO DISPONIBLE EN EL CATÁLOGO'
    if marcador in ultimo_plan:
        seccion = ultimo_plan.split(marcador, 1)[1].strip()
        for siguiente in ('\n\nIMPORTANTE', '\n\nTOTAL CALCULADO'):
            seccion = seccion.split(siguiente, 1)[0].strip()
        return {
            'tipo': 'explicacion_faltantes_proyecto',
            'mensaje': '\n'.join([
                'MATERIALES NO DISPONIBLES EN SFI',
                seccion,
                '',
                'Estos elementos forman parte de la orientación del proyecto, pero no los '
                'presentaré como productos comprables mientras no estén disponibles.',
            ]),
            'productos': [],
            'maestros': [],
            'sugerencias': [
                'Ver alternativas disponibles',
                'Volver al resumen del proyecto',
            ],
        }

    return {
        'tipo': 'explicacion_faltantes_proyecto',
        'mensaje': (
            'En la propuesta actual no quedó ningún material necesario marcado como no '
            'disponible en SFI. Las cantidades y requisitos estructurales todavía deben '
            'confirmarse con las medidas y condiciones reales del lugar.'
        ),
        'productos': [],
        'maestros': [],
        'sugerencias': ['Volver al resumen del proyecto'],
    }


def _comparar_alternativas_economicas(
    mensaje, productos_contexto, estimacion_contexto=None,
):
    """Compara las tarjetas actuales sin mezclar familias ni reiniciar el proyecto."""
    texto = _texto_normalizado(mensaje)
    pide_alternativa_economica = any(frase in texto for frase in (
        'alternativas mas economicas', 'alternativa mas economica',
        'opciones mas economicas', 'opcion mas economica',
        'algo mas barato', 'uno mas barato', 'una mas barata',
        'hay uno mas barato', 'hay una mas barata',
    )) or bool(re.search(
        r'\b(?:alternativas?|opciones?|productos?)\b.{0,35}\b(?:barat\w*|econom\w*)\b|'
        r'\b(?:barat\w*|econom\w*)\b.{0,35}\b(?:alternativas?|opciones?|productos?)\b',
        texto,
    ))
    if not pide_alternativa_economica:
        return None

    ids = list(dict.fromkeys(productos_contexto or []))
    encontrados = {
        producto.pk: producto
        for producto in Producto.objects.filter(pk__in=ids, activo=True)
    }
    productos = [encontrados[pk] for pk in ids if pk in encontrados]
    if not productos:
        return None

    detalles = {
        int(item['id']): item
        for item in (estimacion_contexto or [])
        if isinstance(item, dict) and item.get('id')
    }
    ids_alternativas = [
        producto.pk for producto in productos
        if detalles.get(producto.pk, {}).get('es_alternativa')
    ]
    if ids_alternativas:
        alternativas_proyecto = [
            producto for producto in productos if producto.pk in ids_alternativas
        ]
        superficie = Decimal('0')
        for producto in alternativas_proyecto:
            detalle_texto = str(detalles.get(producto.pk, {}).get('detalle_material') or '')
            coincidencia_superficie = re.search(
                r'para\s+(\d+(?:[.,]\d+)?)\s*m(?:2|²)',
                _texto_normalizado(detalle_texto),
            )
            if coincidencia_superficie:
                superficie = Decimal(coincidencia_superficie.group(1).replace(',', '.'))
                break

        requiere_agua = bool(alternativas_proyecto) and all(
            isinstance(producto.especificaciones, dict)
            and producto.especificaciones.get('resistencia_agua_horas')
            for producto in alternativas_proyecto
        )
        candidatos_economicos = []
        for producto in Producto.objects.filter(
            activo=True,
            stock__gt=0,
            sku__startswith='SFI-PFL-',
        ).order_by('precio', 'nombre'):
            ficha = producto.especificaciones if isinstance(producto.especificaciones, dict) else {}
            if _texto_normalizado(ficha.get('tipo_piso')) != 'laminado':
                continue
            if requiere_agua and not ficha.get('resistencia_agua_horas'):
                continue
            cantidad = (
                _cantidad_por_cobertura(producto, superficie)
                if superficie > 0 else
                int(detalles.get(producto.pk, {}).get('cantidad_requerida') or 1)
            )
            if not cantidad or producto.stock < cantidad:
                continue
            candidatos_economicos.append({
                'producto': producto,
                'cantidad': cantidad,
                'subtotal': producto.precio * cantidad,
            })

        candidatos_economicos.sort(
            key=lambda opcion: (
                opcion['subtotal'], opcion['producto'].precio, opcion['producto'].nombre,
            )
        )
        opciones_economicas = candidatos_economicos[:3]
        if not opciones_economicas:
            return None

        lineas = []
        items = []
        for numero, opcion in enumerate(opciones_economicas, start=1):
            producto = opcion['producto']
            cantidad = opcion['cantidad']
            unidad = _etiqueta_unidad_venta(producto, cantidad)
            lineas.append(
                f'• {producto.nombre}: {_formatear_clp(opcion["subtotal"])} por '
                f'{cantidad} {unidad} para la superficie calculada.'
            )
            item = _producto_publico(producto)
            cobertura_comprada = Decimal(str(producto.rendimiento)) * cantidad
            item.update({
                'rol': f'Opción económica {numero}',
                'cantidad_requerida': cantidad,
                'carrito_cantidad': cantidad,
                'subtotal': opcion['subtotal'],
                'detalle_material': (
                    f'{cantidad} {unidad} para {_formatear_decimal(superficie)} m². '
                    f'Cobertura adquirida: {_formatear_decimal(cobertura_comprada)} m².'
                ),
                'es_alternativa': True,
                'incluido_en_total': False,
            })
            items.append(item)
        return {
            'tipo': 'comparacion_economica',
            'mensaje': '\n'.join([
                'ALTERNATIVAS ECONÓMICAS PARA TU PROYECTO',
                *lineas,
                '',
                'Las opciones están ordenadas por el subtotal necesario para la superficie '
                'indicada, no solamente por el precio de una caja. Elige solo un revestimiento; '
                'los complementos de instalación quedaron fuera de esta comparación.',
                '',
                'IMPORTANTE',
                'Los valores son una estimación. Antes de comprar, confirma cantidades, '
                'compatibilidad y condiciones de instalación con un profesional calificado.',
            ]),
            'productos': items,
            'maestros': [],
            'sugerencias': [
                '¿Por qué elegiste estos materiales?',
                '¿Qué herramientas necesito para este proyecto?',
                'Comparar resistencia y colores',
                'Volver al resumen del proyecto',
            ],
        }

    # En propuestas extensas se comparan solamente materiales seleccionados,
    # no herramientas, seguridad ni elementos opcionales. Además se conserva
    # como máximo un producto por etapa para evitar decenas de búsquedas
    # redundantes en una sola respuesta rápida.
    productos_comparables = []
    roles_usados = set()
    for producto in productos:
        detalle = detalles.get(producto.pk, {})
        rol = _texto_normalizado(detalle.get('rol') or producto.categoria)
        if (
            detalle.get('es_opcional')
            or detalle.get('incluido_en_total') is False
            or any(termino in rol for termino in (
                'herramienta', 'seguridad', 'proteccion', 'alternativa',
            ))
        ):
            continue
        clave_rol = rol or f'producto-{producto.pk}'
        if clave_rol in roles_usados:
            continue
        productos_comparables.append(producto)
        roles_usados.add(clave_rol)
        if len(productos_comparables) >= 8:
            break
    if not productos_comparables:
        productos_comparables = productos[:8]

    lineas = []
    alternativas = []
    alternativas_usadas = set()
    for producto in productos_comparables:
        candidatos = [
            candidato for candidato in _buscar_productos(producto.nombre, limite=20)
            if candidato.pk != producto.pk
            and candidato.stock > 0
            and candidato.precio < producto.precio
        ]
        alternativa = min(candidatos, key=lambda item: item.precio, default=None)
        if alternativa:
            ahorro = producto.precio - alternativa.precio
            lineas.append(
                f'• {producto.nombre}: {alternativa.nombre} cuesta '
                f'{_formatear_clp(alternativa.precio)} y permite ahorrar '
                f'{_formatear_clp(ahorro)} por unidad.'
            )
            if alternativa.pk not in alternativas_usadas:
                item = _producto_publico(alternativa)
                item['carrito_cantidad'] = 1
                item['rol'] = 'Alternativa más económica'
                item['es_alternativa'] = True
                item['incluido_en_total'] = False
                alternativas.append(item)
                alternativas_usadas.add(alternativa.pk)
        else:
            lineas.append(
                f'• {producto.nombre}: no encontré una alternativa compatible '
                'más barata disponible en SFI.'
            )

    return {
        'tipo': 'comparacion_economica',
        'mensaje': '\n'.join([
            'COMPARACIÓN DE PRECIOS',
            *lineas,
            '',
            'La comparación mantiene el tipo y las medidas identificables del producto; '
            'no sustituye materiales por artículos de otra función.',
        ]),
        'productos': alternativas,
        'maestros': [],
        'sugerencias': [
            '¿Por qué elegiste estos materiales?',
            '¿Qué herramientas necesito para este proyecto?',
            'Volver al resumen del proyecto',
        ],
    }


def _pide_profesional_para_proyecto(mensaje):
    """Reconoce distintas formas naturales de pedir el oficio adecuado."""
    texto = _texto_normalizado(mensaje)
    menciona_profesional = bool(re.search(
        r'\b(?:maestr[oa]s?|profesional(?:es)?|especialistas?|carpinter[oa]s?|'
        r'pintor(?:es|as?)?|gasfiter(?:es)?|electricistas?|ceramistas?)\b',
        texto,
    ))
    pide_alguien = bool(re.search(
        r'\b(?:necesito|busco|quiero|quien)\b.{0,35}\balguien\b',
        texto,
    ))
    refiere_trabajo = bool(re.search(
        r'\b(?:este|esta|el|la|mi)\s+(?:proyecto|trabajo|obra|instalacion)\b|'
        r'\b(?:hacerlo|realizarlo|instalarlo|construirlo)\b',
        texto,
    ))
    solicita_orientacion = bool(re.search(
        r'\b(?:que|cual|quien|necesito|busco|quiero|recomiend\w*|muestrame)\b',
        texto,
    ))
    return (menciona_profesional or pide_alguien) and refiere_trabajo and solicita_orientacion


def _resolver_herramientas_iniciales(mensaje):
    """Responde una solicitud explícita de herramientas sin exigir un plan previo."""
    texto = _texto_normalizado(mensaje)
    if 'herramienta' not in texto or not re.search(
        r'\b(?:que|cuales|dime|indica|muestra(?:me)?|necesito)\b', texto
    ):
        return None
    # Si pide materiales/productos y herramientas, se trata de un proyecto
    # completo y debe conservar todos sus datos en el planificador.
    if re.search(r'\b(?:material(?:es)?|producto(?:s)?|insumo(?:s)?)\b', texto):
        return None
    if any(termino in texto for termino in (
        'sacar tierra', 'retirar tierra', 'mover tierra', 'excavar', 'cavar',
        'hacer hoyo', 'hacer una zanja', 'tierra compactada',
    )):
        consultas = ['pala punta', 'picota jardinera', 'carretilla acero', 'guantes jardineria']
        contexto = 'retirar tierra del patio'
    elif any(termino in texto for termino in (
        'pasta muro', 'pasta de retape', 'retape', 'masilla',
        'pasta para juntas', 'yeso carton', 'yeso-carton',
    )):
        # Preparar o reparar un muro no es lo mismo que pintarlo: se debe
        # aplicar y nivelar la pasta antes de lijar, no usar rodillo o brocha.
        consultas = ['espatula acero', 'lija muro']
        contexto = 'aplicar y alisar pasta muro'
    elif any(termino in texto for termino in ('pintar', 'pintura', 'pared', 'muro')):
        consultas = ['rodillo pintura', 'brocha pintura']
        contexto = 'pintar la pared'
    elif any(termino in texto for termino in ('techo', 'techumbre', 'cubierta')):
        consultas = ['cinta metrica', 'taladro percutor']
        contexto = 'trabajar en la techumbre'
    elif any(termino in texto for termino in ('madera', 'repisa', 'mueble')):
        consultas = ['cinta metrica', 'taladro percutor', 'sierra circular']
        contexto = 'realizar el trabajo en madera'
    else:
        consultas = ['cinta metrica', 'taladro percutor']
        contexto = 'realizar el trabajo'

    herramientas = []
    usadas = set()
    for consulta in consultas:
        termino_principal = _texto_normalizado(consulta).split()[0]
        candidatos_directos = Producto.objects.filter(activo=True).order_by('nombre')
        producto = next((
            candidato for candidato in candidatos_directos
            if candidato.pk not in usadas
            and (
                'herramienta' in _texto_normalizado(candidato.categoria)
                or termino_principal in ('espatula', 'lija')
            )
            and termino_principal in _texto_normalizado(candidato.nombre)
        ), None)
        if not producto:
            producto = next((
                candidato for candidato in _buscar_productos(consulta, limite=10)
                if candidato.pk not in usadas
                and (
                    'herramienta' in _texto_normalizado(candidato.categoria)
                    or termino_principal in ('espatula', 'lija')
                )
            ), None)
        if not producto:
            continue
        item = _producto_publico(producto)
        item.update({
            'rol': 'Herramienta recomendada',
            'carrito_cantidad': 1,
            'es_opcional': True,
        })
        herramientas.append(item)
        usadas.add(producto.pk)
    total = sum((item.get('precio') or 0 for item in herramientas), 0)
    return {
        'tipo': 'seguimiento_herramientas',
        'mensaje': (
            f'HERRAMIENTAS PARA {contexto.upper()}\n'
            + (
                '\n'.join(f"• {item['nombre']}" for item in herramientas)
                if herramientas
                else 'No encontré herramientas relacionadas con stock en SFI.'
            )
            + (
                f'\n\nCOSTO OPCIONAL\n{_formatear_clp(total)} CLP considerando '
                'una unidad de cada herramienta.'
                if herramientas else ''
            )
            + '\n\nSi también necesitas los materiales del proyecto, indícame las medidas '
            'y las condiciones principales del lugar.'
        ),
        'productos': herramientas,
        'maestros': [],
        'sugerencias': ['Calcular los materiales del proyecto', 'Ver opciones más económicas'],
    }


def _resolver_diagnostico_filtracion_inicial(mensaje):
    """Guía una filtración incierta antes de sugerir repuestos incompatibles."""
    texto = _texto_normalizado(mensaje)
    es_lavaplatos = 'lavaplatos' in texto
    hay_filtracion = any(termino in texto for termino in (
        'filtra', 'filtracion', 'fuga', 'gotea', 'agua por debajo',
    ))
    origen_identificado = any(termino in texto for termino in (
        'viene del sifon', 'sale del sifon', 'fuga del sifon',
        'viene del flexible', 'sale del flexible', 'fuga del flexible',
        'viene de la llave', 'sale de la llave', 'fuga de la llave',
        'borde del lavaplatos', 'union del lavaplatos', 'desague esta suelto',
    ))
    if not (es_lavaplatos and hay_filtracion) or origen_identificado:
        return None

    return {
        'tipo': 'seguimiento_proyecto',
        'mensaje': (
            'PRIMERO IDENTIFIQUEMOS LA FILTRACIÓN\n'
            'Cierra la llave de paso y seca completamente la zona. Luego deja correr '
            'un poco de agua mientras observas dónde aparece la primera gota.\n\n'
            'Indícame cuál de estas opciones coincide:\n'
            '• Sifón o tubo de desagüe.\n'
            '• Flexible o conexión de agua.\n'
            '• Llave del lavaplatos.\n'
            '• Borde o unión del lavaplatos con el mueble.\n'
            '• No logro identificarlo; describiré dónde aparece la primera gota.\n\n'
            'Cuando sepamos el origen te mostraré solamente los repuestos y herramientas '
            'compatibles que estén disponibles en SFI.'
        ),
        'productos': [],
        'maestros': [],
        'sugerencias': [
            'La fuga viene del sifón o desagüe',
            'La fuga viene del flexible de agua',
            'No logro identificar la fuga',
        ],
    }


def _resolver_gotera_con_cubierta_identificada(mensaje, historial):
    """Da una primera alternativa útil cuando ya se conoce la cubierta.

    No convierte una reparación localizada en una obra de techumbre ni depende
    de Gemini para reconocer zinc, teja o policarbonato.
    """
    texto = _texto_normalizado(mensaje)
    es_gotera_techo = (
        bool(re.search(r'\b(?:gotera|goteras|filtra(?:cion)?|gotea)\b', texto))
        and any(termino in texto for termino in ('techo', 'techumbre', 'cubierta', 'teja', 'zinc', 'policarbonato'))
    )
    if not es_gotera_techo:
        return None
    cubierta = next((material for material in ('policarbonato', 'zinc', 'teja')
                     if material in texto), None)
    if not cubierta:
        return None

    opciones = {
        'policarbonato': (
            ('sellador neutro compatible con policarbonato', 'Sellar uniones y encuentros de policarbonato'),
            ('cinta butilica impermeable', 'Sellar traslapes compatibles'),
        ),
        'zinc': (
            ('cinta butilica impermeable', 'Sellar traslapes y encuentros de planchas de zinc'),
            ('tapagoteras acrilico impermeabilizante', 'Reparar fisuras o encuentros localizados'),
        ),
        'teja': (
            ('tapagoteras acrilico impermeabilizante', 'Sellar un encuentro localizado sin reemplazar una teja sana'),
            ('sellador poliuretano para exterior', 'Sellar uniones exteriores puntuales compatibles'),
        ),
    }
    productos, usados = [], set()
    for consulta, rol in opciones[cubierta]:
        producto = next((candidato for candidato in _buscar_productos(consulta, limite=8)
                         if candidato.stock > 0 and candidato.pk not in usados), None)
        if producto:
            item = _producto_publico(producto)
            item.update({'rol': rol, 'carrito_cantidad': 1, 'es_opcional': True})
            productos.append(item)
            usados.add(producto.pk)

    advertencia_teja = (
        ' Si encuentras una teja quebrada, corrida o faltante, ese elemento debe reemplazarse; '
        'un sellador no sustituye una teja dañada.' if cubierta == 'teja' else ''
    )
    return {
        'tipo': 'orientacion_gotera',
        'mensaje': (
            f'REPARACIÓN INICIAL DE GOTERA EN TECHO DE {cubierta.upper()}\n'
            f'Para una filtración puntual en {cubierta}, estos son los materiales de SFI que puedes revisar primero. '
            'Aplícalos únicamente después de ubicar la unión, traslape o encuentro que pierde agua.'
            + advertencia_teja
            + ('\n\nLos productos mostrados son para una reparación localizada; no hace falta medir ni revisar toda la estructura '
               'para comenzar esta inspección.' if productos else
               '\n\nNo encontré un material compatible con stock para mostrar en este momento.')
            + '\n\nNo trabajes sobre una cubierta mojada. Si la filtración no se puede ubicar desde una posición segura, solicita una revisión de Techumbre.'
        ),
        'productos': productos,
        'maestros': [],
        'sugerencias': [
            'La gotera aparece en un traslape',
            'La gotera aparece junto a un tornillo',
            'Buscar maestro de Techumbre',
        ],
    }


def _resolver_seguimiento_gotera_techo(mensaje, historial):
    """Mantiene un diagnóstico de gotera sin convertirlo en obra de techumbre."""
    contenido_previo = ' '.join(
        str(item.get('content') or '')
        for item in (historial or [])[-8:]
        if item.get('role') == 'assistant'
    )
    if 'filtracion puede provenir de la cubierta' not in _texto_normalizado(contenido_previo):
        return None

    conversacion = _texto_normalizado(' '.join([
        *(str(item.get('content') or '') for item in (historial or [])[-8:]
          if item.get('role') == 'user'),
        mensaje,
    ]))
    if not any(material in conversacion for material in (
        'policarbonato', 'zinc', 'teja', 'cubierta',
    )):
        return None

    tiene_ubicacion = any(indicio in conversacion for indicio in (
        'union', 'junta', 'traslape', 'tornillo', 'borde', 'canaleta',
        'cumbrera', 'al medio', 'esquina', 'encuentro',
    ))
    sabe_si_llueve = any(indicio in conversacion for indicio in (
        'solo con lluvia', 'cuando llueve', 'con lluvia', 'no llueve',
    ))
    no_logra_ubicar = any(frase in conversacion for frase in (
        'no logro ubicar', 'no identifico el origen', 'no identifico el punto',
        'no se donde entra', 'no se por donde entra',
    ))
    if no_logra_ubicar:
        cubierta = next((material for material in ('policarbonato', 'zinc', 'teja')
                         if material in conversacion), 'cubierta')
        # La recomendación inicial debe respetar el material que el cliente ya
        # indicó; no corresponde ofrecer sellador para policarbonato si es zinc.
        opciones_por_cubierta = {
            'policarbonato': (
                ('sellador neutro compatible con policarbonato', 'Sellado posible de uniones'),
                ('cinta butilica impermeable', 'Sellado posible de traslapes'),
            ),
            'zinc': (
                ('cinta butilica impermeable', 'Sellado posible de traslapes de zinc'),
                ('tapagoteras acrilico impermeabilizante', 'Reparación puntual de fisuras o encuentros'),
            ),
            'teja': (
                ('tapagoteras acrilico impermeabilizante', 'Reparación puntual de encuentros'),
                ('sellador poliuretano para exterior', 'Sellado exterior localizado'),
            ),
        }
        productos = []
        usados = set()
        for consulta, rol in opciones_por_cubierta.get(cubierta, ()):
            producto = next((candidato for candidato in _buscar_productos(consulta, limite=8)
                             if candidato.stock > 0 and candidato.pk not in usados), None)
            if not producto:
                continue
            item = _producto_publico(producto)
            item.update({
                'rol': rol,
                'carrito_cantidad': 1,
                'es_opcional': True,
            })
            productos.append(item)
            usados.add(producto.pk)
        mensaje_productos = (
            f'Te muestro materiales reales compatibles con una reparación puntual en una cubierta de {cubierta}. '
            'Úsalos solo en el punto identificado; no es necesario sellar toda la cubierta.'
            if productos else
            f'Por ahora no encontré sellos compatibles disponibles en SFI para una cubierta de {cubierta}.'
        )
        return {
            'tipo': 'orientacion_gotera',
            'mensaje': (
                f'REVISIÓN GUIADA DE GOTERA EN {cubierta.upper()}\n'
                'Como no logras ubicar la entrada, no conviene sellar toda la cubierta al azar. '
                'En una lluvia leve, observa desde un lugar seguro por dónde aparece la primera gota: '
                'los traslapes, los tornillos con golilla y el encuentro con el muro o canaleta.\n\n'
                'Si la primera gota aparece en una unión o traslape, normalmente se revisa el sello '
                'compatible antes de reemplazar una plancha. Si aparece en borde o canaleta, revisa '
                'primero el drenaje.\n\n'
                + mensaje_productos
                + '\n\nNo subas a la techumbre ni trabajes sobre ella si está mojada. '
                'Si no puedes identificar el punto desde una posición segura, solicita una revisión de Techumbre.'
            ),
            'productos': productos,
            'maestros': [],
            'sugerencias': [
                'La gotera aparece en una unión',
                'La gotera aparece junto a un tornillo',
                'Buscar maestro de Techumbre',
            ],
        }
    if tiene_ubicacion and sabe_si_llueve:
        return None

    cubierta = next((material for material in ('policarbonato', 'zinc', 'teja')
                     if material in conversacion), 'cubierta')
    return {
        'tipo': 'seguimiento_gotera',
        'mensaje': (
            'SIGAMOS CON LA GOTERA\n'
            f'Entiendo que la cubierta es de {cubierta}. No necesito las medidas ni la estructura '
            'para ubicar primero una filtración puntual.\n\n'
            'Solo falta identificar el punto por donde entra el agua:\n'
            '• Cerca de una unión, junta o traslape.\n'
            '• Junto a un tornillo o fijación.\n'
            '• En un borde, encuentro con muro o canaleta.\n'
            '• No logro ubicarlo todavía.\n\n'
            'Indícame además si ocurre solamente cuando llueve. Con eso te recomendaré '
            'solo los sellos, fijaciones o materiales compatibles que correspondan.'
        ),
        'productos': [],
        'maestros': [],
        'sugerencias': [
            'Entra por una unión y solo cuando llueve',
            'Entra cerca de un tornillo cuando llueve',
            'No logro ubicar el punto de entrada',
        ],
    }


def _resolver_situacion_cotidiana(mensaje):
    """Orienta expresiones comunes sin invadir los cálculos de proyectos."""
    texto = _texto_normalizado(mensaje)
    if (re.search(r'\b(?:cortar|talar|derribar|corte|tala)\b', texto)
            and re.search(r'\b(?:arbol|arboles)\b', texto)):
        # La sierra circular para tableros no es una herramienta de tala.
        candidatos = [
            producto for producto in Producto.objects.filter(activo=True, stock__gt=0)
            if re.search(r'\bmotosierra\w*\b', _texto_normalizado(producto.nombre))
        ]
        candidatos.sort(key=lambda producto: (producto.precio, producto.pk))
        return {
            'tipo': 'productos' if candidatos else 'sin_resultados',
            'mensaje': (
                'Para cortar un árbol puede utilizarse una motosierra apropiada, '
                'pero la elección depende del tamaño y de las condiciones del lugar. '
                'Una sierra circular para tableros no es adecuada para talarlo. '
                'La tala implica riesgo de caída del árbol y de ramas; solicita una '
                'evaluación de personal capacitado, especialmente cerca de personas, '
                'construcciones o cables.\n\n'
                + ('Encontré estas motosierras con stock en SFI.' if candidatos else
                   'No encontré motosierras con stock en SFI.')
            ),
            'productos': [_producto_publico(producto) for producto in candidatos],
            'maestros': [], 'sugerencias': [],
        }
    if re.fullmatch(
        r'(?:con que|que herramienta)\s+(?:clavo|clavar|clavo yo)\s+'
        r'(?:un|una|el|la)\s+clav(?:o|ito|ito chico)[? .!]*', texto,
    ):
        candidatos = [
            producto for producto in _buscar_productos('martillo', limite=20)
            if producto.stock > 0
            and re.search(r'\bmartillos?\b', _texto_normalizado(producto.nombre))
        ]
        return {
            'tipo': 'productos' if candidatos else 'sin_resultados',
            'mensaje': (
                'Para clavar un clavo pequeño normalmente puedes usar un martillo '
                'adecuado al tamaño del clavo y la superficie. '
                + ('Estas son las opciones disponibles en SFI.' if candidatos else
                   'No encontré martillos con stock en SFI.')
            ),
            'productos': [_producto_publico(producto) for producto in candidatos],
            'maestros': [], 'sugerencias': [],
        }
    if (re.search(r'\btornillos?\b', texto)
            and re.search(r'\b(?:danad[oa]|barrid[oa]|rodad[oa]|pasad[oa]|'
                          r'desgastad[oa]|gastad[oa]|estropead[oa])\b', texto)):
        # No permitir que la regla genérica para tornillos ignore el daño.
        candidatos = [
            producto for producto in _buscar_productos('extractor tornillos', limite=20)
            if producto.stock > 0
            and re.search(r'\bextractor\w*\b', _texto_normalizado(producto.nombre))
            and re.search(r'\btornill\w*\b', _texto_normalizado(producto.nombre))
        ]
        productos = [_producto_publico(producto) for producto in candidatos]
        return {
            'tipo': 'productos' if productos else 'sin_resultados',
            'mensaje': (
                'Para una cabeza de tornillo dañada puede servir un extractor de tornillos, '
                'según el daño y la medida. Un destornillador común podría no sujetarla. '
                'Confirma el tamaño y el estado de la cabeza antes de elegir la herramienta.\n\n'
                + ('Encontré estas opciones en SFI.' if productos else
                   'No encontré un extractor de tornillos con stock en el catálogo de SFI.')
            ),
            'productos': productos, 'maestros': [], 'sugerencias': [],
        }
    situacion = detectar_situacion_cotidiana(mensaje)
    if not situacion:
        return None

    # Las reglas de producto directo solo identifican una acción genérica y
    # no comprueban todas las condiciones de la tarea (material, daño, acceso,
    # medida). Dejamos que Gemini interprete la consulta completa y que la
    # búsqueda posterior contraste sus candidatos con el catálogo real.
    if situacion['tipo'] == 'producto_directo':
        return None

    if situacion['tipo'] == 'riesgo':
        especialidad = situacion.get('especialidad', 'el área correspondiente')
        return {
            'tipo': 'orientacion_seguridad',
            'mensaje': (
                f"{situacion['mensaje']} Solicita la revisión de un profesional de "
                f'{especialidad}; SFI no recomendará materiales sin un diagnóstico seguro. '
                'Esta orientación no reemplaza una evaluación presencial.'
            ),
            'productos': [],
            'maestros': [],
            'sugerencias': [f'Buscar profesional de {especialidad}'],
        }

    if situacion['tipo'] == 'aclaracion':
        preguntas = '\n'.join(
            f'{indice}. {pregunta}'
            for indice, pregunta in enumerate(situacion['preguntas'][:3], start=1)
        )
        especialidad = situacion.get('especialidad')
        cierre = (
            f' Si no puedes comprobarlo con seguridad, consulta a un profesional de '
            f'{especialidad}.' if especialidad else
            ' Si detectas daño importante o no puedes comprobarlo con seguridad, consulta a un profesional.'
        )
        return {
            'tipo': 'aclaracion_cotidiana',
            'mensaje': (
                f"{situacion['contexto']}. Respóndeme estos datos:\n{preguntas}\n\n"
                'Con eso buscaré únicamente productos reales y con stock en SFI.' + cierre
            ),
            'productos': [],
            'maestros': [],
            'sugerencias': list(situacion.get('sugerencias', ()))[:3],
        }

    consulta = situacion['consulta']
    uso = situacion['uso']
    candidatos = [
        producto for producto in _buscar_productos(consulta, limite=10)
        if producto.stock > 0
        and 'herramienta' in _texto_normalizado(producto.categoria)
    ]
    if not candidatos:
        return {
            'tipo': 'sin_resultados',
            'mensaje': (
                f'Para {uso} necesitas una herramienta del tipo {consulta}, pero actualmente '
                'no encontré una disponible con stock en el catálogo SFI.'
            ),
            'productos': [],
            'maestros': [],
            'sugerencias': ['Buscar otra herramienta', 'Explicar el trabajo con más detalle'],
        }

    productos = []
    for producto in candidatos[:4]:
        item = _producto_publico(producto)
        item.update({
            'rol': 'Herramienta para la tarea',
            'carrito_cantidad': 1,
            'es_opcional': False,
        })
        productos.append(item)
    return {
        'tipo': 'productos',
        'mensaje': (
            f'Para {uso}, la herramienta adecuada es un {consulta}. '
            f'Encontré {len(productos)} opción(es) disponible(s) con stock en SFI. '
            'Confirma que sea compatible con el material y las condiciones reales antes de usarla.'
        ),
        'productos': productos,
        'maestros': [],
        'sugerencias': ['Muéstrame la opción más económica', 'Ver herramientas similares'],
    }


def _resolver_herramienta_por_tarea(mensaje):
    """Traduce una tarea cotidiana a una herramienta real del catálogo."""
    texto = _texto_normalizado(mensaje)
    # La herramienta depende de la acción y del material. Una picota de
    # jardinería afloja suelo; no es la recomendación adecuada para piedra.
    # Aunque SFI no la venda, orientamos al cliente con la herramienta correcta.
    if re.search(r'\b(?:picar|romper|quebrar)\b.{0,24}\bpiedra(?:s)?\b', texto):
        return {
            'tipo': 'orientacion_herramienta_no_disponible',
            'mensaje': (
                'Para picar piedra te conviene usar un combo o mazo junto con un cincel '
                'para mampostería: el combo entrega el golpe y el cincel concentra el impacto. '
                'Una picota jardinera sirve para aflojar tierra, por eso no es una alternativa '
                'equivalente. Por ahora no encontré combo ni cincel para piedra disponibles en SFI.'
            ),
            'productos': [],
            'maestros': [],
            'sugerencias': ['Buscar herramientas para tierra', 'Consultar herramientas de mampostería'],
        }
    if re.search(r'\b(?:cortar|trozar|partir)\b.{0,24}\bporcelanato\b', texto):
        return {
            'tipo': 'orientacion_herramienta_no_disponible',
            'mensaje': (
                'Para cortar porcelanato se usa una cortadora manual para porcelanato '
                'o un esmeril angular con disco diamantado continuo para porcelanato. '
                'La cortadora permite cortes rectos; el esmeril se reserva para ajustes o cortes especiales. '
                'También conviene usar lentes, guantes y protección respiratoria al cortar. '
                'Por ahora no encontré esas herramientas disponibles en SFI, por lo que no te recomendaré '
                'una cinta métrica ni un taladro como reemplazo.'
            ),
            'productos': [],
            'maestros': [],
            'sugerencias': ['Buscar materiales para porcelanato', 'Consultar herramientas de corte'],
        }
    tareas = (
        (
            r'\b(?:poner|meter|clavar|afirmar|fijar)\b.{0,24}\bclavos?\b|\bclavar\b',
            'martillo',
            'clavar o poner clavos',
        ),
        (
            r'\b(?:hacer|abrir)\b.{0,18}\b(?:agujeros?|hoyos?)\b|\bperforar\b',
            'taladro',
            'hacer perforaciones',
        ),
        (
            r'\b(?:cortar|trozar)\b.{0,24}\b(?:madera|tabla|tablero|melamina)\b',
            'sierra',
            'cortar madera o tableros',
        ),
        (
            r'\b(?:poner|apretar|soltar|sacar)\b.{0,24}\btornillos?\b',
            'destornillador',
            'trabajar con tornillos',
        ),
    )
    coincidencia = next((
        (consulta, uso)
        for patron, consulta, uso in tareas
        if re.search(patron, texto)
    ), None)
    if not coincidencia:
        return None

    consulta, uso = coincidencia
    candidatos = [
        producto for producto in _buscar_productos(consulta, limite=10)
        if producto.stock > 0
        and 'herramienta' in _texto_normalizado(producto.categoria)
    ]
    if not candidatos:
        return {
            'tipo': 'sin_resultados',
            'mensaje': (
                f'Para {uso} necesitas una herramienta del tipo {consulta}, pero actualmente '
                'no encontré una disponible con stock en el catálogo SFI.'
            ),
            'productos': [],
            'maestros': [],
            'sugerencias': ['Buscar otra herramienta', 'Explicar el trabajo con más detalle'],
        }

    productos = []
    for producto in candidatos[:4]:
        item = _producto_publico(producto)
        item.update({
            'rol': 'Herramienta para la tarea',
            'carrito_cantidad': 1,
            'es_opcional': False,
        })
        productos.append(item)
    return {
        'tipo': 'productos',
        'mensaje': (
            f'Para {uso}, la herramienta adecuada es un {consulta}. '
            f'Encontré {len(productos)} opción(es) disponible(s) con stock en SFI.'
        ),
        'productos': productos,
        'maestros': [],
        'sugerencias': ['Muéstrame la opción más económica', 'Ver herramientas similares'],
    }


def _resolver_producto_breve(mensaje):
    """Trata una frase nominal corta como producto, no como proyecto completo."""
    texto = _texto_normalizado(mensaje)
    if _pregunta_uso_producto(mensaje):
        consulta = _consulta_sin_pregunta_de_uso(mensaje)
        productos = _buscar_productos(consulta, limite=3) if consulta else []
        productos = _producto_mencionado_para_uso(consulta, productos)
        respuesta_uso = _respuesta_uso_producto(productos)
        if respuesta_uso:
            return respuesta_uso
    palabras = re.findall(r'\b\w+\b', texto)
    if not (1 <= len(palabras) <= 7):
        return None
    if not ('?' in str(mensaje) or ' para ' in f' {texto} '):
        return None
    if any(termino in palabras for termino in (
        'que', 'como', 'cuales', 'material', 'materiales', 'herramienta',
        'herramientas', 'proyecto', 'construir', 'hacer', 'instalar',
        'cambiar', 'reparar', 'necesito', 'quiero', 'maestro', 'maestros',
        'profesional', 'profesionales', 'presupuesto', 'precio', 'cuanto',
        'cuesta', 'sale', 'total', 'barato', 'barata', 'economico', 'economica',
        'ese', 'esa', 'esos', 'esas', 'primero', 'primera', 'segundo', 'segunda',
        'mil', 'lucas',
    )):
        return None
    return resolver_interpretacion({
        'intencion': 'buscar_producto',
        'consulta_producto': mensaje.strip().rstrip(' ?'),
    })


def _resolver_busqueda_por_funcion(mensaje):
    """Busca opciones por la necesidad descrita, aunque no haya un producto."""
    texto = _texto_normalizado(mensaje)
    coincidencia = re.search(
        r'\b(?:que|cual)\s+(?:sirve|sirva|funciona|funcione)\s+para\s+(.+)',
        texto,
    )
    if not coincidencia:
        return None
    necesidad = coincidencia.group(1).strip(' ?¿.,;:')
    if not necesidad or len(necesidad.split()) > 8:
        return None
    productos = _buscar_productos(necesidad)
    if not productos:
        return None
    return resolver_interpretacion({
        'intencion': 'buscar_producto',
        'consulta_producto': necesidad,
        'respuesta': (
            'La búsqueda se realizó por la función que necesitas, usando los '
            'usos y descripciones disponibles en las fichas de SFI.'
        ),
    })


def _resolver_identificacion_pieza(mensaje):
    """Identifica piezas descritas por su ubicación o función.

    Esta ruta resuelve descripciones de alta certeza antes de tratarlas como una
    búsqueda literal. El nombre técnico y la explicación se entregan al cliente,
    pero las tarjetas continúan saliendo exclusivamente del catálogo SFI.
    """
    texto = _texto_normalizado(mensaje)

    if (re.search(r'\bgas\b', texto) and re.search(r'\bcocina\b', texto)
            and re.search(r'\b(?:objeto|pieza|cosa|coso)\b', texto)
            and re.search(r'\b(?:conecta|conectar|conectado)\b', texto)
            and not re.search(r'\b(?:flexible|manguera|valvula|llave|regulador)\b', texto)):
        return {
            'tipo': 'aclaracion',
            'mensaje': (
                'Podría tratarse del flexible de gas, de la llave de corte o del '
                'regulador, según la pieza que busques. ¿Necesitas la conexión '
                'flexible de la cocina, la llave que corta el gas o el regulador? '
                'La compatibilidad y la instalación deben ser verificadas por un '
                'instalador de gas autorizado SEC.'
            ),
            'productos': [], 'maestros': [],
            'sugerencias': ['Flexible de gas', 'Llave de corte de gas', 'Regulador de gas'],
        }

    def respuesta_identificacion(nombre, consulta, funcion, verificacion, productos=None):
        productos_publicos = []
        candidatos = productos if productos is not None else _buscar_productos(consulta, limite=6)
        for producto in candidatos:
            item = _producto_publico(producto)
            item.update({'carrito_cantidad': 1, 'rol': 'Kit o componente relacionado'})
            productos_publicos.append(item)

        mensaje_respuesta = (
            'IDENTIFICACIÓN DE LA PIEZA\n\n'
            f'La pieza se llama {nombre}. {funcion}\n\n'
        )
        if productos_publicos:
            mensaje_respuesta += (
                f'DISPONIBILIDAD EN SFI\nEncontré {len(productos_publicos)} opción(es) activa(s) '
                'con stock en el catálogo. Si es un kit, revisa su ficha '
                f'para confirmar que incluya la pieza que necesitas. Antes de comprar, {verificacion}.'
            )
        else:
            mensaje_respuesta += (
                'DISPONIBILIDAD EN SFI\nNo encontré esta pieza disponible como producto en SFI. '
                f'Antes de comprar, {verificacion}.'
            )
        return {
            'tipo': 'identificacion_pieza',
            'mensaje': mensaje_respuesta,
            'productos': productos_publicos,
            'maestros': [],
            'sugerencias': ['¿Para qué sirve?', '¿Cómo verifico la compatibilidad?'],
        }

    # En Chile y otros países de Latinoamérica es habitual describir una pieza
    # sin conocer su nombre técnico: "el coso del agua", "la canilla", "la
    # manguerita de abajo" o "lo que conecta la pileta". Antes de depender de
    # Gemini, traducimos las expresiones inequívocas y pedimos una aclaración
    # breve cuando todavía pueden corresponder a alimentación o desagüe.
    contexto_cocina = bool(re.search(
        r'\b(?:cocina|lavaplatos|fregadero|pileta|tarja)\b', texto,
    ))
    menciona_agua = bool(re.search(
        r'\b(?:agua|gotea|goteo|fuga|filtra|mojado|mojada)\b', texto,
    ))
    termino_vago = bool(re.search(
        r'\b(?:coso|cosito|cosita|cosa|cuestion|chunche|aparato|pieza|cosilla)\b',
        texto,
    ))
    pide_conexion_ambigua = bool(re.search(
        r'\b(?:lo que|la cosa|el coso|la cuestion)\b.{0,35}'
        r'\b(?:conecta|conectar|va debajo|esta debajo|lleva el agua)\b',
        texto,
    ))

    if contexto_cocina:
        menciona_griferia = bool(re.search(
            r'\b(?:griferia|grifo|canilla|mezcladora|monomando|llave del agua|'
            r'llave de agua|abre el agua|abrir el agua|sale el agua)\b', texto,
        ))
        menciona_flexible = bool(re.search(
            r'\b(?:flexible|latiguillo|manguera|manguerita)\b', texto,
        ))
        menciona_sifon = bool(re.search(
            r'\b(?:sifon|desague|drenaje|tubo de abajo|tubo por donde se va|'
            r'por donde se va el agua)\b', texto,
        ))

        if menciona_griferia:
            return respuesta_identificacion(
                'llave o grifería de cocina',
                'griferia cocina lavaplatos',
                'Abre, cierra y regula la salida de agua sobre el lavaplatos.',
                'confirma el tipo de montaje, la cantidad de perforaciones y las conexiones de agua fría y caliente',
            )
        if menciona_flexible and (menciona_agua or re.search(r'\b(?:bajo|debajo|conecta)\b', texto)):
            return respuesta_identificacion(
                'flexible de agua para grifería',
                'flexible agua griferia',
                'Conecta la grifería con la llave de paso o la alimentación de agua.',
                'confirma el largo, el diámetro y si ambos extremos son hilo interno o externo',
            )
        if menciona_sifon:
            return respuesta_identificacion(
                'sifón o conjunto de desagüe de lavaplatos',
                'sifon lavaplatos desague',
                'Conduce el agua usada al desagüe y el sifón ayuda a impedir el retorno de malos olores.',
                'confirma el diámetro, el espacio bajo el lavaplatos y la posición de la descarga',
            )
        if (termino_vago and menciona_agua) or pide_conexion_ambigua:
            return {
                'tipo': 'aclaracion_pieza_cocina',
                'mensaje': (
                    'Entiendo que buscas una pieza relacionada con el agua de la cocina, '
                    'pero puede ser una de estas tres:\n\n'
                    '• Llave, grifo, canilla o grifería: es la pieza por donde sale el agua.\n'
                    '• Flexible o manguerita: conecta la grifería con la alimentación de agua bajo el lavaplatos.\n'
                    '• Sifón o desagüe: es el tubo por donde se elimina el agua usada.\n\n'
                    'Indica cuál se parece más a lo que necesitas y cuéntame si gotea, está roto o quieres reemplazarlo.'
                ),
                'productos': [],
                'maestros': [],
                'sugerencias': [
                    'Es la llave por donde sale el agua',
                    'Es la manguerita bajo el lavaplatos',
                    'Es el tubo del desagüe',
                ],
            }

    menciona_lavaplatos = bool(re.search(r'\b(?:lavaplatos|fregadero)\b', texto))
    evita_olores = bool(re.search(
        r'\b(?:malos? olores?|olores?|olor|evita(?:r)? que suba(?:n)?)\b', texto,
    ))
    debajo = bool(re.search(r'\b(?:debajo|bajo)\b', texto))
    menciona_desague = bool(re.search(r'\b(?:desague|desagüe)\b', texto))
    if menciona_lavaplatos and evita_olores and (debajo or menciona_desague):
        return respuesta_identificacion(
            'sifón de lavaplatos',
            'sifon lavaplatos',
            'Va bajo el lavaplatos y mantiene un sello de agua que ayuda a impedir '
            'el retorno de olores desde el desagüe.',
            'verifica el diámetro de la descarga, el espacio disponible y el tipo de conexión',
        )

    menciona_gas = bool(re.search(r'\bgas\b', texto))
    solicita_corte_gas = bool(re.search(
        r'\b(?:cortar|corte|cerrar|cierre|paso|detener)\b', texto,
    ))
    if menciona_gas and solicita_corte_gas:
        valvulas_gas = [
            producto
            for producto in Producto.objects.filter(activo=True, stock__gt=0).order_by('nombre')
            if 'gas' in _texto_normalizado(producto.nombre)
            and any(termino in _texto_normalizado(producto.nombre) for termino in (
                'valvula', 'llave', 'corte',
            ))
        ]
        return respuesta_identificacion(
            'llave de paso o válvula de corte de gas',
            'valvula corte gas',
            'Permite interrumpir el paso de gas hacia un artefacto para una mantención o una emergencia.',
            'confirma la medida, el tipo de gas y la compatibilidad con tu instalación; su instalación o reemplazo debe realizarlo un instalador autorizado SEC',
            productos=valvulas_gas[:6],
        )

    menciona_dispositivos = bool(re.search(
        r'\b(?:dispositivo|dispositivos|equipo|equipos|aparato|aparatos|electronico|electronicos)\b',
        texto,
    ))
    solicita_conexion_multiple = bool(re.search(
        r'\b(?:conectar|conecta|enchufar|enchufa|alimentar)\b', texto,
    )) and bool(re.search(r'\b(?:multiples?|multoples?|varios?|muchos?)\b', texto))
    if menciona_dispositivos and solicita_conexion_multiple:
        alargadores = [
            producto
            for producto in Producto.objects.filter(activo=True, stock__gt=0).order_by('nombre')
            if any(termino in _texto_normalizado(producto.nombre) for termino in (
                'alargador', 'extension electrica',
            ))
        ]
        return respuesta_identificacion(
            'alargador eléctrico; para conectar varios equipos a la vez se usa además una zapatilla o multitoma',
            'alargador electrico',
            'El alargador lleva la alimentación hasta el lugar de uso. Para varios dispositivos, la zapatilla o multitoma debe respetar la potencia máxima del circuito.',
            'revisa la potencia total de los equipos y no sobrecargues el alargador ni conectes artefactos de alto consumo en una multitoma doméstica',
            productos=alargadores[:6],
        )

    menciona_caja_electrica = bool(re.search(
        r'\b(?:caja electrica|caja de conexiones|caja estanca|caja de paso)\b', texto,
    ))
    menciona_cable = bool(re.search(r'\b(?:cable|cables|conductor|conductores)\b', texto))
    solicita_union_electrica = bool(re.search(
        r'\b(?:conectar|conecta|unir|une|empalmar|empalma|juntar|junta)\b', texto,
    ))
    if menciona_caja_electrica and menciona_cable and solicita_union_electrica:
        conectores = [
            producto
            for producto in Producto.objects.filter(activo=True, stock__gt=0).order_by('nombre')
            if any(termino in _texto_normalizado(producto.nombre) for termino in (
                'conector', 'bornera', 'regleta', 'terminal',
            ))
            and any(termino in _texto_normalizado(
                f'{producto.nombre} {producto.categoria} {producto.descripcion}'
            ) for termino in ('electr', 'cable', 'conductor'))
        ]
        return respuesta_identificacion(
            'conector eléctrico, también llamado bornera o regleta de conexión',
            'conector cable electrico',
            'Une conductores dentro de una caja eléctrica de forma ordenada. La alternativa exacta depende '
            'del número de cables, su sección y del tipo de caja.',
            'confirma la sección del cable y que la conexión se realice sin tensión; si el circuito está energizado o es fijo, solicita apoyo de un electricista competente',
            productos=conectores[:6],
        )

    menciona_porton_automatico = bool(re.search(
        r'\bporton\b.{0,25}\b(?:automatico|electrico)\b|'
        r'\b(?:automatico|electrico)\b.{0,25}\bporton\b',
        texto,
    ))
    solicita_abrir_porton = bool(re.search(
        r'\b(?:abrir|abre|apertura|accionar|activar|controlar)\b', texto,
    ))
    if menciona_porton_automatico and solicita_abrir_porton:
        controles_porton = [
            producto
            for producto in Producto.objects.filter(activo=True, stock__gt=0).order_by('nombre')
            if 'porton' in _texto_normalizado(producto.nombre)
            and any(termino in _texto_normalizado(producto.nombre) for termino in (
                'control remoto', 'control porton',
            ))
        ]
        return respuesta_identificacion(
            'control remoto para portón automático',
            'control remoto porton automatico',
            'Envía una señal al receptor compatible para abrir o cerrar el portón a distancia.',
            'confirma la frecuencia, la codificación y la compatibilidad con el motor o receptor instalado',
            productos=controles_porton[:6],
        )

    # Jardinería también forma parte del catálogo. Estas consultas suelen
    # describir la función y no el nombre técnico del producto.
    menciona_planta = bool(re.search(
        r'\b(?:planta|plantas|tallo|tallos|enredadera|enredaderas)\b', texto,
    ))
    solicita_soporte_planta = bool(re.search(
        r'\b(?:sostener|sujetar|guiar|afirmar|apoyar|mantener)\b', texto,
    ))
    if menciona_planta and solicita_soporte_planta:
        productos_jardin = list(
            Producto.objects.filter(activo=True, stock__gt=0).order_by('nombre')
        )
        tutores = [
            producto for producto in productos_jardin
            if any(termino in _texto_normalizado(producto.nombre) for termino in (
                'tutor', 'estaca', 'bambu',
            ))
        ]
        amarras = [
            producto for producto in productos_jardin
            if any(termino in _texto_normalizado(producto.nombre) for termino in (
                'amarra', 'cinta jardin', 'cinta para plantas',
            ))
        ]
        candidatos = []
        for producto in tutores + amarras:
            if producto.id not in {item.id for item in candidatos}:
                candidatos.append(producto)
        return respuesta_identificacion(
            'tutor para plantas',
            'tutor plantas',
            'Se instala junto al tallo para mantenerlo erguido y guiar su crecimiento. '
            'Puede complementarse con amarras flexibles de jardín para sujetarlo sin apretarlo.',
            'verifica la altura que alcanzará la planta y usa una amarra suave, dejando espacio para que el tallo crezca',
            productos=candidatos[:6],
        )

    menciona_monomando = bool(re.search(r'\b(?:monomando|llave de ducha|griferia de ducha)\b', texto))
    menciona_ducha_manual = bool(re.search(
        r'\b(?:ducha telefono|telefono de ducha|mango de ducha|regadera)\b', texto,
    ))
    describe_union = bool(re.search(
        r'\b(?:va|une|conecta|sale)\b.{0,55}\b(?:desde|entre|hasta|al|del)\b', texto,
    ))
    if not (menciona_monomando and menciona_ducha_manual and describe_union):
        return None
    return respuesta_identificacion(
        'flexible de ducha, también conocido como manguera para ducha teléfono',
        'flexible ducha',
        'Conecta el monomando con el mango de ducha y permite moverlo durante el uso.',
        'verifica el largo y el tipo de rosca de tu instalación',
    )


def _mensaje_para_continuar_guia(mensaje, historial):
    """Aclara a Gemini que una respuesta breve completa la guía vigente."""
    texto = _texto_normalizado(mensaje)
    palabras = re.findall(r'\b\w+\b', texto)
    if not palabras or len(palabras) > 8:
        return mensaje
    if re.search(
        r'\b(?:quiero|necesito|voy a|deseo)\b.{0,30}'
        r'\b(?:hacer|construir|instalar|cambiar|reparar|comprar)\b',
        texto,
    ):
        return mensaje

    ultimo_asistente = next((
        str(item.get('content') or '')
        for item in reversed(historial)
        if item.get('role') == 'assistant'
    ), '')
    ultimo_normalizado = _texto_normalizado(ultimo_asistente)
    es_guia_pendiente = any(marca in ultimo_normalizado for marca in (
        'primero identifiquemos',
        'antes de recomendar productos',
        'sigamos con tu proyecto',
        'indica cual de estas opciones',
        'responde todo en un mensaje',
        'que tipo de teja prefieres',
    ))
    if not es_guia_pendiente:
        return mensaje

    return (
        'CONTINÚA EL PROYECTO Y LA PREGUNTA PENDIENTE DEL HISTORIAL. '
        'No interpretes esta respuesta como una búsqueda ni como un proyecto nuevo. '
        'Conserva los datos ya entregados y no vuelvas a preguntar lo que el cliente '
        'respondió. Si la respuesta identifica una categoría pero falta una variante '
        'que cambia la compatibilidad, pregunta solo por esa variante; no la inventes. '
        f'Respuesta breve del cliente: {mensaje}'
    )


def _clasificar_seguimiento_natural(mensaje, productos_contexto):
    """Clasifica expresiones libres sin obligar al cliente a usar botones."""
    if not productos_contexto:
        return ''
    texto = _texto_normalizado(mensaje)
    if (
        'herramienta' in texto
        and re.search(r'\b(?:material(?:es)?|producto(?:s)?|insumo(?:s)?)\b', texto)
    ):
        # Es una solicitud de proyecto completo, no una acción sobre las
        # tarjetas mostradas anteriormente.
        return ''
    if re.search(
        r'\b(?:herramientas?|con que)\b.{0,45}\b(?:usar|uso|hacer|instalar|'
        r'trabajar|necesit\w*|recomend\w*)\b|'
        r'\b(?:que|cuales|dime|muestra(?:me)?)\b.{0,45}\bherramientas?\b',
        texto,
    ) or any(frase in texto for frase in ('con que hago esta pega', 'con que se hace')):
        return 'herramientas'
    if _pide_profesional_para_proyecto(mensaje) or bool(re.search(
        r'\b(?:busco|necesito|quiero|recomiend\w*)\b.{0,40}'
        r'\b(?:alguien|maestr[oa]|profesional|especialista)\b.{0,40}'
        r'\b(?:pega|trabajo|proyecto|instalacion|obra)\b',
        texto,
    )):
        return 'profesional'
    if re.search(
        r'\b(?:cuanto|cuanto me|cuanto nos)\b.{0,35}'
        r'\b(?:sale|cuesta|costaria|saldra|total|todo|proyecto)\b|'
        r'\b(?:total|costo total|valor total|presupuesto final)\b',
        texto,
    ):
        return 'total'
    if re.search(
        r'\bpor que\b.{0,45}\b(?:materiales?|productos?|eleg\w*|'
        r'pusiste|incluiste|seleccion\w*|recomiend\w*)\b',
        texto,
    ):
        return 'explicacion'
    if re.search(
        r'\b(?:alternativas?|opciones?|algo)\b.{0,35}\b(?:barat\w*|econom\w*)\b|'
        r'\b(?:barat\w*|econom\w*)\b.{0,35}\b(?:alternativas?|opciones?|algo)\b',
        texto,
    ):
        return 'economico'
    if re.search(
        r'\b(?:ver|mostrar|muestrame|buscar|comparar)\b.{0,30}'
        r'\b(?:alternativas?|opciones?)\b',
        texto,
    ):
        return 'alternativas'
    if re.search(
        r'\b(?:ajustar|modificar|cambiar)\b.{0,40}'
        r'\b(?:proyecto|medidas?|material|cubierta|terminacion|solo)\b',
        texto,
    ):
        return 'ajuste'
    return ''


def _resolver_total_contextual(historial):
    """Recupera el último total ya calculado sin reconstruir el proyecto."""
    ultimo_total = None
    for item in reversed(historial):
        if item.get('role') != 'assistant':
            continue
        contenido = str(item.get('content') or '')
        coincidencia = re.search(
            r'TOTAL CALCULADO\s*\n?\s*(\$[\d.]+\s*CLP)(.*?)(?:\n\n|$)',
            contenido,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if coincidencia:
            ultimo_total = ' '.join(
                f'{coincidencia.group(1)} {coincidencia.group(2)}'.split()
            )
            break
    mensaje = (
        f'TOTAL ACTUAL DEL PROYECTO\n{ultimo_total}'
        if ultimo_total
        else (
            'Todavía no hay un total completo calculado para este proyecto. '
            'Primero debo contar con cantidades verificadas para los materiales.'
        )
    )
    return {
        'tipo': 'seguimiento_proyecto',
        'mensaje': mensaje,
        'productos': [],
        'maestros': [],
        'sugerencias': ['Volver al resumen del proyecto', 'Ver alternativas más económicas'],
    }


def _resolver_resumen_contextual(historial):
    """Recupera la última propuesta sin volver a interpretarla con Gemini."""
    for item in reversed(historial):
        if item.get('role') != 'assistant':
            continue
        contenido = str(item.get('content') or '').strip()
        if any(marca in contenido.upper() for marca in (
            'PROPUESTA ESTÁNDAR PARA TU PROYECTO',
            'PRODUCTOS POR ETAPA',
            'MATERIALES Y PARA QUÉ SE USAN',
            'RESULTADO\nENCONTRÉ',
        )):
            return {
                'tipo': 'resumen_proyecto',
                'mensaje': contenido,
                'productos': [],
                'maestros': [],
                'sugerencias': [
                    '¿Por qué elegiste estos materiales?',
                    '¿Qué herramientas necesito para este proyecto?',
                    'Muéstrame alternativas más económicas',
                ],
            }
    return {
        'tipo': 'seguimiento_proyecto',
        'mensaje': (
            'No encontré un resumen anterior completo en esta conversación. '
            'Describe el proyecto que deseas retomar y conservaré su contexto.'
        ),
        'productos': [],
        'maestros': [],
        'sugerencias': ['Describir el proyecto nuevamente'],
    }


def _resolver_accion_seguimiento(mensaje, productos_contexto):
    """Resuelve botones de seguimiento sin reinterpretar el proyecto completo."""
    if not productos_contexto:
        return None
    texto = _texto_normalizado(mensaje)
    if (
        'herramienta' in texto
        and re.search(r'\b(?:material(?:es)?|producto(?:s)?|insumo(?:s)?)\b', texto)
    ):
        # La consulta solicita una propuesta completa. No debe convertirse en
        # una acción de seguimiento aunque el navegador conserve tarjetas.
        return None
    pide_herramientas = bool(re.search(
        r'\b(?:que|cuales|dime|indica|muestra(?:me)?|necesito)\b.{0,45}'
        r'\bherramientas?\b|\bherramientas?\b.{0,35}'
        r'\b(?:necesarias?|recomendadas?|usar|uso|necesito)\b',
        texto,
    ))
    if pide_herramientas:
        materiales = list(Producto.objects.filter(
            pk__in=list(dict.fromkeys(productos_contexto))[:8],
            activo=True,
        ))
        contexto = _texto_normalizado(' '.join(
            f'{producto.nombre} {producto.categoria} {producto.uso_recomendado}'
            for producto in materiales
        ))
        consultas = []
        es_contexto_pintura = any(
            _texto_normalizado(producto.categoria) == 'pinturas'
            or _texto_normalizado(producto.tipo_calculo) == 'pintura'
            for producto in materiales
        )
        if es_contexto_pintura:
            # La ficha de una pintura puede mencionar madera, hormigón u otras
            # superficies. Esos términos describen el soporte y no deben
            # activar herramientas de carpintería u obra gruesa.
            consultas.extend([
                'rodillo pintura',
                'brocha pintura',
                'bandeja para pintura',
            ])
        elif any(termino in contexto for termino in (
            'pasta muro', 'pasta de retape', 'retape', 'masilla',
            'pasta para juntas', 'yeso carton', 'yeso-carton',
        )):
            # Debe evaluarse antes de pintura: las pastas se aplican con
            # espátula y luego se lijan; rodillo y brocha son para pintar.
            consultas.extend(['espatula acero', 'lija muro'])
        elif any(termino in contexto for termino in (
            'ceramica', 'porcelanato', 'frague', 'separadores',
            'nivelador ceramica', 'adhesivo ceramico',
        )):
            consultas.extend([
                'cinta metrica',
                'nivel de burbuja aluminio 60 cm',
                'llana dentada acero 10 mm',
                'cortadora manual porcelanato 600 mm',
                'disco diamantado continuo porcelanato 115 mm',
                'esmeril angular 4 1/2 pulgadas 850 W',
                'mazo de goma para ceramica',
                'balde flexible para mezcla pisos 28 litros',
                'paleta mezcladora para adhesivo y mortero',
                'llana de goma para frague',
                'esponja para limpieza de frague',
                'rodillera espuma instalacion pisos',
                'guantes de trabajo nitrilo reforzado',
                'lentes seguridad policarbonato transparentes',
                'respirador reutilizable P95 con filtro',
                'protector auditivo tipo copa 27 dB',
            ])
        elif any(termino in contexto for termino in (
            'techo', 'techumbre', 'zinc', 'teja', 'policarbonato', 'cubierta',
        )):
            consultas.extend(['cinta metrica', 'taladro percutor'])
        if not es_contexto_pintura:
            if any(termino in contexto for termino in ('madera', 'pino', 'tablero', 'melamina')):
                consultas.extend(['cinta metrica', 'taladro percutor', 'sierra circular'])
            if any(termino in contexto for termino in ('radier', 'hormigon', 'mortero', 'tierra')):
                consultas.extend(['cinta metrica', 'pala'])
        if not consultas:
            consultas = ['cinta metrica', 'taladro percutor']
        consultas = list(dict.fromkeys(consultas))

        herramientas = []
        usadas = set()
        usos_herramientas = {
            'cinta metrica': 'Medir y marcar las dimensiones antes de cortar o montar.',
            'taladro percutor': 'Perforar y colocar las fijaciones del proyecto.',
            'sierra circular': 'Cortar madera o tableros a las medidas necesarias.',
            'rodillo pintura': 'Aplicar la pintura uniformemente en superficies amplias.',
            'brocha pintura': 'Aplicar pintura en bordes, esquinas y zonas de detalle.',
            'bandeja para pintura': 'Cargar y distribuir la pintura sobre el rodillo de forma controlada.',
            'espatula acero': 'Extender, presionar y nivelar la pasta en grietas e imperfecciones.',
            'lija muro': 'Emparejar suavemente la superficie una vez que la pasta esté seca.',
            'pala': 'Mover y mezclar materiales para preparar la base del proyecto.',
            'nivel de burbuja aluminio 60 cm': (
                'Comprobar nivel y planeidad durante la colocación.'
            ),
            'llana dentada acero 10 mm': (
                'Distribuir y peinar el adhesivo con un dentado compatible con la pieza.'
            ),
            'cortadora manual porcelanato 600 mm': (
                'Realizar cortes rectos y ajustes perimetrales en las piezas.'
            ),
            'disco diamantado continuo porcelanato 115 mm': (
                'Realizar cortes especiales con una herramienta eléctrica compatible; '
                'es condicional y exige protección adecuada.'
            ),
            'esmeril angular 4 1/2 pulgadas 850 W': (
                'Accionar el disco diamantado en cortes especiales, solo cuando sea '
                'compatible con el disco y se utilice protección completa.'
            ),
            'mazo de goma para ceramica': (
                'Asentar suavemente las piezas sin golpearlas con metal.'
            ),
            'balde flexible para mezcla pisos 28 litros': (
                'Contener y preparar adhesivo o fragüe respetando su ficha.'
            ),
            'paleta mezcladora para adhesivo y mortero': (
                'Homogeneizar la mezcla conectada a una herramienta motriz y mandril '
                'compatibles; la paleta no incluye el motor.'
            ),
            'llana de goma para frague': (
                'Aplicar el fragüe diagonalmente sobre las juntas y retirar el exceso.'
            ),
            'esponja para limpieza de frague': (
                'Limpiar el excedente superficial sin vaciar las juntas.'
            ),
            'rodillera espuma instalacion pisos': (
                'Proteger las rodillas durante el trabajo prolongado a nivel de piso.'
            ),
            'guantes de trabajo nitrilo reforzado': (
                'Proteger las manos durante la mezcla, colocación y limpieza.'
            ),
            'lentes seguridad policarbonato transparentes': (
                'Proteger los ojos frente a partículas durante cortes y preparación.'
            ),
            'respirador reutilizable P95 con filtro': (
                'Reducir la exposición a polvo durante cortes o preparación en seco.'
            ),
            'protector auditivo tipo copa 27 dB': (
                'Proteger la audición al utilizar herramientas eléctricas de corte.'
            ),
        }
        herramientas_por_sku = {
            # Este producto fue incorporado al catálogo con una ficha exacta,
            # pero las búsquedas libres pueden no resolver la tilde de
            # "cerámica" de forma uniforme entre MySQL y Python.
            'mazo de goma para ceramica': 'SFI-HER-CER-MAZ-16',
            # Estas consultas generales priorizan pinturas por relevancia.
            # Los SKU aseguran que el seguimiento devuelva herramientas.
            'rodillo pintura': 'TEST-HER-ROD-23',
            'brocha pintura': 'TEST-HER-BRO-2',
            'bandeja para pintura': 'SFI-PIN-BAN-25',
        }
        for consulta in consultas:
            herramienta = Producto.objects.filter(
                sku=herramientas_por_sku.get(consulta, ''),
                activo=True,
                stock__gt=0,
            ).first() or next((
                producto for producto in _buscar_productos(consulta, limite=10)
                if producto.pk not in usadas
                and (
                    any(clase in _texto_normalizado(producto.categoria) for clase in (
                        'herramienta', 'seguridad',
                    ))
                    or consulta == 'disco diamantado continuo porcelanato 115 mm'
                    or consulta in ('espatula acero', 'lija muro')
                )
            ), None)
            if not herramienta:
                continue
            herramientas_condicionales = {
                'disco diamantado continuo porcelanato 115 mm',
                'esmeril angular 4 1/2 pulgadas 850 W',
            }
            elementos_proteccion = {
                'rodillera espuma instalacion pisos',
                'guantes de trabajo nitrilo reforzado',
                'lentes seguridad policarbonato transparentes',
                'respirador reutilizable P95 con filtro',
                'protector auditivo tipo copa 27 dB',
            }
            if consulta in herramientas_condicionales:
                rol_herramienta = 'Herramienta condicional'
            elif consulta in elementos_proteccion:
                rol_herramienta = 'Protección recomendada'
            else:
                rol_herramienta = 'Herramienta principal no incluida'
            item = _producto_publico(herramienta)
            item.update({
                'rol': rol_herramienta,
                'carrito_cantidad': 1,
                'es_opcional': consulta in herramientas_condicionales,
                'incluido_en_total': False,
                'detalle_material': usos_herramientas.get(
                    consulta,
                    'Apoyar la ejecución segura y precisa de esta etapa del proyecto.',
                ),
            })
            herramientas.append(item)
            usadas.add(herramienta.pk)

        total_opcional = sum(
            (herramienta.get('precio') or 0 for herramienta in herramientas),
            0,
        )
        return {
            'tipo': 'seguimiento_herramientas',
            'mensaje': (
                'HERRAMIENTAS PARA ESTE PROYECTO\n'
                + (
                    '\n'.join(f"• {herramienta['nombre']}" for herramienta in herramientas)
                    if herramientas
                    else 'No encontré herramientas compatibles con stock en SFI.'
                )
                + (
                    '\n\nPARA QUÉ SE UTILIZA CADA UNA\n'
                    + '\n'.join(
                        f"- {herramienta['nombre']}: {herramienta['detalle_material']}"
                        for herramienta in herramientas
                    )
                    if herramientas else ''
                )
                + (
                    f'\n\nCOSTO DE HERRAMIENTAS NO INCLUIDO\n{_formatear_clp(total_opcional)} CLP '
                    'considerando una unidad de cada herramienta.'
                    if herramientas else ''
                )
                + (
                    '\n\nDEPENDENCIA A CONFIRMAR\nLa paleta mezcladora necesita una '
                    'herramienta motriz y un mandril compatibles, que no están incluidos '
                    'automáticamente en esta selección.'
                    if any('paleta mezcladora' in _texto_normalizado(
                        herramienta.get('nombre')
                    ) for herramienta in herramientas)
                    else ''
                )
                + '\n\nEstas herramientas no modifican el total calculado de materiales.'
            ),
            'productos': herramientas,
            'maestros': [],
            'sugerencias': [
                '¿Por qué elegiste estos materiales?',
                'Volver al resumen del proyecto',
                '¿Qué maestro realiza este trabajo?',
            ],
        }
    consulta_maestro_proyecto = _pide_profesional_para_proyecto(mensaje) or any(
        frase in texto for frase in (
        'que tipo de maestro necesito', 'que maestro necesito',
        'que tipo de profesional necesito', 'que profesional necesito',
        'que maestro trabaja con estos productos',
        'que maestra trabaja con estos productos',
        'que profesional trabaja con estos productos',
        'que especialista trabaja con estos productos',
        'quien puede hacer este proyecto', 'quien realiza este trabajo',
        'que maestro realiza este trabajo', 'que maestro hace este trabajo',
        'que maestro realiza este proyecto', 'que maestro hace este proyecto',
        'necesito un maestro para este trabajo',
        'neceisto un maestro para este trabajo',
        'necesito un maestro para este proyecto',
        'neceisto un maestro para este proyecto',
        'busco un maestro para este trabajo', 'busco un maestro para este proyecto',
        )
    ) or bool(re.search(
        r'\b(?:que|cual|quien)\b.{0,35}'
        r'\b(?:maestr[oa]|profesional|especialista|tecnico|tecnica)\b.{0,35}'
        r'\b(?:trabaja|instala|repara|realiza|usa|maneja)\b',
        texto,
    ))
    if consulta_maestro_proyecto:
        productos = list(Producto.objects.filter(
            pk__in=list(dict.fromkeys(productos_contexto))[:8],
            activo=True,
        ))
        contexto = _texto_normalizado(' '.join(
            f'{producto.nombre} {producto.categoria} {producto.uso_recomendado}'
            for producto in productos
        ))
        reglas = (
            # Una red o artefacto a gas no debe presentarse como gasfitería
            # general. La intervención requiere un instalador autorizado SEC.
            (
                (
                    'gas licuado', 'gas natural', 'cocina a gas', 'calefont',
                    'valvula de corte para gas', 'valvula corte gas',
                    'regulador gas', 'tubo cobre para gas', 'cobre para gas',
                    'instalacion de gas', 'red de gas',
                ),
                'Instalaciones de gas · SEC gas',
            ),
            ((
                'ladrillo', 'mortero', 'radier', 'malla acma',
                'refractario', 'base estabilizada',
            ), 'Albañilería'),
            (('techo', 'techumbre', 'zinc', 'teja', 'cumbrera', 'policarbonato'), 'Techumbre'),
            (('pino', 'madera', 'tablero', 'melamina'), 'Carpintería'),
            (('pintura', 'latex', 'esmalte', 'barniz'), 'Pintura'),
            # Las consultas pueden venir desde tarjetas de gas (válvulas,
            # cobre o flexibles) sin mencionar ducha o lavaplatos. Todos estos
            # componentes corresponden al oficio de gasfitería.
            (
                (
                    'gasfiteria', 'gas', 'valvula', 'cobre', 'flexible',
                    'sanitario', 'lavamanos', 'ducha', 'griferia', 'tuberia',
                    'sifon', 'desague', 'ppr', 'pvc sanitario',
                ),
                'Gasfitería',
            ),
            (('cable', 'enchufe', 'interruptor', 'luminaria'), 'Electricidad'),
            (('ceramica', 'porcelanato', 'fragüe'), 'Cerámica y revestimientos'),
        )
        especialidades = []
        for terminos, especialidad in reglas:
            if any(termino in contexto for termino in terminos):
                especialidades.append(especialidad)
        especialidades = list(dict.fromkeys(especialidades))[:3]
        maestros_relacionados = []
        if especialidades:
            principal = especialidades[0]
            apoyos = especialidades[1:]
            complemento = ''
            if apoyos:
                lista_apoyos = (
                    apoyos[0]
                    if len(apoyos) == 1
                    else f'{", ".join(apoyos[:-1])} y {apoyos[-1]}'
                )
                complemento = (
                    f' Como apoyo también corresponden {lista_apoyos}, según la etapa '
                    'del trabajo.'
                )
            mensaje_respuesta = (
                f'Para este proyecto, la especialidad principal es {principal}.'
                f'{complemento} Antes de contratar, confirma experiencia en el tipo de '
                'material y trabajo mostrado.'
            )
            if principal == 'Instalaciones de gas · SEC gas':
                mensaje_respuesta += (
                    ' Esta intervención debe realizarla un instalador autorizado '
                    'SEC en gas.'
                )
            # Una techumbre no puede asignarse a un oficio distinto solo para
            # llenar la respuesta. Se muestran perfiles actuales de apoyo
            # únicamente cuando sus especialidades se desprenden de los
            # materiales del proyecto (por ejemplo, estructura de madera).
            if principal == 'Techumbre':
                perfiles_usados = set()
                techumbristas = buscar_maestros('Techumbre', None, limite=5)
                for maestro in techumbristas:
                    if maestro['id'] not in perfiles_usados:
                        maestros_relacionados.append(maestro)
                        perfiles_usados.add(maestro['id'])
                for especialidad_apoyo in apoyos:
                    for maestro in buscar_maestros(
                        especialidad_apoyo, None, limite=5,
                    ):
                        if maestro['id'] not in perfiles_usados:
                            maestro = dict(maestro)
                            maestro['rol_en_proyecto'] = (
                                f'Apoyo de {especialidad_apoyo}; no reemplaza al '
                                'especialista en Techumbre.'
                            )
                            maestros_relacionados.append(maestro)
                            perfiles_usados.add(maestro['id'])
                if not techumbristas:
                    mensaje_respuesta += (
                        ' Actualmente no hay un perfil disponible registrado como '
                        'especialista en Techumbre.'
                    )
                if maestros_relacionados and apoyos:
                    mensaje_respuesta += (
                        ' Los perfiles mostrados corresponden solamente a etapas de '
                        'apoyo y no sustituyen al techumbrista.'
                    )
            sugerencias = [
                *(
                    'Buscar instalador SEC de gas'
                    if especialidad == 'Instalaciones de gas · SEC gas'
                    else f'Buscar maestro de {especialidad}'
                    for especialidad in especialidades
                ),
                '¿Qué debo consultar antes de contratarlo?',
            ][:3]
        else:
            mensaje_respuesta = (
                'No puedo determinar una especialidad segura únicamente con los productos '
                'mostrados. Describe brevemente el trabajo principal y te orientaré sin '
                'modificar el proyecto.'
            )
            sugerencias = ['Describir el trabajo principal']
        return {
            'tipo': 'seguimiento_proyecto',
            'mensaje': mensaje_respuesta,
            'productos': [],
            'maestros': maestros_relacionados,
            'sugerencias': sugerencias,
        }
    pide_alternativas = any(frase in texto for frase in (
        'ver alternativas de productos', 'ver alternativas',
        'mostrar alternativas de productos', 'comparar alternativas',
    )) or bool(re.search(
        r'\b(?:ver|mostrar|muestrame|buscar|comparar)\b.{0,30}'
        r'\b(?:alternativas?|opciones?)\b',
        texto,
    ))
    if pide_alternativas:
        return {
            'tipo': 'seguimiento_proyecto',
            'mensaje': (
                '¿Qué deseas comparar de los productos actuales? Puedo buscar opciones '
                'más económicas o ayudarte a cambiar un material específico sin modificar '
                'el resto del proyecto.'
            ),
            'productos': [],
            'maestros': [],
            'sugerencias': [
                'Muéstrame alternativas más económicas',
                'Quiero cambiar el material principal',
                '¿Por qué elegiste estos materiales?',
            ],
        }
    pide_ajuste = any(frase in texto for frase in (
        'ajustar el proyecto', 'ajustar proyecto', 'modificar el proyecto',
        'cambiar el proyecto',
    )) or bool(re.search(
        r'\b(?:ajustar|modificar|cambiar)\b.{0,35}'
        r'\b(?:proyecto|medidas?|material|cubierta|terminacion)\b',
        texto,
    ))
    if pide_ajuste:
        return {
            'tipo': 'seguimiento_proyecto',
            'mensaje': (
                'Indica qué deseas cambiar del proyecto actual. Mantendré todo lo demás '
                'sin modificaciones.'
            ),
            'productos': [],
            'maestros': [],
            'sugerencias': [
                'Quiero cambiar las medidas',
                'Quiero cambiar el material principal',
                'Quiero cambiar la cubierta o terminación',
            ],
        }
    return None


def _resolver_caneria_por_servicio(mensaje):
    """Interpreta el servicio solicitado antes de reutilizar tarjetas anteriores."""
    texto = _texto_normalizado(mensaje)
    pide_canalizacion = bool(re.search(
        r'\b(?:canerias?|tuberias?|tubos?|canos?|ductos?|conduits?|canalizaciones?|canalizacion)\b', texto,
    ))
    if not pide_canalizacion:
        return None

    es_electrica = bool(re.search(
        r'\b(?:electrica|electrico|electricidad|cables?|conductores?)\b', texto,
    ))
    es_agua_potable = bool(re.search(
        r'\b(?:agua potable|aguas limpias|agua limpia|agua fria|agua caliente|'
        r'red de agua|alimentacion de agua)\b', texto,
    ))
    es_sanitaria = bool(re.search(
        r'\b(?:aguas servidas|agua servida|aguas residuales|agua residual|'
        r'aguas grises|agua gris|aguas negras|agua negra|alcantarillado|'
        r'alcantarilla|desague|sanitaria|sanitario|descarga)\b', texto,
    ))
    es_septica = bool(re.search(
        r'\b(?:aguas septicas|agua septica|sistema septico|fosa septica|'
        r'pozo septico|drenaje septico)\b', texto,
    ))
    es_gas = bool(re.search(r'\b(?:gas|gas natural|gas licuado)\b', texto))
    if not any((es_electrica, es_agua_potable, es_sanitaria, es_septica, es_gas)):
        if re.search(r'\b(?:lavaplatos|fregadero)\b', texto):
            return {
                'tipo': 'aclaracion',
                'mensaje': (
                    'En un lavaplatos hay dos conexiones distintas: la alimentación '
                    'lleva agua potable a la grifería, mientras el desagüe y el sifón '
                    'evacuan el agua usada y ayudan a evitar malos olores. '
                    '¿Buscas la cañería de alimentación, la de desagüe o ambas? '
                    'Así podré mostrarte productos del catálogo que correspondan.'
                ),
                'productos': [],
                'maestros': [],
                'sugerencias': ['Alimentación de agua potable', 'Desagüe del lavaplatos', 'Ambas conexiones'],
            }
        if re.search(r'\bagua(?:s)?\b', texto):
            return {
                'tipo': 'aclaracion',
                'mensaje': (
                    '¿La cañería es para alimentar agua limpia o potable, o para '
                    'evacuar aguas servidas por un desagüe? Son redes diferentes y '
                    'no corresponde recomendar el mismo material para ambas.'
                ),
                'productos': [],
                'maestros': [],
                'sugerencias': [
                    'Es para agua potable',
                    'Es para desagüe o aguas servidas',
                    'Es para una fosa séptica',
                ],
            }
        return None

    base = Producto.objects.filter(activo=True, stock__gt=0)
    if es_electrica:
        candidatos = base.filter(nombre__icontains='conduit')
        candidatos = [
            producto for producto in candidatos.order_by('precio', 'nombre', 'pk')
            if 'electrico' in _texto_normalizado(producto.nombre)
        ]
        rol = 'Canalización eléctrica'
        explicacion = (
            'El conduit canaliza y protege los conductores; una cañería de agua o gas '
            'y una llave Stillson no cumplen esa función. El diámetro de 20 o 25 mm '
            'depende de la cantidad y sección de los conductores, del trazado y de si '
            'la instalación será embutida o visible.'
        )
        profesional = 'un instalador eléctrico autorizado'
        sugerencias = [
            '¿Qué diámetro necesito?',
            '¿Qué accesorios necesita el conduit?',
            'Buscar un instalador eléctrico',
        ]
    elif es_agua_potable:
        candidatos = list(base.filter(
            Q(nombre__icontains='Tubo PPR agua potable')
            | Q(nombre__icontains='Tubo cobre tipo L')
        ).order_by('precio', 'nombre', 'pk'))
        rol = 'Conducción de agua potable'
        explicacion = (
            'Para agua limpia o potable encontré alternativas PPR y cobre tipo L. '
            'No son automáticamente intercambiables: el material y diámetro dependen '
            'de si transportará agua fría o caliente, la presión, el trazado y si la '
            'instalación será visible o embutida. El conduit eléctrico y el PVC sanitario '
            'no deben utilizarse para conducir agua potable.'
        )
        profesional = 'un gasfíter o instalador sanitario competente'
        sugerencias = [
            'Es para agua fría',
            'Es para agua fría y caliente',
            'Buscar un maestro de Gasfitería',
        ]
    elif es_septica:
        candidatos = list(base.filter(
            nombre__icontains='Tubo PVC sanitario',
        ).order_by('precio', 'nombre', 'pk'))
        rol = 'Conducción hacia sistema séptico'
        explicacion = (
            'Para conducir aguas residuales hacia una fosa o sistema séptico se utiliza '
            'tubería sanitaria compatible. El diámetro, la pendiente, la ventilación '
            'y el tratamiento final dependen del diseño sanitario y del terreno. Esta '
            'tubería no reemplaza una red de agua potable, un conduit eléctrico ni el '
            'diseño profesional del sistema séptico.'
        )
        profesional = 'un gasfíter o proyectista sanitario competente'
        sugerencias = [
            'Es una descarga domiciliaria',
            'Necesito identificar el diámetro',
            'Buscar un maestro de Gasfitería',
        ]
    elif es_sanitaria:
        candidatos = list(base.filter(
            nombre__icontains='Tubo PVC sanitario',
        ).order_by('precio', 'nombre', 'pk'))
        rol = 'Descarga sanitaria'
        explicacion = (
            'Para aguas servidas o desagüe se utiliza tubería sanitaria compatible. '
            'El diámetro depende del artefacto conectado, el caudal, la pendiente y el '
            'trazado. Esta tubería no reemplaza una red de agua potable ni un conduit eléctrico.'
        )
        profesional = 'un gasfíter o instalador sanitario competente'
        sugerencias = [
            'Es para un lavaplatos o lavamanos',
            'Es para un sanitario',
            'Buscar un maestro de Gasfitería',
        ]
    else:
        candidatos = list(base.filter(
            nombre__icontains='Tubo cobre rígido para gas',
        ).order_by('precio', 'nombre', 'pk'))
        rol = 'Conducción de gas'
        explicacion = (
            'Las redes de gas requieren materiales certificados y un diseño autorizado. '
            'No deben ejecutarse con PPR, PVC sanitario ni conduit eléctrico, y no corresponde '
            'definir el diámetro sin revisar el artefacto, tipo de gas y recorrido.'
        )
        profesional = 'un instalador de gas autorizado por la SEC'
        sugerencias = [
            'Buscar un instalador de gas autorizado',
            'Ver válvulas certificadas para gas',
        ]

    unicos = []
    nombres_vistos = set()
    for producto in candidatos:
        nombre = _texto_normalizado(producto.nombre)
        if nombre in nombres_vistos:
            continue
        nombres_vistos.add(nombre)
        unicos.append(producto)

    productos = []
    for producto in unicos[:6]:
        item = _producto_publico(producto)
        item.update({
            'rol': rol,
            'carrito_cantidad': 1,
            'es_opcional': False,
        })
        productos.append(item)

    if not productos:
        orientacion = ''
        try:
            respuesta_ia = interpretar_con_gemini(
                'Orienta brevemente sobre esta necesidad sin afirmar que SFI tiene '
                'productos disponibles ni inventar precios, stock o compatibilidades. '
                'Menciona el tipo de componente que se usa y qué debe verificarse: '
                + mensaje,
                [],
                [],
            )
            orientacion = ' '.join(str((respuesta_ia or {}).get('respuesta') or '').split())[:520]
        except GeminiNoDisponible:
            pass
        return {
            'tipo': 'sin_resultados',
            'mensaje': (
                f'Identifiqué que buscas una cañería para {rol.casefold()}, pero actualmente '
                'no encontré una alternativa compatible con stock en SFI. El material y '
                f'diámetro deben confirmarse con {profesional}.'
                + (f'\n\nORIENTACIÓN GENERAL\n{orientacion}' if orientacion else
                   '\n\nNo pude obtener orientación adicional de la IA en este momento.')
            ),
            'productos': [],
            'maestros': [],
            'sugerencias': sugerencias,
        }

    return {
        'tipo': 'productos',
        'mensaje': (
            f'Encontré {len(productos)} alternativa(s) para {rol.casefold()} con stock en SFI. '
            f'{explicacion} Antes de comprar o ejecutar el trabajo, confirma el '
            f'dimensionamiento y la instalación con {profesional}.'
        ),
        'productos': productos,
        'maestros': [],
        'sugerencias': sugerencias,
    }


def _es_nueva_consulta_pintura(mensaje):
    """Distingue una búsqueda de pintura de una referencia a tarjetas previas."""
    texto = _texto_normalizado(mensaje)
    familia = bool(re.search(
        r'\b(?:pintura|pinturas|pintar|latex|esmalte|barniz|anticorrosivo)\b',
        texto,
    ))
    if not familia:
        return False
    # "Ese esmalte me sirve" sigue siendo una consulta sobre el producto visible.
    if re.search(
        r'\b(?:este|esta|ese|esa|aquel|aquella|el primero|la primera|'
        r'el segundo|la segunda)\b', texto,
    ):
        return False
    nueva_necesidad = bool(re.search(
        r'\b(?:que tipo|cual|cuales|recomiend\w*|busco|necesito|quiero|'
        r'sirve|sirven|apta|apto|compatible)\b', texto,
    ))
    criterio_nuevo = bool(re.search(
        r'\b(?:madera|metal|fierro|acero|hormigon|concreto|cemento|ladrillo|'
        r'yeso|volcanita|interior|exterior|fachada|piscina|techo|muro|pared)\b',
        texto,
    ))
    return nueva_necesidad or criterio_nuevo


def _resolver_calculo_pintura_local(mensaje, historial):
    """Resuelve cálculos claros de pintura sin depender de Gemini.

    Se limita a una solicitud explícita nueva o a la respuesta inmediata del
    cuestionario de pintura. No interviene en proyectos que solo mencionen
    pintura como uno de sus materiales.
    """
    historial = historial or []
    nueva_consulta = _es_nueva_consulta_pintura(mensaje)
    ultimo_asistente = next((
        _texto_normalizado(item.get('content'))
        for item in reversed(historial)
        if item.get('role') == 'assistant'
    ), '')
    usuarios_recientes = ' '.join(
        _texto_normalizado(item.get('content'))
        for item in historial[-6:]
        if item.get('role') == 'user'
    )
    responde_cuestionario = bool(
        'para calcularlo con precision necesito saber' in ultimo_asistente
        and re.search(
            r'\b(?:pintura|pintar|latex|esmalte|barniz|anticorrosivo)\b',
            usuarios_recientes,
        )
    )
    if not nueva_consulta and not responde_cuestionario:
        return None

    datos = {'intencion': 'calcular_pintura'} if responde_cuestionario else {}
    datos = _aplicar_contexto_calculo_pintura(datos, mensaje, historial)
    if datos.get('intencion') != 'calcular_pintura':
        return None
    return resolver_interpretacion(datos)


def _resolver_consulta_fuera_contexto_sfi(mensaje, historial=None, productos_contexto=None):
    """Detiene solicitudes iniciales ajenas al dominio ferretero de SFI.

    Los seguimientos conservan prioridad porque respuestas breves como "el
    segundo" o "sí, agrégalo" solo tienen sentido junto al contexto previo.
    """
    historial = historial or []
    if historial or productos_contexto:
        return None

    texto = _texto_normalizado(mensaje)
    if not texto:
        return None
    texto_sin_saludo = re.sub(
        r'\b(?:hola|buenos dias|buenas tardes|buenas noches|wenas|buenas)\b',
        ' ', texto,
    ).strip(' ,.!?')
    if not texto_sin_saludo:
        return None

    vocabulario_sfi = re.compile(
        r'\b(?:ferreter\w*|producto\w*|material\w*|herramient\w*|maestr\w*|'
        r'constru\w*|obra\w*|proyecto\w*|repar\w*|arregl\w*|instal\w*|'
        r'mont\w*|armar|fabric\w*|manteni\w*|remodel\w*|cambiar|reemplaz\w*|'
        r'pint\w*|barniz\w*|sell\w*|impermeabil\w*|peg\w*|adhesiv\w*|'
        r'cola fria|silicona\w*|mortero\w*|cement\w*|hormigon\w*|radier\w*|'
        r'ladrill\w*|ceramic\w*|porcelanat\w*|frag\w*|yeso\w*|estuco\w*|'
        r'madera\w*|melamina\w*|mdf|osb|metal\w*|acero\w*|aluminio\w*|'
        r'pvc|policarbonat\w*|zinc\w*|teja\w*|plancha\w*|perfil\w*|'
        r'tornill\w*|clav\w*|perno\w*|tuerca\w*|golilla\w*|fijaci\w*|'
        r'taladr\w*|martill\w*|sierra\w*|esmeril\w*|lija\w*|brocha\w*|'
        r'rodillo\w*|llana\w*|nivel\w*|huincha\w*|cinta metrica|'
        r'techo\w*|techumbre\w*|cubierta\w*|piso\w*|muro\w*|pared\w*|'
        r'puerta\w*|ventana\w*|reja\w*|cerco\w*|porton\w*|escalera\w*|'
        r'mueble\w*|mesa\w*|silla\w*|closet\w*|armario\w*|repisa\w*|'
        r'cocina\w*|bano\w*|lavamanos\w*|lavaplatos\w*|fregadero\w*|sifon\w*|sanitari\w*|ducha\w*|grifer\w*|'
        r'caneria\w*|tuberia\w*|desague\w*|gotera\w*|filtracion\w*|humedad\w*|'
        r'electric\w*|enchufe\w*|interruptor\w*|cable\w*|ampolleta\w*|luz|luces|'
        r'dispositivo\w*|equipo\w*|electronico\w*|alargador\w*|zapatilla\w*|multitoma\w*|'
        r'jardin\w*|riego\w*|manguera\w*|pala\w*|picota\w*|carretilla\w*|'
        r'planta\w*|tutor\w*|maceter\w*|compost\w*|fertiliz\w*|abono\w*|semilla\w*|'
        r'poda\w*|rastrill\w*|huerto\w*|hojas?\w*|'
        r'piscina\w*|quincho\w*|pergola\w*|bodega\w*|cobertizo\w*|terraza\w*|'
        r'candado\w*|cerradura\w*|bisagra\w*|cadena\w*|seguridad\w*)\b'
    )
    if vocabulario_sfi.search(texto):
        return None
    # El catálogo puede incorporar familias nuevas que todavía no figuren en
    # el vocabulario anterior. Una coincidencia real mantiene la consulta dentro
    # del alcance sin inventar productos ni depender solamente de palabras clave.
    if _buscar_productos(mensaje, limite=1):
        return None

    # Muchas consultas válidas no mencionan el nombre comercial: describen la
    # función o ubicación de una pieza ("la pieza que une dos tubos", "lo que
    # sella una junta"). En esos casos dejamos que Gemini identifique el
    # componente y que la búsqueda posterior lo contraste con el catálogo.
    # Exigimos tanto una pregunta funcional como vocabulario de componente para
    # no convertir solicitudes ajenas, como recetas o poemas, en proyectos.
    consulta_funcional = bool(re.search(
        r'\b(?:como se llama|que se llama|para que sirve|que sirve|cual es|'
        r'necesito algo|que va|que une|que conecta|que evita|que tapa|'
        r'que sella|que sostiene|que fija)\b',
        texto,
    ))
    componente_ferretero = bool(re.search(
        r'\b(?:pieza|parte|repuesto|accesorio|componente|conexion|union|'
        r'junta|sello|sellado|adaptador|soporte|fitting|acople|valvula|'
        r'flexible|manguera|tubo|cable|conductor|desague|drenaje|'
        r'filtracion|fuga|olor|humedad|anclaje|bisagra|riel|rueda)\b',
        texto,
    ))
    if consulta_funcional and componente_ferretero:
        return None

    # La ausencia de palabras clave no demuestra que una consulta sea ajena:
    # el cliente puede describir una necesidad de jardinería o una pieza sin
    # conocer su nombre. Gemini interpreta el alcance con el mensaje completo.
    return None


def procesar_consulta(
    mensaje, historial, productos_contexto=None, modo_consulta='auto',
    estimacion_contexto=None,
):
    # Los avisos de riesgo preceden cualquier identificación o búsqueda.
    riesgo = detectar_situacion_cotidiana(mensaje)
    if riesgo and riesgo.get('tipo') == 'riesgo':
        return _resolver_situacion_cotidiana(mensaje)
    ultimo_asistente = next((
        _texto_normalizado(item.get('content')) for item in reversed(historial or [])
        if item.get('role') == 'assistant'
    ), '')
    respuesta_conexion = _texto_normalizado(mensaje).strip(' ¿?.,!')
    if (re.fullmatch(r'(?:no (?:lo )?se|no tengo idea|no estoy segur[oa]|lo desconozco)', respuesta_conexion)
            and any(marca in ultimo_asistente for marca in (
                'antes de recomendar productos', 'sigamos con tu proyecto',
                'necesito estos datos', 'que tipo de teja prefieres',
            ))):
        solicitud = (
            'El cliente no conoce el dato solicitado. Continúa el mismo proyecto usando '
            'el historial, sin repetir el cuestionario. Explica brevemente qué sí puede '
            'considerar y cómo identificar el dato; no lo inventes ni presupongas que '
            'el material, soporte o instalación son compatibles. No afirmes disponibilidad, '
            'stock o precios. Para gas, electricidad o estructura indica revisión profesional. '
            'Si falta un dato crítico mantén la recomendación como orientación general.'
        )
        try:
            orientacion = interpretar_con_gemini(solicitud, historial, productos_contexto or [])
        except GeminiNoDisponible:
            orientacion = None
        respuesta = str((orientacion or {}).get('respuesta') or '').strip()
        return {
            'tipo': 'orientacion',
            'mensaje': respuesta or (
                'Entiendo que no conoces ese dato. Por ahora no puedo determinarlo ni '
                'confirmar la compatibilidad; consulta la ficha del producto o a un '
                'profesional antes de ejecutar el trabajo.'
            ),
            'productos': [], 'maestros': [], 'sugerencias': [],
        }
    usuarios_previos = ' '.join(
        str(item.get('content') or '') for item in (historial or [])
        if item.get('role') == 'user'
    )
    contexto_previo = _texto_normalizado(usuarios_previos)
    if (('piso flotante' in ultimo_asistente or 'piso laminado' in ultimo_asistente)
            and 'alfombra' in contexto_previo
            and re.fullmatch(r'(?:no (?:lo )?se|no tengo idea|no conozco la base)', respuesta_conexion)):
        return {
            'tipo': 'orientacion',
            'mensaje': (
                'No hay problema. La alfombra es el revestimiento que ves; todavía '
                'no sabemos qué base tiene debajo ni si está seca, firme y nivelada.\n\n'
                'Para orientarte: normalmente se retira la alfombra y su bajoalfombra '
                'y se revisa la base antes de colocar la manta y el piso flotante. '
                'No conviene asumir que la alfombra sirve como base: confirma siempre '
                'los requisitos del fabricante del piso. Si observas humedad o daños, '
                'deben revisarse antes de instalar.\n\n'
                'Las cantidades y la compatibilidad '
                'quedan pendientes de verificar; un instalador puede ayudarte a '
                'identificar la base si no puedes hacerlo con seguridad.'
            ),
            'productos': [], 'maestros': [],
            'sugerencias': ['Qué materiales se usan para piso flotante', 'Buscar maestro de pisos'],
        }
    if ('que tipo de teja prefieres' in ultimo_asistente
            and respuesta_conexion in ('arcilla', 'arciilla', 'de arcilla', 'de arciilla', 'terracota', 'colonial')):
        return _resolver_proyecto({
            'proyecto': 'Techumbre estándar de teja de arcilla',
            'tipo_cubierta': 'teja de arcilla',
            '_proyecto_estandar': True,
        })
    if 'buscas la caneria de alimentacion, la de desague o ambas' in ultimo_asistente:
        if respuesta_conexion in ('alimentacion de agua potable', 'alimentacion', 'agua potable'):
            return _resolver_caneria_por_servicio('cañería para agua potable')
        if respuesta_conexion in ('desague del lavaplatos', 'desague'):
            return _resolver_caneria_por_servicio('cañería para desagüe sanitario')
        if respuesta_conexion in ('ambas conexiones', 'ambas', 'las dos'):
            alimentacion = _resolver_caneria_por_servicio('cañería para agua potable')
            desague = _resolver_caneria_por_servicio('cañería para desagüe sanitario')
            productos = alimentacion['productos'] + desague['productos']
            return {
                'tipo': 'productos' if productos else 'sin_resultados',
                'mensaje': (
                    'La alimentación conduce agua potable a la grifería; el desagüe '
                    'evacua el agua usada. Revisa también un sifón compatible con el '
                    'lavaplatos. Los diámetros y conexiones deben confirmarse en la instalación. '
                    + ('Estas son las cañerías relacionadas disponibles en SFI.' if productos else
                       'No encontré cañerías para estas conexiones con stock en SFI.')
                ),
                'productos': productos, 'maestros': [], 'sugerencias': [],
            }
    if (historial or productos_contexto) and re.fullmatch(
        r'(?:eso |esto )?(?:esta mal|es incorrecto|no es correcto)[.!? ]*',
        _texto_normalizado(mensaje).strip(),
    ):
        return {
            'tipo': 'aclaracion',
            'mensaje': 'Gracias por indicarlo. ¿Qué parte de la recomendación es incorrecta? La revisaré antes de volver a recomendar productos.',
            'productos': [],
            'maestros': [],
            'sugerencias': [],
        }
    caneria_por_servicio = _resolver_caneria_por_servicio(mensaje)
    if caneria_por_servicio:
        return caneria_por_servicio
    nueva_consulta_pintura = _es_nueva_consulta_pintura(mensaje)
    calculo_pintura_local = _resolver_calculo_pintura_local(mensaje, historial)
    if calculo_pintura_local:
        return calculo_pintura_local
    # Las descripciones de piezas conocidas deben resolverse antes del filtro
    # general de alcance: frases como "lo que va bajo el lavaplatos" pueden no
    # contener una palabra exacta del catálogo, pero siguen siendo ferretería.
    identificacion_pieza = _resolver_identificacion_pieza(mensaje)
    if identificacion_pieza:
        return identificacion_pieza
    fuera_contexto = _resolver_consulta_fuera_contexto_sfi(
        mensaje, historial, productos_contexto,
    )
    if fuera_contexto:
        return fuera_contexto
    gotera_directa = _resolver_gotera_con_cubierta_identificada(mensaje, historial)
    if gotera_directa:
        return gotera_directa
    # Una pregunta abierta por función necesita interpretación completa: buscar
    # literalmente su descripción puede devolver coincidencias sin relación.
    # Una aclaración iniciada por el propio asistente debe resolverse antes de
    # reclasificar el mensaje breve como un problema cotidiano distinto.
    aclaracion_adhesivo = _aclarar_reparacion_mueble_con_adhesivo(mensaje, historial)
    if aclaracion_adhesivo:
        return aclaracion_adhesivo
    seguimiento_adhesivo = _resolver_seguimiento_reparacion_mueble_adhesivo(
        mensaje, historial,
    )
    if seguimiento_adhesivo:
        return seguimiento_adhesivo
    situacion_cotidiana = _resolver_situacion_cotidiana(mensaje)
    if situacion_cotidiana:
        return situacion_cotidiana
    seguimiento_gotera = _resolver_seguimiento_gotera_techo(mensaje, historial)
    if seguimiento_gotera:
        return seguimiento_gotera
    producto_breve = (
        None if historial or productos_contexto
        else _resolver_producto_breve(mensaje)
    )
    if producto_breve:
        return producto_breve
    diagnostico_filtracion = _resolver_diagnostico_filtracion_inicial(mensaje)
    if diagnostico_filtracion:
        return diagnostico_filtracion
    texto_actual = _texto_normalizado(mensaje)
    contexto_ids = list(dict.fromkeys(productos_contexto or []))
    referencia_singular = bool(re.search(
        r'\b(?:ese|esa|aquel|aquella|el producto|la opcion)\b',
        texto_actual,
    ))
    referencia_posicional = bool(re.search(
        r'\b(?:primer[oa]?|segund[oa]|tercer[oa]?|cuart[oa]|quint[oa]|'
        r'sext[oa]|septim[oa]|octav[oa]|noven[oa]|decim[oa]|'
        r'[1-9][0-9]*(?:er|ro|ra|do|da|to|ta)?)\b',
        texto_actual,
    ))
    if referencia_singular and len(contexto_ids) > 1 and not referencia_posicional:
        return {
            'tipo': 'aclaracion',
            'mensaje': (
                '¿A cuál de los productos mostrados te refieres? Indica su nombre '
                'o su posición para entregarte el dato correcto.'
            ),
            'productos': [],
            'maestros': [],
            'sugerencias': ['El primero', 'El segundo'],
        }
    flujo_natural = _clasificar_seguimiento_natural(
        mensaje,
        productos_contexto or [],
    )
    if re.search(
        r'\b(?:volver|regresar|mostrar|muestrame|ver)\b.{0,30}'
        r'\b(?:resumen|propuesta|proyecto)\b',
        texto_actual,
    ):
        return _resolver_resumen_contextual(historial)
    if flujo_natural == 'total':
        return _resolver_total_contextual(historial)
    mensaje_economico = (
        'Muéstrame alternativas más económicas'
        if flujo_natural == 'economico' else mensaje
    )
    comparacion_economica = _comparar_alternativas_economicas(
        mensaje_economico,
        productos_contexto or [],
        estimacion_contexto or [],
    )
    if comparacion_economica:
        return comparacion_economica
    mensajes_accion = {
        'herramientas': '¿Qué herramientas necesito para este proyecto?',
        'profesional': '¿Qué maestro necesito para este proyecto?',
        'alternativas': 'Ver alternativas de productos',
        'ajuste': 'Ajustar el proyecto',
    }
    accion_seguimiento = _resolver_accion_seguimiento(
        mensajes_accion.get(flujo_natural, mensaje),
        productos_contexto or [],
    )
    if accion_seguimiento:
        return accion_seguimiento
    mensaje_explicacion = (
        '¿Por qué elegiste estos materiales?'
        if flujo_natural == 'explicacion' else mensaje
    )
    explicacion_contextual = None
    if not nueva_consulta_pintura:
        explicacion_contextual = _explicar_productos_mostrados(
            mensaje_explicacion,
            historial,
            productos_contexto or [],
        )
    if explicacion_contextual:
        return explicacion_contextual
    explicacion_faltantes = _explicar_faltantes_del_proyecto(
        mensaje,
        historial,
        productos_contexto or [],
    )
    if explicacion_faltantes:
        return explicacion_faltantes
    cuestionario_pendiente = None
    if not nueva_consulta_pintura:
        cuestionario_pendiente = _mantener_cuestionario_antes_de_recomendar(
            mensaje, historial,
        )
    if cuestionario_pendiente:
        return cuestionario_pendiente
    mensaje_para_ia = _mensaje_para_continuar_guia(mensaje, historial)
    historial_interpretacion = historial
    productos_interpretacion = productos_contexto or []
    if nueva_consulta_pintura:
        mensaje_para_ia = (
            'INICIA UNA NUEVA CONSULTA DE PINTURA. No expliques ni reutilices los '
            'productos de la consulta anterior. Interpreta la superficie, ambiente, '
            f'estado, color y cantidad solicitados en este mensaje: {mensaje}'
        )
        historial_interpretacion = []
        productos_interpretacion = []
    contextos_iniciales = {
        'producto': (
            'El cliente inició la consulta desde Buscar un producto. '
            'Orienta primero la interpretación a identificar nombre, uso, marca, '
            'característica o presupuesto.'
        ),
        'herramienta': (
            'El cliente inició la consulta desde Elegir una herramienta. '
            'Orienta primero la interpretación al trabajo, material y frecuencia de uso.'
        ),
        'proyecto_reparacion': (
            'El cliente inició la consulta desde Proyecto o reparación. '
            'Orienta primero la interpretación al objetivo, condiciones y medidas necesarias.'
        ),
        'problema_cotidiano': (
            'El cliente indicó que no sabe qué necesita. Interpreta primero el problema '
            'cotidiano y solicita solo los datos indispensables antes de recomendar.'
        ),
    }
    contexto_inicial = contextos_iniciales.get(modo_consulta)
    if contexto_inicial:
        mensaje_para_ia = (
            f'{contexto_inicial} Esta ruta es solo una orientación inicial: si el mensaje '
            f'actual expresa otra intención, prioriza el mensaje.\n\n{mensaje_para_ia}'
        )
    try:
        interpretacion = interpretar_con_gemini(
            mensaje_para_ia, historial_interpretacion, productos_interpretacion,
        )
    except GeminiNoDisponible as exc:
        raise AsistenteNoDisponible(str(exc)) from exc
    interpretacion = _normalizar_preferencias_extraidas(
        interpretacion,
        mensaje,
        historial,
    )
    interpretacion = _aplicar_contexto_calculo_pintura(
        interpretacion, mensaje, historial_interpretacion,
    )
    if _plan_estandar_incompleto(interpretacion):
        proyecto = str(interpretacion.get('proyecto') or mensaje).strip()
        tareas_iniciales = list(interpretacion.get('tareas_proyecto') or [])
        componentes_iniciales = [
            str(busqueda).strip()
            for tarea in tareas_iniciales if isinstance(tarea, dict)
            for busqueda in (tarea.get('busquedas') or [])
            if str(busqueda).strip()
        ]
        solicitud_completa = (
            'REVISA LA COBERTURA DEL PROYECTO SIN RECONSTRUIRLO. '
            f'Proyecto: {proyecto}. Ya están considerados estos componentes: '
            f'{", ".join(componentes_iniciales) or "ninguno"}. '
            'Devuelve solamente componentes relevantes que falten, agrupados por etapa. '
            'Revisa de forma general: preparación, estructura o soporte, uniones y fijaciones, '
            'conexiones, sellado o protección, terminaciones, drenaje cuando aplique, seguridad '
            'y herramientas específicas. No repitas los componentes ya cubiertos, no inventes '
            'productos ni asumas que están disponibles; Django verificará el catálogo.'
        )
        try:
            propuesta_completa = interpretar_con_gemini(
                solicitud_completa,
                [*historial, {'role': 'user', 'content': mensaje}],
                productos_contexto or [],
            )
        except GeminiNoDisponible:
            propuesta_completa = None
        if isinstance(propuesta_completa, dict):
            for campo in (
                'proyecto', 'ancho_cm', 'fondo_cm', 'alto_cm', 'superficie',
                'superficie_muros', 'material_principal_proyecto',
                'material_estructura', 'estado_estructura', 'tipo_cubierta',
                'alcance_bano', 'comuna_maestro',
            ):
                if not propuesta_completa.get(campo) and interpretacion.get(campo):
                    propuesta_completa[campo] = interpretacion[campo]
            existentes = {
                _texto_normalizado(busqueda)
                for tarea in tareas_iniciales if isinstance(tarea, dict)
                for busqueda in (tarea.get('busquedas') or [])
            }
            tareas_combinadas = list(tareas_iniciales)
            for tarea in propuesta_completa.get('tareas_proyecto') or []:
                if not isinstance(tarea, dict):
                    continue
                busquedas_nuevas = [
                    busqueda for busqueda in (tarea.get('busquedas') or [])
                    if _texto_normalizado(busqueda) not in existentes
                ]
                if not busquedas_nuevas:
                    continue
                existentes.update(_texto_normalizado(busqueda) for busqueda in busquedas_nuevas)
                tareas_combinadas.append({**tarea, 'busquedas': busquedas_nuevas})
            # El planificador admite hasta doce etapas. Limitar esta fusión a
            # ocho podía descartar silenciosamente iluminación, drenaje o
            # seguridad en proyectos grandes.
            propuesta_completa['tareas_proyecto'] = tareas_combinadas[:12]
            propuesta_completa['herramientas_proyecto'] = list(dict.fromkeys([
                *(interpretacion.get('herramientas_proyecto') or []),
                *(propuesta_completa.get('herramientas_proyecto') or []),
            ]))[:3]
            propuesta_completa['modo_orientacion'] = (
                'propuesta_estandar'
                if interpretacion.get('_proyecto_estandar') is True
                else 'propuesta_directa'
            )
            interpretacion = _normalizar_preferencias_extraidas(
                propuesta_completa,
                mensaje,
                historial,
            )
    interpretacion = _completar_intencion_maestro(
        interpretacion,
        mensaje,
        historial,
    )
    continua_proyecto = _continuar_dato_pendiente_proyecto(
        interpretacion, mensaje, historial,
    )
    if not continua_proyecto:
        interpretacion = _aplicar_contexto_productos(
            interpretacion, mensaje, productos_contexto,
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
