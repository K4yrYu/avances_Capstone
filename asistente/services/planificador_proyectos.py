import re
import unicodedata
from decimal import Decimal, ROUND_CEILING

from maestros.models import Especialidad
from productos.models import Producto


MAX_TAREAS = 12
MAX_BUSQUEDAS = 36
MAX_ESPECIALIDADES = 3
MAX_MAESTROS = 5


# Gemini puede describir correctamente la función de un componente usando un
# nombre genérico, mientras que el catálogo lo comercializa con otra familia o
# medida. Estos equivalentes NO crean productos: solo abren búsquedas locales
# adicionales antes de decidir que el componente no está disponible.
_EQUIVALENCIAS_FUNCIONALES_CATALOGO = (
    (
        ('caja', 'derivacion', 'estanca'),
        ('caja estanca electrica',),
    ),
    (
        ('luces', 'suelo', 'exterior'),
        ('estaca LED jardin exterior',),
    ),
    (
        ('luminaria', 'suelo', 'exterior'),
        ('estaca LED jardin exterior',),
    ),
    (
        ('luz', 'jardin', 'exterior'),
        ('estaca LED jardin exterior',),
    ),
    (
        ('luminaria', 'muro', 'exterior'),
        ('aplique LED exterior',),
    ),
    (
        ('foco', 'exterior'),
        ('reflector LED exterior',),
    ),
    (
        ('madera', 'dimensionada'),
        ('pino dimensionado 2 x 4 pulgadas', 'pino dimensionado 2 x 6 pulgadas'),
    ),
    (
        ('madera', 'estructural'),
        ('pino dimensionado 2 x 4 pulgadas', 'tablero OSB estructural'),
    ),
    (
        ('fijacion', 'madera'),
        ('tornillo estructural para madera', 'escuadra metalica reforzada'),
    ),
    (
        ('tornillo', 'madera'),
        ('tornillo estructural para madera', 'tornillos para madera'),
    ),
    (
        ('anclaje', 'hormigon'),
        ('perno anclaje expansion M12 x 120 mm', 'kit fijacion para hormigon y ladrillo'),
    ),
    (
        ('sombra',),
        ('malla raschel sombra 80%', 'policarbonato alveolar'),
    ),
    (
        ('cubierta', 'sombra'),
        ('malla raschel sombra 80%', 'policarbonato alveolar'),
    ),
    (
        ('zinc', 'ondulado'),
        ('plancha zinc acanalado 0,35 mm x 3 m',),
    ),
    (
        ('zinc', 'galvanizado'),
        ('plancha zinc acanalado 0,35 mm x 3 m',),
    ),
    (
        ('sellado', 'techumbre'),
        ('cinta butilica impermeable', 'tapagoteras acrilico impermeabilizante'),
    ),
    (
        ('sellador', 'techo'),
        ('cinta butilica impermeable', 'tapagoteras acrilico impermeabilizante'),
    ),
    (
        ('canalizacion', 'electrica'),
        ('conduit PVC electrico 20 mm', 'caja estanca electrica'),
    ),
    (
        ('proteccion', 'electrica'),
        ('interruptor automatico 16 A curva C', 'interruptor diferencial 25 A 30 mA'),
    ),
    (
        ('conexion', 'agua'),
        ('flexible agua HI-HI 1/2 pulgada', 'cinta PTFE teflon'),
    ),
    # Techumbre, madera y construcción.
    (
        ('lamina', 'zinc'),
        ('plancha zinc acanalado 0,35 mm x 3 m',),
    ),
    (
        ('techo', 'metalico'),
        ('plancha zinc acanalado 0,35 mm x 3 m',),
    ),
    (
        ('malla', 'sombra'),
        ('malla raschel sombra 80%',),
    ),
    (
        ('protector', 'madera'),
        ('impregnante protector madera exterior', 'barniz al agua para madera'),
    ),
    (
        ('cemento', 'radier'),
        ('hormigon predosificado H20 saco 25 kg', 'base estabilizada para radier'),
    ),
    (
        ('malla', 'radier'),
        ('malla electrosoldada C92 panel 2,6 x 5 m',),
    ),
    # Redes de agua, gasfitería y riego.
    (
        ('llave', 'paso', 'gas'),
        ('valvula corte gas bronce 1/2 pulgada',),
    ),
    (
        ('llave', 'paso', 'agua'),
        ('valvula bola bronce 1/2 pulgada',),
    ),
    (
        ('teflon',),
        ('cinta PTFE teflon 12 mm x 12 m',),
    ),
    (
        ('manguera', 'goteo'),
        ('manguera riego por goteo 16 mm x 25 m',),
    ),
    (
        ('tubo', 'riego'),
        ('tubo polietileno para riego 16 mm x 50 m',),
    ),
    (
        ('emisor', 'riego'),
        ('gotero regulable para riego por goteo pack 10',),
    ),
    # Electricidad: palabras habituales de clientes para los productos reales.
    (
        ('toma', 'corriente'),
        ('enchufe doble embutido 16 A blanco',),
    ),
    (
        ('tomacorriente',),
        ('enchufe doble embutido 16 A blanco',),
    ),
    (
        ('breaker',),
        ('interruptor automatico 16 A curva C',),
    ),
    (
        ('termica',),
        ('interruptor automatico 16 A curva C',),
    ),
    (
        ('automatico', 'tablero'),
        ('interruptor automatico 16 A curva C',),
    ),
    (
        ('proteccion', 'diferencial'),
        ('interruptor diferencial 25 A 30 mA',),
    ),
    (
        ('empalme', 'electrico'),
        ('conector rapido electrico 3 polos pack 10', 'caja estanca electrica 100 x 100 mm'),
    ),
    # Terminaciones, herramientas y jardín.
    (
        ('pasta', 'muro'),
        ('pasta muro interior saco 15 kg',),
    ),
    (
        ('retape',),
        ('pasta de retape interior 1 kg',),
    ),
    (
        ('espaciar', 'ceramica'),
        ('separadores para ceramica 3 mm pack 100',),
    ),
    (
        ('junta', 'ceramica'),
        ('frague flexible gris bolsa 2 kg',),
    ),
    (
        ('sacar', 'tierra'),
        ('pala punta huevo mango fibra',),
    ),
    (
        ('mover', 'hojas'),
        ('rastrillo plastico para hojas 22 dientes',),
    ),
    (
        ('picar', 'piedra'),
        ('picota acero 2,5 kg mango fibra',),
    ),
    (
        ('tijera', 'podar'),
        ('tijera de poda bypass 8 pulgadas',),
    ),
    (
        ('tijeras', 'podar'),
        ('tijera de poda bypass 8 pulgadas',),
    ),
    (
        ('amarras', 'jardin'),
        ('amarras plasticas para jardin 20 cm pack 50',),
    ),
    (
        ('amarras', 'plantas'),
        ('amarras plasticas para jardin 20 cm pack 50',),
    ),
    (
        ('puerta', 'exterior', 'bodega'),
        ('puerta exterior de acero 80 x 200 cm',),
    ),
    (
        ('bisagra', 'reforzada', 'puerta'),
        ('bisagra puerta acero zincado 3 pulgadas',),
    ),
    (
        ('barrera', 'humedad', 'solera'),
        ('polietileno construccion 200 micras 4 x 25 m',),
    ),
)


def _normalizar(valor):
    texto = unicodedata.normalize("NFKD", str(valor or "").casefold())
    return " ".join(
        "".join(
            caracter for caracter in texto
            if not unicodedata.combining(caracter)
        ).split()
    )


def _texto_seguro(valor, limite):
    return " ".join(str(valor or "").strip().split())[:limite]


def _formatear_clp(valor):
    return f"${int(valor):,}".replace(",", ".")


def _palabras_consulta(consulta):
    omitidas = {'para', 'con', 'del', 'las', 'los', 'una', 'uno', 'por'}
    palabras = [
        palabra for palabra in re.findall(r'[a-z0-9-]+', _normalizar(consulta))
        if len(palabra) >= 3 and palabra not in omitidas
    ]
    equivalencias = {
        'roja': 'rojo', 'blanca': 'blanco', 'negra': 'negro',
        'amarilla': 'amarillo',
    }
    return [equivalencias.get(palabra, palabra) for palabra in palabras]


def _consultas_catalogo_equivalentes(consulta):
    """Devuelve búsquedas reales para un componente funcional de Gemini."""
    normalizada = _normalizar(consulta)
    resultado = [consulta]
    for claves, equivalentes in _EQUIVALENCIAS_FUNCIONALES_CATALOGO:
        if all(clave in normalizada for clave in claves):
            resultado.extend(equivalentes)
    return _lista_textos(resultado, 5, 80)


def _separar_componentes_compuestos(componentes):
    """Separa solo combinaciones frecuentes que son productos distintos."""
    resultado = []
    for componente in componentes:
        normalizado = _normalizar(componente)
        if 'pala' in normalizado and 'carretilla' in normalizado:
            resultado.extend([
                'pala punta huevo mango fibra',
                'carretilla acero 90 L rueda neumatica',
            ])
            continue
        resultado.append(componente)
    return _lista_textos(resultado, 8, 80)


def _textos_producto(producto):
    nombre = _normalizar(producto.nombre)
    identificacion = _normalizar(
        ' '.join([
            producto.sku or '', producto.marca, producto.categoria,
            producto.color, producto.tipo_pintura, producto.terminacion,
        ])
    )
    detalle = _normalizar(
        ' '.join([
            producto.descripcion,
            producto.uso_recomendado,
            str(producto.especificaciones or {}),
        ])
    )
    return nombre, identificacion, detalle


def _coincidencias_directas(producto, consulta):
    palabras = _palabras_consulta(consulta)
    textos = ' '.join(_textos_producto(producto))
    return sum(
        bool(re.search(rf'\b{re.escape(palabra)}\w*', textos))
        for palabra in palabras
    )


def _puntaje_directo(producto, consulta):
    palabras = _palabras_consulta(consulta)
    nombre, identificacion, detalle = _textos_producto(producto)
    puntaje = 8 if _normalizar(consulta) in nombre else 0
    for palabra in palabras:
        patron = rf'\b{re.escape(palabra)}\w*'
        if re.search(patron, nombre):
            puntaje += 5
        elif re.search(patron, identificacion):
            puntaje += 3
        elif re.search(patron, detalle):
            puntaje += 1
    return puntaje


def _coincidencia_suficiente(producto, consulta):
    palabras = _palabras_consulta(consulta)
    cantidad_palabras = len(palabras)
    # Son términos demasiado polisémicos para identificar por sí solos un
    # producto. Por ejemplo, "llaves" no convierte un candado en herramienta
    # de gasfitería y "kit" no define qué clase de kit necesita el proyecto.
    ambiguas = {'llave', 'llaves', 'kit', 'juego', 'set', 'pieza', 'piezas'}
    if cantidad_palabras == 1 and palabras[0] in ambiguas:
        return False
    minimo = min(cantidad_palabras, 3)
    return _coincidencias_directas(producto, consulta) >= minimo


def _candidatos_directos(consulta):
    candidatos = [
        producto for producto in Producto.objects.filter(activo=True)
        if _puntaje_directo(producto, consulta) > 0
    ]
    candidatos.sort(key=lambda producto: (
        -_puntaje_directo(producto, consulta),
        producto.precio,
        producto.nombre.casefold(),
    ))
    return candidatos[:20]


def _producto_incompatible_con_gas(producto):
    """Evita que coincidencias genéricas mezclen gas con artefactos sanitarios."""
    texto = _normalizar(' '.join([
        producto.nombre,
        producto.categoria,
        producto.descripcion,
        producto.uso_recomendado,
    ]))
    return any(termino in texto for termino in (
        'sanitario', 'inodoro', 'lavamanos', 'lavaplatos', 'ducha',
        'sifon', 'desague', 'wc ',
    ))


def _es_herramienta_equivalente_ya_elegida(candidato, productos_elegidos):
    """Evita repetir herramientas de la misma familia en etapas distintas.

    Un plan puede separar "Herramientas" y "Herramientas recomendadas". Si
    ambas búsquedas recuperan dos palas, al cliente le basta con la mejor
    coincidencia: no se deben presentar como herramientas diferentes.
    """
    familias = (
        'pala', 'tijera', 'serrucho', 'taladro', 'sierra', 'martillo',
        'picota', 'barreta', 'rastrillo', 'llana', 'espatula', 'cortatubo',
        'alicate', 'destornillador', 'nivel', 'cinta metrica',
    )
    def contiene_familia(texto, familia):
        # "nivel" es una herramienta; "nivelador" y "cuñas niveladoras" son
        # componentes distintos del sistema de colocación.
        if familia == 'nivel':
            return bool(re.search(r'\bnivel\b', texto))
        return familia in texto

    def familia_herramienta(texto):
        familia = next((
            familia for familia in familias
            if contiene_familia(texto, familia)
        ), None)
        if familia == 'llana':
            if 'goma' in texto or 'frague' in texto:
                return 'llana_goma'
            if 'dentada' in texto:
                return 'llana_dentada'
        return familia

    nombre_candidato = _normalizar(candidato.nombre)
    familia = familia_herramienta(nombre_candidato)
    if not familia:
        return False

    return any(
        familia_herramienta(_normalizar(producto.get('nombre'))) == familia
        for producto in productos_elegidos
    )


def _lista_textos(valores, maximo, limite=100):
    if not isinstance(valores, list):
        return []
    resultado = []
    vistos = set()
    for valor in valores:
        texto = _texto_seguro(valor, limite)
        clave = _normalizar(texto)
        if texto and clave not in vistos:
            vistos.add(clave)
            resultado.append(texto)
        if len(resultado) >= maximo:
            break
    return resultado


def _preguntas_guiadas(faltantes, proyecto=''):
    """Convierte requisitos técnicos en preguntas que un cliente pueda responder."""
    lineas = []
    contexto = _normalizar(proyecto)
    for indice, faltante in enumerate(faltantes, start=1):
        pregunta = faltante.strip().lstrip("¿").rstrip("?.")
        clave = _normalizar(pregunta)
        lineas.extend(["", f"{indice}. {pregunta.upper()}"])
        if "quincho" in contexto and "base existente" in clave:
            lineas.extend([
                "• Indica si ya existe un radier o losa firme donde se construirá.",
                "• Si se hará desde terreno natural, escribe “no existe radier”.",
            ])
        elif "quincho" in contexto and "diseno general" in clave:
            lineas.extend([
                "• Abierto: sin cerramientos laterales permanentes.",
                "• Semiabierto: con uno o más lados protegidos.",
                "• Cerrado: con cerramientos en todo el perímetro.",
            ])
        elif "quincho" in contexto and "altura aproximada" in clave:
            lineas.extend([
                "• Indica la altura aproximada en metros; por ejemplo: 2,4 m.",
                "• Si variará por la pendiente, informa la altura menor y la mayor.",
            ])
        elif (
            "quincho" in contexto
            and "estructura" in clave
            and "cubierta" in clave
        ):
            lineas.extend([
                "• Indica si prefieres estructura de madera o metal.",
                "• Para la cubierta puedes elegir zinc, policarbonato o tejas.",
                "• Si no tienes preferencia, escribe “elige tú ambos materiales”.",
            ])
        elif (
            any(termino in contexto for termino in ("mueble", "gabinete"))
            and "tipo" in clave
            and "mueble" in clave
        ):
            lineas.extend([
                "• Indica su función: clóset, escritorio, estante, mueble de cocina, baño, TV u otro.",
                "• Si no conoces el nombre, explica qué necesitas guardar o hacer en él.",
                "• El tipo no se elegirá automáticamente porque define su estructura y herrajes.",
            ])
        elif (
            any(termino in contexto for termino in ("mueble", "gabinete"))
            and "material" in clave
        ):
            lineas.extend([
                "• Puedes elegir melamina, MDF, terciado, pino u otro material disponible.",
                "• Si no tienes preferencia, escribe “elige tú el material” y compararé opciones compatibles.",
            ])
        elif "material" in clave and "estado" in clave and "estructura" in clave:
            lineas.extend([
                "• Indica si la estructura es de madera, metal, hormigón u otro material.",
                "• Señala si está firme y reutilizable, necesita reparación o será reemplazada.",
                "• Si será nueva, agrega la altura aproximada en metros.",
                "• Si no sabes evaluarla, describe si ves humedad, grietas, deformaciones o piezas sueltas.",
            ])
        elif "vano" in clave or (
            "puerta" in clave
            and any(termino in clave for termino in ("medida", "ancho", "alto"))
        ):
            lineas.extend([
                "• Indica ancho × alto en centímetros; por ejemplo: 80 × 200 cm.",
                "• Mide el vano en la parte superior, central e inferior y usa la medida menor.",
                "• Indica también el espesor del muro o marco si lo conoces.",
                "• Si no puedes medirlo con precisión, entrega una medida aproximada y acláralo.",
            ])
        elif "puerta" in clave and any(
            termino in clave for termino in ("interior", "exterior", "ubicacion")
        ):
            lineas.extend([
                "• Interior seco: dormitorio, living, pasillo u oficina.",
                "• Interior húmedo: baño, lavadero o recinto con vapor frecuente.",
                "• Exterior: indica si queda protegida o recibe lluvia y sol directo.",
                "• Señala si cambiarás solo la hoja o también el marco.",
            ])
        elif "marco" in clave and "estado" in clave:
            lineas.extend([
                "• Bueno: está firme, derecho y sin humedad ni partes sueltas.",
                "• Deteriorado: está deformado, podrido, oxidado o se mueve.",
                "• Indica si deseas conservarlo o reemplazarlo junto con la puerta.",
                "• Si no lo sabes, indica si el marco se mueve, está deformado o presenta humedad.",
            ])
        elif "estado" in clave:
            lineas.extend([
                "• Bueno: firme, seco, nivelado y sin daños visibles.",
                "• Regular: tiene daños o desniveles menores.",
                "• Malo: presenta humedad, grietas, piezas sueltas o deformación.",
                "• No lo sé: describe si ves humedad, grietas, piezas sueltas o deformación.",
            ])
        elif any(termino in clave for termino in ("medida", "ancho", "largo", "alto", "altura", "superficie", "area")):
            if any(termino in contexto for termino in ("mueble", "repisa", "estante", "gabinete")):
                lineas.extend([
                    "• Indica ancho × alto × fondo en centímetros; por ejemplo: 120 × 80 × 35 cm.",
                    "• Señala si las medidas corresponden al espacio disponible o al mueble terminado.",
                    "• Si hay obstáculos, indica su posición y sus medidas aproximadas.",
                ])
            elif any(termino in contexto for termino in ("cerco", "reja", "cierre", "porton")):
                lineas.extend([
                    "• Indica largo total × altura en metros; por ejemplo: 12 × 1,80 m.",
                    "• Señala cuántas esquinas, accesos o cambios de nivel existen.",
                    "• Si el recorrido es irregular, entrega el largo de cada tramo.",
                ])
            else:
                lineas.extend([
                    "• Indica ancho × largo y su unidad; por ejemplo: 3 × 4 metros.",
                    "• Si la forma es irregular, entrega las medidas de cada tramo.",
                    "• No lo sé: mide de forma aproximada y aclara que es una estimación.",
                ])
        elif "cubierta" in clave and any(
            termino in clave for termino in ("material", "formato", "espesor", "tipo")
        ):
            lineas.extend([
                "• Indica si prefieres zinc, policarbonato, tejas u otra cubierta.",
                "• Si ya conoces el formato o espesor, agrégalo en la misma respuesta.",
                "• Si no tienes preferencia, escribe “elige tú” y compararé opciones compatibles disponibles.",
            ])
        elif any(termino in clave for termino in ("material", "base", "soporte", "estructura", "superficie")):
            lineas.extend([
                "• Describe lo que ves: hormigón, madera/OSB, metal, cerámica u otro.",
                "• No lo sé: describe su color, textura, dureza y cómo suena al golpear suavemente.",
            ])
        elif any(termino in clave for termino in ("ambiente", "ubicacion", "exterior", "interior", "humedad", "exposicion")):
            lineas.extend([
                "• Indica si es interior, exterior o una zona húmeda.",
                "• Si es exterior, menciona si recibe lluvia o sol directo.",
                "• No lo sé: indica la habitación o lugar donde se realizará el trabajo.",
            ])
        elif any(termino in clave for termino in ("acabado", "terminacion", "color", "estilo", "formato", "espesor", "tipo")):
            lineas.extend([
                "• Indica tu preferencia si ya la conoces.",
                "• No lo sé: escribe “elige tú” y seleccionaré una opción compatible del catálogo.",
            ])
        elif any(termino in clave for termino in ("presupuesto", "monto", "precio")):
            lineas.extend([
                "• Indica un máximo aproximado en pesos chilenos.",
                "• No lo sé: escribe “sin presupuesto definido” y compararé alternativas.",
            ])
        else:
            lineas.extend([
                "• Responde con la información que conozcas.",
                "• No lo sé: describe el resultado que buscas con tus propias palabras.",
            ])
    return lineas


def _sugerencias_respuesta(proyecto, faltantes):
    """Entrega ejemplos de respuesta útiles, nunca acciones ajenas al cuestionario."""
    contexto = _normalizar(proyecto)
    claves = " ".join(_normalizar(item) for item in faltantes)

    if "quincho" in contexto:
        if len(faltantes) > 1:
            return [
                (
                    "Mide 3 × 4 m; existe un radier firme; será semiabierto; "
                    "tendrá 2,4 m de altura; estructura metálica y cubierta de zinc"
                ),
                (
                    "Mide 3 × 4 m; no existe radier; será abierto; tendrá 2,4 m; "
                    "elige tú la estructura y la cubierta"
                ),
            ]
        if any(termino in claves for termino in ("ancho", "largo")):
            return ["El quincho medirá 3 × 4 m"]
        if "base existente" in claves:
            return [
                "Ya existe un radier firme y reutilizable",
                "Se construirá desde terreno natural; no existe radier",
            ]
        if "diseno general" in claves:
            return ["Será abierto", "Será semiabierto", "Será cerrado"]
        if "altura aproximada" in claves:
            return ["Tendrá aproximadamente 2,4 m de altura"]
        if "estructura" in claves and "cubierta" in claves:
            return [
                "Estructura metálica y cubierta de zinc",
                "Estructura de madera y cubierta de policarbonato",
                "Elige tú ambos materiales",
            ]

    if any(termino in contexto for termino in ("techo", "techumbre", "cubierta")):
        partes = []
        if any(termino in claves for termino in ("medida", "ancho", "largo", "area")):
            partes.append("Mide 3 × 4 m")
        if "estructura" in claves:
            partes.append("la estructura es de madera y está firme")
        if any(termino in claves for termino in ("cubierta", "policarbonato", "formato", "espesor")):
            partes.append("elige tú una cubierta compatible")
        sugerencias = ["; ".join(partes)] if partes else []
        if "estructura" in claves:
            sugerencias.append("No sé evaluarla; veo la estructura firme y sin daños visibles")
        sugerencias.append("Usa una opción estándar disponible y deja lo estructural como referencia")
        return [item for item in sugerencias if item][:3]

    if any(termino in contexto for termino in ("puerta", "ventana")):
        return [
            "Es interior seco; el vano mide 80 × 200 cm; cambiaré hoja y marco",
            "Es exterior protegida; mide 90 × 200 cm; conservaré el marco",
            "No sé evaluarlo; el marco no se mueve y no veo humedad",
        ]
    if any(termino in contexto for termino in ("mueble", "repisa", "estante", "gabinete")):
        return [
            "Necesito un clóset para guardar ropa; el espacio mide 120 × 200 × 55 cm",
            "Quiero un escritorio; el espacio mide 120 × 75 × 60 cm",
            "Necesito un estante para libros; elige tú el material",
        ]
    if any(termino in contexto for termino in ("cerco", "reja", "cierre", "porton")):
        return [
            "Son 12 m de largo × 1,80 m de alto; terreno plano y un acceso",
            "El recorrido tiene dos tramos; enviaré las medidas de cada uno",
            "Elige tú un sistema estándar disponible",
        ]
    if any(termino in contexto for termino in ("piso", "terraza", "radier")):
        return [
            "Mide 3 × 5 m; la base es de hormigón firme y seca",
            "Es exterior y recibe lluvia; elige tú una opción compatible",
            "No sé identificar la base; describiré su color, textura y estado",
        ]

    return [
        "Responderé las medidas y condiciones en un solo mensaje",
        "Elige tú las preferencias no críticas con productos disponibles",
        "No sé identificarlo; describiré lo que veo",
    ]


def _es_proyecto_mueble(proyecto):
    contexto = _normalizar(proyecto)
    return any(termino in contexto for termino in (
        'mueble', 'closet', 'ropero', 'armario', 'escritorio', 'estante',
        'repisero', 'biblioteca', 'rack', 'zapatero', 'velador', 'cajonera',
        'despensa',
    ))


def _tiene_tipo_mueble(proyecto):
    """Distingue el uso funcional del material o del adjetivo 'estándar'."""
    contexto = _normalizar(proyecto)
    tipos = (
        'closet', 'ropero', 'armario', 'escritorio', 'estante', 'repisero',
        'biblioteca', 'rack', 'televisor', 'zapatero', 'velador', 'cajonera',
        'comoda', 'despensa', 'mueble de cocina', 'mueble cocina',
        'mueble de bano', 'mueble bano', 'mueble lavamanos', 'vanitorio',
        'mesa de trabajo', 'meson de trabajo',
    )
    usos = (
        'guardar ropa', 'guardar zapatos', 'guardar libros', 'guardar vajilla',
        'organizar cocina', 'trabajar', 'estudiar', 'para la television',
        'para tv',
    )
    return any(termino in contexto for termino in (*tipos, *usos))


def _herramienta_reconocible(nombre):
    """Evita publicar como faltante un nombre de herramienta inventado por la IA."""
    texto = _normalizar(nombre)
    familias_reconocibles = (
        'alicate', 'atornillador', 'azadon', 'brocha', 'buscador de cables',
        'carretilla', 'cincel', 'combo', 'cortador', 'destornillador',
        'escalera', 'escuadra', 'esmeril', 'formon', 'guante', 'huincha',
        'lija', 'lijadora', 'llave', 'martillo', 'mascara', 'mascarilla',
        'mazo', 'nivel', 'pala', 'picota', 'pinza', 'protector', 'rastrillo',
        'rodillo', 'serrucho', 'sierra', 'taladro', 'tester', 'tijera',
    )
    return any(familia in texto for familia in familias_reconocibles)


def _extraer_tareas(datos):
    tareas_crudas = datos.get("tareas_proyecto")
    if not isinstance(tareas_crudas, list):
        return []

    tareas = []
    total_busquedas = 0
    for tarea in tareas_crudas[:MAX_TAREAS]:
        if not isinstance(tarea, dict):
            continue
        nombre = _texto_seguro(tarea.get("nombre"), 100)
        busquedas = _separar_componentes_compuestos(
            _lista_textos(tarea.get("busquedas"), 5, 80)
        )
        usos = {}
        for indice, item in enumerate(tarea.get("usos_materiales") or []):
            if isinstance(item, dict):
                busqueda_uso = _texto_seguro(item.get("busqueda"), 80)
                uso = _texto_seguro(item.get("uso"), 180)
            else:
                busqueda_uso = busquedas[indice] if indice < len(busquedas) else ''
                uso = _texto_seguro(item, 180)
            if busqueda_uso and uso:
                usos[_normalizar(busqueda_uso)] = uso
        bases = {}
        for indice, base in enumerate(tarea.get("bases_calculo") or []):
            if indice >= len(busquedas):
                break
            if base in {
                'superficie_piso', 'superficie_cubierta', 'superficie_muros',
                'superficie_general', 'perimetro', 'referencial',
            }:
                bases[_normalizar(busquedas[indice])] = base
        cupo = MAX_BUSQUEDAS - total_busquedas
        busquedas = busquedas[:cupo]
        if nombre and busquedas:
            tareas.append({
                "nombre": nombre, "busquedas": busquedas,
                "usos": usos, "bases": bases,
            })
            total_busquedas += len(busquedas)
        if total_busquedas >= MAX_BUSQUEDAS:
            break

    es_propuesta_estandar = (
        datos.get("_proyecto_estandar") is True
        or datos.get("_proyecto_integral") is True
    )
    herramientas = (
        _lista_textos(datos.get("herramientas_proyecto"), 8, 80)
        if datos.get("incluir_herramientas") is True or es_propuesta_estandar
        else []
    )
    herramientas = _separar_componentes_compuestos(herramientas)
    herramientas = [
        herramienta for herramienta in herramientas
        if _herramienta_reconocible(herramienta)
    ]
    herramientas = herramientas[:max(0, MAX_BUSQUEDAS - total_busquedas)]
    if herramientas:
        tareas = tareas[:max(0, MAX_TAREAS - 1)]
        tareas.append({"nombre": "Herramientas recomendadas", "busquedas": herramientas})
    return tareas[:MAX_TAREAS]


def _ajustar_radier_a_condiciones_informadas(datos, tareas, modo_estandar):
    """Capa aislada y reversible para propuestas de radier.

    Una plantilla estandar sigue siendo valida, pero no puede contradecir la
    base que el cliente describio. Esta funcion concentra las reglas de radier
    para poder retirarlas sin afectar los demas tipos de proyecto.
    """
    contexto = _normalizar(" ".join([
        datos.get("proyecto") or "",
        datos.get("_contexto_usuario") or "",
    ]))
    if "radier" not in contexto:
        return tareas

    base_hormigon_existente = any(frase in contexto for frase in (
        "base es de hormigon", "base de hormigon", "sobre hormigon",
        "hormigon existente", "hormigon firme", "losa de hormigon",
    )) and not datos.get("_parte_desde_cero")

    espesor = ""
    for patron in (
        r"espesor(?: de)?\s*(?:es|de|:)?\s*(\d+(?:[.,]\d+)?)\s*(cm|mm)\b",
        r"(\d+(?:[.,]\d+)?)\s*(cm|mm)\s*(?:de\s*)?espesor\b",
    ):
        coincidencia = re.search(patron, contexto)
        if coincidencia:
            espesor = f"{coincidencia.group(1).replace(',', '.')} {coincidencia.group(2)}"
            break

    datos["_radier_condiciones"] = {
        "base_hormigon_existente": base_hormigon_existente,
        "espesor": espesor,
        "espesor_estandar": "10 cm" if modo_estandar and not espesor else "",
    }
    if not base_hormigon_existente:
        return tareas

    # Sobre una losa existente no se prepara nuevamente un suelo natural.
    exclusiones_suelo = (
        "base estabilizada", "polietileno construccion", "arena seca multiuso",
    )
    herramientas = (
        "prensa", "sargento", "cincel", "carretilla", "pala", "combo",
    )
    tareas_ajustadas = []
    herramientas_movidas = []
    for tarea in tareas:
        busquedas = []
        usos = {}
        bases = {}
        for busqueda in tarea.get("busquedas", []):
            clave = _normalizar(busqueda)
            if any(exclusion in clave for exclusion in exclusiones_suelo):
                continue
            if any(herramienta in clave for herramienta in herramientas):
                herramientas_movidas.append(busqueda)
                continue
            busquedas.append(busqueda)
            if clave in tarea.get("usos", {}):
                usos[clave] = tarea["usos"][clave]
            if clave in tarea.get("bases", {}):
                bases[clave] = tarea["bases"][clave]
        if not busquedas:
            continue
        texto_busquedas = _normalizar(" ".join(busquedas))
        nombre = tarea["nombre"]
        if "moldaje" in texto_busquedas:
            nombre = "Contencion y moldaje"
        elif "malla" in texto_busquedas or "refuerzo" in texto_busquedas:
            nombre = "Refuerzo referencial"
        elif "hormigon" in texto_busquedas:
            nombre = "Nueva capa de hormigon"
        tareas_ajustadas.append({
            **tarea,
            "nombre": nombre,
            "busquedas": busquedas,
            "usos": usos,
            "bases": bases,
        })

    herramientas_movidas = _lista_textos(herramientas_movidas, 8, 80)
    if herramientas_movidas:
        tareas_ajustadas.append({
            "nombre": "Herramientas opcionales",
            "busquedas": herramientas_movidas,
            "usos": {},
            "bases": {},
        })
    return tareas_ajustadas[:MAX_TAREAS]


def _ajustar_cuestionario_quincho(datos):
    """Conserva un cuestionario breve y completo para quinchos no estandar.

    La zona de fuego forma parte de la propuesta base del quincho y no se
    pregunta. Se muestran juntos todos los datos realmente pendientes para que
    el cliente pueda responderlos en un solo mensaje. En turnos posteriores
    desaparecen los requisitos ya reconocidos.
    """
    contexto = _normalizar(" ".join([
        datos.get("proyecto") or "",
        datos.get("_contexto_usuario") or "",
    ]))
    es_construccion_quincho = (
        "quincho" in contexto
        and any(termino in contexto for termino in (
            "construir", "construccion", "hacer un quincho",
            "armar", "levantar", "desde cero",
        ))
        and not any(termino in contexto for termino in (
            "reparar quincho", "arreglar quincho", "cambiar quincho",
        ))
    )
    if not es_construccion_quincho:
        return

    datos["_quincho_zona_fuego_estandar"] = True

    try:
        dimensiones = (
            Decimal(str(datos.get("ancho_cm") or 0)) > 0
            and Decimal(str(datos.get("fondo_cm") or 0)) > 0
        )
    except (ArithmeticError, TypeError, ValueError):
        dimensiones = False

    if any(termino in contexto for termino in (
        "radier existente", "sobre radier", "base de hormigon",
        "base es de hormigon", "losa existente",
    )):
        base = "radier_existente"
    elif any(termino in contexto for termino in (
        "terreno natural", "suelo de tierra", "sobre tierra",
        "sin radier", "no hay radier", "no existe radier",
        "no exite radier", "desde cero", "desde 0",
    )):
        base = "terreno_natural"
    else:
        base = ""

    if "semiabierto" in contexto or "semi abierto" in contexto:
        diseno = "semiabierto"
    elif "cerrado" in contexto:
        diseno = "cerrado"
    elif re.search(r"\babierto\b", contexto):
        diseno = "abierto"
    else:
        diseno = ""

    try:
        altura_cm = max(0, int(datos.get("alto_cm") or 0))
    except (TypeError, ValueError):
        altura_cm = 0
    if not altura_cm:
        patrones_altura = (
            r"(?:altura|altira|alto)(?:\s+aproximad[ao])?\s*(?:de|es|:)?\s*"
            r"(\d+(?:[.,]\d+)?)\s*(m|metros?|cm)\b",
            r"(\d+(?:[.,]\d+)?)\s*(m|metros?|cm)\s+de\s+(?:altura|altira|alto)\b",
        )
        for patron in patrones_altura:
            coincidencia = re.search(patron, contexto)
            if not coincidencia:
                continue
            valor = Decimal(coincidencia.group(1).replace(",", "."))
            altura_cm = int(valor if coincidencia.group(2) == "cm" else valor * 100)
            datos["alto_cm"] = altura_cm
            break

    material_estructura = _normalizar(datos.get("material_estructura"))
    if material_estructura not in {"madera", "metal", "hormigon", "otra"}:
        if re.search(r"estructura.{0,25}\bmadera\b", contexto):
            material_estructura = "madera"
        elif re.search(r"estructura.{0,25}\b(?:metal|acero|metalica)\b", contexto):
            material_estructura = "metal"
        else:
            material_estructura = ""
    tipo_cubierta = _normalizar(datos.get("tipo_cubierta"))
    if not tipo_cubierta:
        if "policarbonato" in contexto:
            tipo_cubierta = "policarbonato"
        elif re.search(r"\b(?:zinc|plancha galvanizada)\b", contexto):
            tipo_cubierta = "zinc"
        elif re.search(r"\btejas?\b", contexto):
            tipo_cubierta = "tejas"
    delega_materiales = bool(
        datos.get("_delega_eleccion")
        or re.search(r"\b(?:elige tu|recomienda|recomiendame)\b", contexto)
    )

    datos["_quincho_base"] = base
    datos["_quincho_diseno"] = diseno
    datos["_quincho_altura_cm"] = altura_cm
    datos["_quincho_material_estructura"] = material_estructura
    datos["_quincho_tipo_cubierta"] = tipo_cubierta

    faltantes = []
    if not dimensiones:
        faltantes.append("Ancho y largo del quincho")
    if not base:
        faltantes.append("Base existente del quincho")
    if not diseno:
        faltantes.append("Diseño general del quincho")
    if not altura_cm:
        faltantes.append("Altura aproximada del quincho")
    if not delega_materiales and not (material_estructura and tipo_cubierta):
        faltantes.append("Material de la estructura y cubierta del quincho")

    # Al volver a interpretar la conversación, los datos ya reconocidos
    # desaparecen naturalmente y solo se repiten los requisitos pendientes.
    datos["datos_faltantes_proyecto"] = faltantes


def _ajustar_proyecto_ceramica(datos, tareas):
    """Relaciona revestimiento, materiales y herramientas de colocacion.

    La capa es deliberadamente independiente de las plantillas generales: solo
    actua sobre pisos ceramicos o porcelanatos y conserva el material pedido.
    """
    contexto = _normalizar(" ".join([
        datos.get("proyecto") or "",
        datos.get("_contexto_usuario") or "",
    ]))
    es_revestimiento_ceramico = any(
        material in contexto for material in ("ceramica", "porcelanato")
    )
    if not es_revestimiento_ceramico:
        return tareas

    es_muro = any(termino in contexto for termino in (
        "muro", "muros", "pared", "paredes", "revestimiento mural",
    ))
    es_piso = any(termino in contexto for termino in ("piso", "suelo"))
    aplicacion = "muro" if es_muro and not es_piso else "piso" if es_piso else ""
    ambientes = {
        "bano": ("bano", "ducha", "lavamanos"),
        "cocina": ("cocina",),
        "lavadero": ("lavadero", "logia"),
        "exterior": ("terraza", "balcon", "patio", "exterior"),
        "interior_seco": (
            "dormitorio", "habitacion", "living", "comedor", "pasillo",
        ),
    }
    ambiente = next((
        nombre for nombre, terminos in ambientes.items()
        if any(termino in contexto for termino in terminos)
    ), "")

    descripcion_base_cementicia = (
        "gris" in contexto
        and any(termino in contexto for termino in ("dura", "duro"))
        and any(termino in contexto for termino in ("firme", "continua", "continuo"))
        and not any(termino in contexto for termino in (
            "junta", "juntas", "palmeta", "palmetas", "madera", "osb",
            "tabla", "tablas", "panel", "paneles",
        ))
    )
    tipo_base = ""
    base_inferida = False
    if any(termino in contexto for termino in (
        "ceramica existente", "piso ceramico existente", "palmetas existentes",
        "ceramica antigua", "sobre ceramica", "encima de ceramica",
    )):
        tipo_base = "ceramica_existente"
    elif any(termino in contexto for termino in (
        "base de madera", "base madera", "base de osb", "base osb",
        "soporte de madera", "soporte madera", "soporte osb",
        "piso de madera", "piso osb", "muro de madera", "pared de madera",
    )):
        tipo_base = "madera_osb"
    elif any(termino in contexto for termino in (
        "fibrocemento", "fibro cemento",
    )):
        tipo_base = "fibrocemento"
    elif any(termino in contexto for termino in (
        "sobrelosa", "mortero de nivelacion", "mortero nivelacion",
        "carpeta de mortero", "base de mortero", "contrapiso de mortero",
    )):
        tipo_base = "mortero_sobrelosa"
    elif any(termino in contexto for termino in (
        "base de hormigon", "base es de hormigon", "base hormigon",
        "piso de hormigon", "piso hormigon", "sobre hormigon", "losa",
        "radier", "contrapiso de hormigon", "muro de hormigon",
        "pared de hormigon", "muro de concreto", "pared de concreto",
    )):
        tipo_base = "hormigon_radier"
    elif descripcion_base_cementicia:
        tipo_base = "base_cementicia_probable"
        base_inferida = True
    material_base_informado = bool(tipo_base)
    base_firme = "firme" in contexto
    base_seca = any(termino in contexto for termino in (
        "seca", "seco", "sin humedad", "libre de humedad",
    ))
    base_nivelada = any(termino in contexto for termino in (
        "nivelada", "nivelado", "sin desnivel", "sin desniveles",
    ))
    estado_descrito = any(termino in contexto for termino in (
        "buen estado", "regular", "mal estado", "grieta", "humedad",
        "desnivel", "suelta", "suelto", "deteriorada", "deteriorado",
    ))
    estado_base_informado = estado_descrito or all((
        base_firme, base_seca, base_nivelada,
    ))
    faltantes = _lista_textos(datos.get("datos_faltantes_proyecto"), 4, 100)
    try:
        superficie_informada = Decimal(str(datos.get("superficie") or 0)) > 0
        dimensiones_informadas = (
            Decimal(str(datos.get("ancho_cm") or 0)) > 0
            and Decimal(str(datos.get("fondo_cm") or 0)) > 0
        )
    except (ArithmeticError, TypeError, ValueError):
        superficie_informada = dimensiones_informadas = False
    dimensiones_informadas = dimensiones_informadas or bool(re.search(
        r'\b\d+(?:[.,]\d+)?\s*(?:x|por)\s*\d+(?:[.,]\d+)?'
        r'\s*(?:m|metro|metros)?\b',
        contexto,
    ))
    ubicacion_informada = any(termino in contexto for termino in (
        "bano", "cocina", "dormitorio", "habitacion", "living", "comedor",
        "pasillo", "lavadero", "logia", "terraza", "balcon", "patio",
        "garaje", "estacionamiento", "interior", "exterior",
    ))
    # Material y estado son respuestas diferentes. Mantenerlas separadas evita
    # volver a preguntar qué base existe cuando el cliente ya dijo, por
    # ejemplo, "base hormigón", pero todavía no confirmó su estado.
    faltantes = [
        faltante for faltante in faltantes
        if not (
            any(termino in _normalizar(faltante) for termino in (
                "base", "piso actual", "contrapiso",
            ))
            or "estado" in _normalizar(faltante)
            or any(termino in _normalizar(faltante) for termino in (
                "medida", "dimension", "superficie", "metros cuadrados",
                "ancho", "largo",
            ))
            or any(termino in _normalizar(faltante) for termino in (
                "ubicacion", "habitacion", "ambiente", "donde se instalara",
            ))
        )
    ]
    if not (superficie_informada or dimensiones_informadas):
        faltantes.append(
            "Dimensiones o metros cuadrados del piso"
            if aplicacion == "piso"
            else "Dimensiones o metros cuadrados de la superficie"
        )
    if not material_base_informado:
        faltantes.append(
            "Material actual de la base o piso"
            if aplicacion == "piso"
            else (
                "Material actual del muro o soporte"
                if aplicacion == "muro"
                else "Material actual de la base, muro o soporte"
            )
        )
    if not estado_base_informado:
        faltantes.append(
            "Confirmar si la base esta seca y libre de humedad"
            if base_firme and base_nivelada and not base_seca
            else "Estado actual de la base"
        )
    datos["datos_faltantes_proyecto"] = faltantes[:4]
    datos["_ceramica_material_base"] = material_base_informado
    datos["_ceramica_tipo_base"] = tipo_base
    datos["_ceramica_base_inferida"] = base_inferida
    datos["_ceramica_estado_base"] = estado_base_informado
    if not aplicacion:
        faltantes.insert(0, "Aplicacion de la ceramica: piso o pared")
    if not ambiente:
        faltantes.insert(
            1 if not aplicacion else 0,
            "Ubicacion o habitacion donde se instalara la ceramica",
        )
    datos["datos_faltantes_proyecto"] = list(dict.fromkeys(faltantes))[:4]
    datos["_ceramica_base_pendiente"] = not all((
        aplicacion,
        ambiente,
        superficie_informada or dimensiones_informadas,
        material_base_informado,
        estado_base_informado,
    ))
    datos["_proyecto_ceramica"] = True
    datos["_ceramica_aplicacion"] = aplicacion
    datos["_ceramica_ambiente"] = ambiente
    datos["_ceramica_requiere_antideslizante"] = bool(
        aplicacion == "piso" and ambiente in {"bano", "cocina", "lavadero", "exterior"}
    )

    pidio_porcelanato = "porcelanato" in contexto
    pidio_ceramica = "ceramica" in contexto and not pidio_porcelanato
    material = "ceramica" if pidio_ceramica else "porcelanato"
    ambiente_busqueda = {
        "bano": "bano zona humeda",
        "cocina": "cocina",
        "lavadero": "lavadero zona humeda",
        "exterior": "exterior",
        "interior_seco": "interior",
    }.get(ambiente, "interior")
    revestimiento = " ".join(filter(None, (
        material,
        aplicacion or "revestimiento",
        ambiente_busqueda,
        "antideslizante" if datos["_ceramica_requiere_antideslizante"] else "",
    )))
    base_superficie = "superficie_muros" if aplicacion == "muro" else "superficie_piso"
    adhesion_segun_base = {
        "ceramica_existente": "adhesivo flexible ceramica sobre ceramica",
        "madera_osb": "adhesivo flexible ceramica para placa fibrocemento",
        "fibrocemento": "adhesivo flexible ceramica para fibrocemento",
    }
    adhesion = adhesion_segun_base.get(tipo_base) or " ".join(filter(None, (
        "adhesivo ceramico",
        "para muro" if aplicacion == "muro" else "para piso",
        "zona humeda" if ambiente in {"bano", "lavadero"} else "interior",
    )))
    tareas_ceramica = [
        {
            "nombre": "Revestimiento principal",
            "busquedas": [revestimiento],
            "usos": {
                _normalizar(revestimiento): (
                    "Formar el revestimiento de piso solicitado sin cambiar "
                    "silenciosamente entre ceramica y porcelanato."
                ),
            },
            "bases": {_normalizar(revestimiento): base_superficie},
        },
        *([{
            "nombre": "Preparacion del soporte existente",
            "busquedas": [
                "promotor de adherencia ceramica sobre ceramica"
                if tipo_base == "ceramica_existente"
                else "placa fibrocemento compatible sobre madera OSB"
            ],
            "usos": {
                _normalizar(
                    "promotor de adherencia ceramica sobre ceramica"
                    if tipo_base == "ceramica_existente"
                    else "placa fibrocemento compatible sobre madera OSB"
                ): (
                    "Preparar el revestimiento existente para recibir una nueva capa."
                    if tipo_base == "ceramica_existente"
                    else "Crear un soporte compatible antes de instalar la ceramica."
                ),
            },
            "bases": {},
        }] if tipo_base in {"ceramica_existente", "madera_osb"} else []),
        {
            "nombre": "Adhesion del revestimiento",
            "busquedas": [adhesion],
            "usos": {
                _normalizar(adhesion): (
                    "Adherir las piezas a una base compatible, firme, limpia y nivelada."
                ),
            },
            "bases": {
                _normalizar(adhesion): base_superficie,
            },
        },
        {
            "nombre": "Separacion y nivelacion",
            "busquedas": [
                "separadores para ceramica 3 mm",
                "sistema nivelador ceramica clip 2 mm",
                "cuñas reutilizables nivelador ceramica",
            ],
            "usos": {
                _normalizar("separadores para ceramica 3 mm"): "Mantener juntas regulares entre las piezas.",
                _normalizar("sistema nivelador ceramica clip 2 mm"): "Reducir diferencias de altura entre piezas durante la colocacion.",
                _normalizar("cuñas reutilizables nivelador ceramica"): "Completar el sistema de clips de nivelacion compatible.",
            },
            "bases": {
                _normalizar("separadores para ceramica 3 mm"): "superficie_general",
                _normalizar("sistema nivelador ceramica clip 2 mm"): "referencial",
                _normalizar("cuñas reutilizables nivelador ceramica"): "referencial",
            },
        },
        {
            "nombre": "Juntas y terminacion",
            "busquedas": ["frague flexible gris bolsa 2 kg"],
            "usos": {
                _normalizar("frague flexible gris bolsa 2 kg"): (
                    "Rellenar las juntas con un producto compatible con su ancho y el revestimiento."
                ),
            },
            "bases": {_normalizar("frague flexible gris bolsa 2 kg"): base_superficie},
        },
    ]

    if datos.get("_consulta_solo_herramientas") or datos.get("incluir_herramientas"):
        herramientas = [
            ("cinta metrica", "Medir el recinto y trazar la distribucion inicial."),
            ("nivel de burbuja aluminio 60 cm", "Comprobar nivel y planeidad durante la colocacion."),
            ("llana dentada acero 10 mm", "Peinar el adhesivo con un dentado acorde al formato de la pieza."),
            ("cortadora manual porcelanato 600 mm", "Realizar cortes rectos y ajustes perimetrales."),
            ("disco diamantado continuo porcelanato 115 mm", "Realizar cortes especiales con una herramienta compatible y proteccion adecuada."),
            ("mazo de goma para ceramica", "Asentar suavemente las piezas sin golpearlas con metal."),
            ("balde flexible para mezcla pisos 28 litros", "Preparar adhesivo o frague siguiendo su ficha."),
            ("paleta mezcladora para adhesivo y mortero", "Mezclar el producto con una herramienta motriz compatible."),
            ("llana de goma para frague", "Distribuir el frague diagonalmente sobre las juntas."),
            ("esponja para limpieza de frague", "Retirar el excedente sin vaciar las juntas."),
            ("rodillera espuma instalacion pisos", "Proteger las rodillas durante el trabajo a nivel de piso."),
            ("guantes de trabajo nitrilo reforzado", "Proteger las manos durante mezcla, corte y limpieza."),
        ]
        tareas_ceramica.append({
            "nombre": "Herramientas opcionales",
            "busquedas": [nombre for nombre, _ in herramientas],
            "usos": {_normalizar(nombre): uso for nombre, uso in herramientas},
            "bases": {_normalizar(nombre): "referencial" for nombre, _ in herramientas},
        })
    return tareas_ceramica


def _producto_compatible_con_revestimiento_ceramico(producto, datos, consulta):
    """Aplica requisitos duros antes de puntuar el revestimiento principal."""
    especificaciones = producto.especificaciones or {}
    pares = {
        _normalizar(clave): valor
        for clave, valor in especificaciones.items()
    } if isinstance(especificaciones, dict) else {}

    def texto_valor(*claves):
        valores = []
        for clave in claves:
            valor = pares.get(_normalizar(clave))
            if isinstance(valor, (list, tuple, set)):
                valores.extend(str(item) for item in valor)
            elif valor not in (None, ""):
                valores.append(str(valor))
        return _normalizar(" ".join(valores))

    texto = _normalizar(" ".join((
        producto.nombre,
        producto.descripcion,
        producto.uso_recomendado,
        texto_valor(
            "Aplicacion", "Uso", "Ambientes", "Ambientes recomendados",
            "Antideslizante", "Nivel de transito", "Diseno",
        ),
    )))
    aplicacion = datos.get("_ceramica_aplicacion") or ""
    ambiente = datos.get("_ceramica_ambiente") or ""
    consulta_normalizada = _normalizar(consulta)

    if any(accesorio in _normalizar(producto.nombre) for accesorio in (
        "adhesivo", "frague", "separador", "nivelador", "cuna",
        "silicona", "sellador", "membrana", "llana", "cortadora",
        "disco", "mazo", "esponja", "rodillera",
    )):
        return False

    if aplicacion == "piso" and "piso" not in texto:
        return False
    if aplicacion == "muro" and not any(palabra in texto for palabra in ("muro", "pared")):
        return False
    if "ceramica" in consulta_normalizada and "porcelanato" not in consulta_normalizada:
        if "ceramica" not in texto or "porcelanato" in _normalizar(producto.nombre):
            return False
    if "porcelanato" in consulta_normalizada and "porcelanato" not in texto:
        return False

    ambientes_requeridos = {
        "bano": ("bano", "zona humeda", "ducha", "lavamanos"),
        "cocina": ("cocina",),
        "lavadero": ("lavadero", "logia", "zona humeda"),
        "exterior": ("exterior", "terraza", "balcon", "patio"),
        "interior_seco": ("interior", "dormitorio", "living", "comedor", "pasillo"),
    }
    if ambiente and not any(
        termino in texto for termino in ambientes_requeridos.get(ambiente, ())
    ):
        return False
    if datos.get("_ceramica_requiere_antideslizante") and not any(
        termino in texto for termino in ("antideslizante", "antislip")
    ):
        return False
    return True


def _especialidades_validas(datos, texto_plan, resolver_especialidad):
    disponibles = {
        _normalizar(nombre): nombre
        for nombre in Especialidad.objects.filter(activa=True)
        .values_list("nombre", flat=True)
    }
    resultado = []
    for propuesta in _lista_textos(
        datos.get("especialidades_proyecto"),
        MAX_ESPECIALIDADES,
    ):
        especialidad = disponibles.get(_normalizar(propuesta))
        if especialidad and especialidad not in resultado:
            resultado.append(especialidad)

    inferida = resolver_especialidad(texto_plan)
    inferida = disponibles.get(_normalizar(inferida))
    if inferida and inferida not in resultado and len(resultado) < MAX_ESPECIALIDADES:
        resultado.append(inferida)
    return resultado


def resolver_proyecto_generico(
    datos,
    *,
    buscar_productos,
    producto_publico,
    buscar_maestros,
    resolver_especialidad,
):
    """Convierte un plan libre de Gemini en resultados verificados por Django."""
    proyecto = _texto_seguro(datos.get("proyecto"), 120)
    tareas = _extraer_tareas(datos)
    contexto_usuario = _normalizar(datos.get('_contexto_usuario'))
    contexto_inicial = _normalizar(" ".join([
        proyecto,
        contexto_usuario,
        *(busqueda for tarea in tareas for busqueda in tarea.get("busquedas", [])),
    ]))
    es_porton_automatico = (
        "porton" in contexto_inicial
        and any(termino in contexto_inicial for termino in (
            "electrico", "automatico", "automatizacion", "motor",
        ))
    )
    contexto_proyecto = _normalizar(proyecto)
    es_contexto_gas = any(termino in contexto_inicial for termino in (
        'gas', 'calefont', 'cocina a gas', 'encimera a gas',
    ))
    es_intervencion_acotada = (
        any(accion in contexto_proyecto for accion in (
            'instalar', 'instalacion', 'reparar', 'reparacion',
            'cambiar', 'cambio', 'reemplazar', 'reemplazo',
        ))
        and not any(accion in contexto_proyecto for accion in (
            'construir', 'construccion', 'hacer un', 'levantar',
            'obra completa', 'renovacion completa', 'remodelacion completa',
        ))
    )
    es_quincho_estandar = (
        'quincho' in contexto_inicial
        and not es_intervencion_acotada
        and (
            datos.get('_proyecto_estandar') is True
            or datos.get('_proyecto_integral') is True
            or 'estandar' in _normalizar(proyecto)
        )
    )
    es_bodega_estandar = (
        'bodega' in contexto_inicial
        and not es_intervencion_acotada
        and (
            datos.get('_proyecto_estandar') is True
            or datos.get('_proyecto_integral') is True
            or 'estandar' in _normalizar(proyecto)
        )
    )
    es_pergola_estandar = (
        'pergola' in contexto_inicial
        and not es_intervencion_acotada
        and (
            datos.get('_proyecto_estandar') is True
            or datos.get('_proyecto_integral') is True
            or 'estandar' in _normalizar(proyecto)
        )
    )
    # Para una pérgola estándar la alternativa inicial es de madera, incluso
    # si el cliente aún no nombra el material. Así la propuesta sirve como guía
    # completa; el cliente puede luego pedir una alternativa metálica.
    es_pergola_madera = (
        'pergola' in contexto_inicial
        and ('madera' in contexto_inicial or es_pergola_estandar)
        and not es_intervencion_acotada
    )
    parte_desde_cero = datos.get('_parte_desde_cero') is True
    es_instalacion_gas_cocina = (
        'gas' in contexto_inicial
        and any(termino in contexto_inicial for termino in (
            'cocina', 'encimera', 'horno', 'artefacto de cocina',
        ))
        and (
            datos.get('_proyecto_estandar') is True
            or 'estandar' in contexto_proyecto
        )
    )
    es_iluminacion_exterior_con_sensor = (
        any(termino in contexto_inicial for termino in (
            'luz exterior', 'luminaria exterior', 'foco exterior',
            'aplique exterior', 'iluminacion exterior',
        ))
        and any(termino in contexto_inicial for termino in (
            'sensor', 'movimiento', 'presencia',
        ))
    )
    requisitos_explicitos = datos.get('_requisitos_explicitos') or {}
    solicita_luz_interior_bodega = (
        es_bodega_estandar
        and (
            requisitos_explicitos.get('iluminacion_interior') is True
            or any(termino in contexto_usuario for termino in (
                'luz interior', 'iluminacion interior', 'lampara interior',
                'ampolleta interior',
            ))
        )
    )
    if es_bodega_estandar:
        # La bodega debe contemplar cerramiento, acceso, techumbre y aguas
        # lluvia. Los elementos ausentes se informarán como faltantes.
        tareas = [
            *([{
                'nombre': 'Preparación y fundaciones',
                'busquedas': [
                    'base estabilizada para radier saco 25 kg',
                    'hormigon predosificado H20 saco 25 kg',
                    'polietileno construccion 200 micras 4 x 25 m',
                ],
                'usos': {
                    _normalizar('base estabilizada para radier saco 25 kg'): 'Preparar y nivelar el terreno antes de formar las fundaciones.',
                    _normalizar('hormigon predosificado H20 saco 25 kg'): 'Formar dados o una base de hormigón para recibir la estructura.',
                    _normalizar('polietileno construccion 200 micras 4 x 25 m'): 'Separar el hormigón de la humedad del terreno cuando corresponda.',
                },
            }] if parte_desde_cero else []),
            {
                'nombre': 'Anclaje a la base',
                'busquedas': [
                    'perno anclaje expansion M12 x 120 mm',
                ],
                'usos': {
                    _normalizar('perno anclaje expansion M12 x 120 mm'): 'Fijar la estructura a la base firme de hormigón.',
                },
            },
            {
                'nombre': 'Estructura de madera',
                'busquedas': [
                    'pino dimensionado 2 x 4 pulgadas',
                    'escuadra metalica reforzada',
                    'tornillo estructural para madera',
                ],
                'usos': {
                    _normalizar('pino dimensionado 2 x 4 pulgadas'): 'Formar pilares, soleras y vigas de la estructura.',
                    _normalizar('escuadra metalica reforzada'): 'Reforzar encuentros entre piezas estructurales.',
                    _normalizar('tornillo estructural para madera'): 'Unir las piezas principales de madera.',
                },
            },
            {
                'nombre': 'Muros y protección exterior',
                'busquedas': [
                    'tablero OSB estructural 9,5 mm',
                    'membrana hidrofuga para muros',
                    'plancha fibrocemento exterior 8 mm',
                    'tornillo fibrocemento exterior',
                ],
                'usos': {
                    _normalizar('tablero OSB estructural 9,5 mm'): 'Rigidizar y cerrar la estructura de los muros.',
                    _normalizar('membrana hidrofuga para muros'): 'Proteger el cerramiento frente a humedad exterior.',
                    _normalizar('plancha fibrocemento exterior 8 mm'): 'Formar el revestimiento exterior expuesto a la intemperie.',
                    _normalizar('tornillo fibrocemento exterior'): 'Fijar las planchas exteriores a la estructura.',
                },
            },
            {
                'nombre': 'Cubierta y remates',
                'busquedas': [
                    'plancha zinc acanalado 0,35 mm x 3 m',
                    'tornillo techo autoperforante',
                    'membrana impermeable para techumbre',
                    'cumbrera galvanizada',
                ],
                'usos': {
                    _normalizar('plancha zinc acanalado 0,35 mm x 3 m'): 'Cubrir la bodega y evacuar el agua de lluvia.',
                    _normalizar('tornillo techo autoperforante'): 'Fijar la cubierta a la estructura de techumbre.',
                    _normalizar('membrana impermeable para techumbre'): 'Crear una protección secundaria bajo la cubierta.',
                    _normalizar('cumbrera galvanizada'): 'Cerrar y proteger el encuentro superior del techo.',
                },
            },
            {
                'nombre': 'Acceso y seguridad',
                'busquedas': [
                    'puerta exterior para bodega',
                    'bisagra puerta acero zincado 3 pulgadas',
                    'cerradura exterior para puerta',
                ],
                'usos': {
                    _normalizar('puerta exterior para bodega'): 'Cerrar el acceso principal de la bodega.',
                    _normalizar('bisagra reforzada para puerta'): 'Permitir el giro y sostener la hoja de la puerta.',
                    _normalizar('cerradura exterior para puerta'): 'Asegurar el acceso a los elementos almacenados.',
                },
            },
            *([{
                'nombre': 'Iluminación interior',
                'busquedas': [
                    'portalámpara E27 sobrepuesto blanco',
                    'ampolleta LED E27 9 W luz neutra',
                    'interruptor simple 10 A 250 V blanco',
                    'cable eléctrico 1,5 mm² rollo 100 m',
                    'conduit PVC eléctrico 20 mm x 3 m',
                ],
                'usos': {
                    _normalizar('portalámpara E27 sobrepuesto blanco'): 'Sostener la ampolleta en el punto de iluminación interior.',
                    _normalizar('ampolleta LED E27 9 W luz neutra'): 'Iluminar el interior de la bodega.',
                    _normalizar('interruptor simple 10 A 250 V blanco'): 'Controlar el encendido de la luz desde un punto compatible.',
                    _normalizar('cable eléctrico 1,5 mm² rollo 100 m'): 'Alimentar la luminaria desde un circuito dimensionado por personal competente.',
                    _normalizar('conduit PVC eléctrico 20 mm x 3 m'): 'Proteger el cableado en su recorrido interior.',
                },
            }] if solicita_luz_interior_bodega else []),
            {
                'nombre': 'Evacuación de aguas lluvia',
                'busquedas': [
                    'canaleta aguas lluvia',
                    'bajada aguas lluvia PVC',
                ],
                'usos': {
                    _normalizar('canaleta aguas lluvia'): 'Recoger el agua que cae desde la cubierta.',
                    _normalizar('bajada aguas lluvia PVC'): 'Conducir el agua desde la canaleta hasta la descarga.',
                },
            },
        ]
    if es_pergola_madera:
        # Una pérgola de madera para sombra no debe depender de una lista
        # incompleta del modelo: requiere estructura, anclaje, uniones,
        # protección y una cubierta de sombra claramente separada.
        tareas = [
            *([{
                'nombre': 'Fundaciones de pilares',
                'busquedas': [
                    'base estabilizada para radier saco 25 kg',
                    'hormigon predosificado H20 saco 25 kg',
                    'clavo corriente 4 pulgadas',
                ],
                'usos': {
                    _normalizar('base estabilizada para radier saco 25 kg'): 'Preparar y nivelar la base de los dados que recibirán los pilares.',
                    _normalizar('hormigon predosificado H20 saco 25 kg'): 'Formar los dados de hormigón para apoyar y fijar los pilares.',
                    _normalizar('clavo corriente 4 pulgadas'): 'Armar moldajes temporales para los dados de hormigón cuando se requiera.',
                },
            }] if parte_desde_cero else []),
            {
                'nombre': 'Anclaje de pilares',
                'busquedas': [
                    'perno anclaje expansion M12 x 120 mm',
                ],
                'usos': {
                    _normalizar('perno anclaje expansion M12 x 120 mm'): 'Fijar los soportes de los pilares al radier de hormigón.',
                },
            },
            {
                'nombre': 'Pilares y vigas de madera',
                'busquedas': [
                    'pino dimensionado 2 x 4 pulgadas x 3,2 m',
                    'pino dimensionado 2 x 6 pulgadas x 3,20 m',
                ],
                'usos': {
                    _normalizar('pino dimensionado 2 x 4 pulgadas x 3,2 m'): 'Formar pilares, costaneras y elementos secundarios de la estructura.',
                    _normalizar('pino dimensionado 2 x 6 pulgadas x 3,20 m'): 'Formar vigas principales cuando el diseño y las cargas lo permitan.',
                },
            },
            {
                'nombre': 'Uniones estructurales',
                'busquedas': [
                    'tornillo estructural para madera 6 x 100 mm pack 50',
                    'escuadra metalica reforzada 50 x 50 mm pack 4',
                ],
                'usos': {
                    _normalizar('tornillo estructural para madera 6 x 100 mm pack 50'): 'Unir vigas y pilares de madera con una fijación estructural.',
                    _normalizar('escuadra metalica reforzada 50 x 50 mm pack 4'): 'Reforzar los encuentros a 90 grados entre las piezas de madera.',
                },
            },
            {
                'nombre': 'Sombra y protección',
                'busquedas': [
                    'malla raschel sombra 80% verde rollo 2 x 10 m',
                    'barniz al agua para madera satinado 1 litro',
                ],
                'usos': {
                    _normalizar('malla raschel sombra 80% verde rollo 2 x 10 m'): 'Dar sombra sobre la pérgola dejando circular el aire.',
                    _normalizar('barniz al agua para madera satinado 1 litro'): 'Proteger y terminar la madera expuesta del proyecto.',
                },
            },
            {
                'nombre': 'Herramientas recomendadas',
                'busquedas': [
                    'taladro percutor',
                    'nivel de burbuja aluminio 60 cm',
                    'sierra circular',
                    'cinta metrica',
                ],
                'usos': {
                    _normalizar('taladro percutor'): 'Perforar para los anclajes y preparar las fijaciones compatibles.',
                    _normalizar('nivel de burbuja aluminio 60 cm'): 'Comprobar plomo y nivel antes de fijar pilares y vigas.',
                    _normalizar('sierra circular'): 'Cortar las piezas de madera según las medidas definidas.',
                    _normalizar('cinta metrica'): 'Trazar la ubicación de pilares y medir las piezas de la estructura.',
                },
            },
        ]
    if es_instalacion_gas_cocina:
        # Gas es un caso de seguridad: no se permite que una búsqueda libre
        # convierta una palabra genérica como "instalación" en un sanitario.
        # La lista describe el sistema de referencia y deja el montaje a un
        # instalador autorizado.
        tareas = [
            {
                'nombre': 'Tubería y uniones de gas',
                'busquedas': [
                    'tubo cobre rigido para gas 1/2 pulgada x 3 m',
                    'codo cobre para gas 1/2 pulgada',
                    'union cobre para gas 1/2 pulgada',
                ],
                'usos': {
                    _normalizar('tubo cobre rigido para gas 1/2 pulgada x 3 m'): 'Conducir el gas por el recorrido definido por el instalador autorizado.',
                    _normalizar('codo cobre para gas 1/2 pulgada'): 'Resolver cambios de dirección en la tubería de cobre.',
                    _normalizar('union cobre para gas 1/2 pulgada'): 'Unir tramos compatibles de tubería de cobre.',
                },
            },
            {
                'nombre': 'Corte y conexión de la cocina',
                'busquedas': [
                    'valvula corte gas bronce 1/2 pulgada',
                    'flexible para gas 1/2 pulgada x 1 m',
                    'sellador de roscas para gas 50 ml',
                ],
                'usos': {
                    _normalizar('valvula corte gas bronce 1/2 pulgada'): 'Permitir cortar el gas antes de la cocina para una emergencia o mantención.',
                    _normalizar('flexible para gas 1/2 pulgada x 1 m'): 'Conectar el artefacto a la red fija solo cuando sea compatible y certificado.',
                    _normalizar('sellador de roscas para gas 50 ml'): 'Sellar uniones roscadas compatibles según la indicación del fabricante.',
                },
            },
            {
                'nombre': 'Prueba y verificación',
                'busquedas': [
                    'detector de fugas para gas spray 250 ml',
                    'manometro para prueba de presion de gas',
                ],
                'usos': {
                    _normalizar('detector de fugas para gas spray 250 ml'): 'Ayudar a detectar fugas durante la revisión realizada por el instalador.',
                    _normalizar('manometro para prueba de presion de gas'): 'Verificar la presión de la instalación durante las pruebas técnicas.',
                },
            },
            {
                'nombre': 'Herramientas recomendadas',
                'busquedas': [
                    'llave de cañeria ajustable 12 pulgadas',
                ],
                'usos': {
                    _normalizar('llave de cañeria ajustable 12 pulgadas'): 'Ajustar conexiones compatibles durante el montaje profesional.',
                },
            },
        ]
    if es_iluminacion_exterior_con_sensor:
        # Una instalación exterior debe partir por la luminaria solicitada.
        # No se asume un enchufe ni la capacidad del tablero: ambos dependen
        # de cómo está resuelto el circuito existente.
        tareas = [
            {
                'nombre': 'Luminaria y control',
                'busquedas': [
                    'aplique LED exterior IP65 12 W',
                    'sensor movimiento exterior 180 grados',
                ],
                'usos': {
                    _normalizar('aplique LED exterior IP65 12 W'): 'Iluminar el acceso o sector exterior expuesto a la intemperie.',
                    _normalizar('sensor movimiento exterior 180 grados'): 'Encender la luminaria al detectar movimiento, cuando sea compatible con el circuito.',
                },
            },
            {
                'nombre': 'Canalización y conexión exterior',
                'busquedas': [
                    'conduit PVC electrico 20 mm x 3 m',
                    'cable electrico 1,5 mm2 rollo 100 m',
                    'caja estanca electrica 100 x 100 mm',
                ],
                'usos': {
                    _normalizar('conduit PVC electrico 20 mm x 3 m'): 'Proteger el recorrido del cable en una instalación exterior.',
                    _normalizar('cable electrico 1,5 mm2 rollo 100 m'): 'Conducir la energía hacia la luminaria según el circuito validado.',
                    _normalizar('caja estanca electrica 100 x 100 mm'): 'Resguardar las uniones de cables frente a humedad y polvo.',
                },
            },
            {
                'nombre': 'Fijación',
                'busquedas': [
                    'kit fijacion para hormigon y ladrillo pack 10',
                ],
                'usos': {
                    _normalizar('kit fijacion para hormigon y ladrillo pack 10'): 'Fijar la luminaria o su soporte a un muro firme.',
                },
            },
            {
                'nombre': 'Herramientas recomendadas',
                'busquedas': [
                    'taladro percutor',
                    'alicate universal aislado',
                ],
                'usos': {
                    _normalizar('taladro percutor'): 'Perforar el muro para instalar el soporte y la canalización.',
                    _normalizar('alicate universal aislado'): 'Manipular conductores solo durante una intervención segura y desenergizada.',
                },
            },
        ]
    if es_quincho_estandar:
        # Una referencia de quincho debe mostrar el sistema completo y no una
        # muestra abreviada dependiente de cuántas etapas devolvió Gemini.
        tareas = [
            {
                'nombre': 'Preparación, base y radier',
                'busquedas': [
                    'base estabilizada radier saco 25 kg',
                    'polietileno construccion 200 micras',
                    'malla electrosoldada C92',
                    'hormigon predosificado H20 saco 25 kg',
                    'madera moldaje radier',
                    'clavo corriente moldaje',
                ],
                'usos': {
                    _normalizar('base estabilizada radier saco 25 kg'): 'Preparar y nivelar el terreno bajo el radier.',
                    _normalizar('polietileno construccion 200 micras'): 'Formar una barrera de humedad bajo el hormigón.',
                    _normalizar('malla electrosoldada C92'): 'Reforzar el radier de acuerdo con el diseño del proyecto.',
                    _normalizar('hormigon predosificado H20 saco 25 kg'): 'Construir la losa o radier que sirve de base al quincho.',
                    _normalizar('madera moldaje radier'): 'Formar y contener los bordes del radier durante el hormigonado.',
                    _normalizar('clavo corriente moldaje'): 'Armar y fijar temporalmente el moldaje del radier.',
                },
            },
            {
                'nombre': 'Muretes y albañilería',
                'busquedas': [
                    'ladrillo fiscal',
                    'mortero pega ladrillos saco 25 kg',
                ],
                'usos': {
                    _normalizar('ladrillo fiscal'): 'Levantar los muretes y cerramientos de albañilería.',
                    _normalizar('mortero pega ladrillos saco 25 kg'): 'Asentar y unir los ladrillos de los muretes.',
                },
            },
            {
                'nombre': 'Zona de fuego',
                'busquedas': [
                    'ladrillo refractario',
                    'mortero refractario',
                    'parrilla acero inoxidable quincho',
                    'campana humo quincho',
                    'ducto chimenea quincho',
                ],
                'usos': {
                    _normalizar('ladrillo refractario'): 'Revestir el sector interior expuesto directamente al calor.',
                    _normalizar('mortero refractario'): 'Unir los ladrillos de la zona de fuego.',
                    _normalizar('parrilla acero inoxidable quincho'): 'Sostener los alimentos sobre la zona de cocción.',
                    _normalizar('campana humo quincho'): 'Captar el humo generado sobre la zona de fuego.',
                    _normalizar('ducto chimenea quincho'): 'Evacuar el humo captado hacia el exterior de forma segura.',
                },
            },
            {
                'nombre': 'Estructura de techumbre',
                'busquedas': [
                    'perfil tubular acero 80 x 80 x 3 mm',
                    'perfil costanera acero 100 x 50 x 2 mm',
                    'perno anclaje expansion M12',
                    'electrodo soldadura E6013',
                    'anticorrosivo metal exterior',
                ],
                'usos': {
                    _normalizar('perfil tubular acero 80 x 80 x 3 mm'): 'Formar los pilares principales de la techumbre.',
                    _normalizar('perfil costanera acero 100 x 50 x 2 mm'): 'Sostener la cubierta entre los apoyos principales.',
                    _normalizar('perno anclaje expansion M12'): 'Anclar los pilares metálicos a una base firme de hormigón.',
                    _normalizar('electrodo soldadura E6013'): 'Realizar las uniones soldadas de la estructura metálica.',
                    _normalizar('anticorrosivo metal exterior'): 'Proteger la estructura metálica frente a corrosión e intemperie.',
                },
            },
            {
                'nombre': 'Cubierta y fijaciones',
                'busquedas': [
                    'plancha zinc acanalado 0,35 mm x 3 m',
                    'tornillo techo autoperforante 12 x 2 pulgadas',
                    'cumbrera galvanizada 0,35 mm x 2 m',
                    'cinta butilica impermeable',
                ],
                'usos': {
                    _normalizar('plancha zinc acanalado 0,35 mm x 3 m'): 'Cubrir la parte superior del quincho.',
                    _normalizar('tornillo techo autoperforante 12 x 2 pulgadas'): 'Fijar las planchas a la estructura metálica.',
                    _normalizar('cumbrera galvanizada 0,35 mm x 2 m'): 'Cerrar el encuentro superior de las aguas del techo.',
                    _normalizar('cinta butilica impermeable'): 'Sellar traslapes y encuentros expuestos al agua.',
                },
            },
            {
                'nombre': 'Evacuación de aguas lluvia',
                'busquedas': [
                    'canaleta aguas lluvia',
                    'bajada aguas lluvia PVC',
                ],
                'usos': {
                    _normalizar('canaleta aguas lluvia'): 'Recoger el agua que escurre desde la cubierta.',
                    _normalizar('bajada aguas lluvia PVC'): 'Conducir el agua recogida desde la canaleta hasta la descarga.',
                },
            },
            {
                'nombre': 'Seguridad recomendada',
                'busquedas': [
                    'extintor ABC 6 kg',
                ],
                'usos': {
                    _normalizar('extintor ABC 6 kg'): 'Disponer de protección inicial ante un principio de incendio.',
                },
            },
        ]
    if es_porton_automatico:
        # La propuesta debe representar el sistema completo. Lo que no exista
        # quedará declarado como faltante en vez de ocultarse.
        tareas = [
            {
                "nombre": "Estructura y anclaje",
                "busquedas": [
                    "perfil tubular acero 80 x 80 x 3 mm",
                    "perno anclaje expansion M12 x 120 mm",
                ],
            },
            {
                "nombre": "Hoja y cerramiento del portón",
                "busquedas": [
                    "hoja porton corredera vehicular",
                    "panel cerco electrosoldado 2,50 x 2 m",
                ],
            },
            {
                "nombre": "Rodadura y recorrido",
                "busquedas": [
                    "riel porton corredera",
                    "rueda porton corredera",
                    "tope mecanico final de carrera",
                ],
            },
            {
                "nombre": "Automatización y seguridad",
                "busquedas": [
                    "motor porton corredera hasta 600 kg",
                    "cremallera nylon porton automatico",
                    "fotocelda seguridad porton automatico",
                    "control remoto porton automatico 433 MHz",
                ],
            },
            {
                "nombre": "Alimentación y protección eléctrica",
                "busquedas": [
                    "conduit PVC electrico 20 mm",
                    "cable electrico 2,5 mm2",
                    "interruptor automatico 16 A curva C",
                ],
            },
        ]
    # Los catálogos estándar especializados reemplazan las etapas de Gemini
    # para asegurar el sistema completo, pero deben conservar las herramientas
    # que la IA identificó para ejecutar ese proyecto.
    if (es_bodega_estandar or es_quincho_estandar or es_porton_automatico):
        herramientas_estandar = _lista_textos(datos.get("herramientas_proyecto"), 8, 80)
        busquedas_usadas = sum(len(tarea.get("busquedas") or []) for tarea in tareas)
        herramientas_estandar = herramientas_estandar[:max(0, MAX_BUSQUEDAS - busquedas_usadas)]
        if herramientas_estandar:
            tareas = tareas[:max(0, MAX_TAREAS - 1)]
            tareas.append({
                "nombre": "Herramientas recomendadas",
                "busquedas": herramientas_estandar,
            })
    # El modo estandar omite cuestionarios y aplica supuestos, por lo que solo
    # puede activarlo una solicitud explicita ya validada por Django. Un
    # proyecto integral puede seguir usando un catalogo completo sin afirmar
    # que el cliente pidio una propuesta estandar.
    modo_estandar = datos.get("_proyecto_estandar") is True
    contexto_reparacion_mueble = _normalizar(
        f"{proyecto} {datos.get('_contexto_usuario') or ''} "
        + " ".join(
            busqueda
            for tarea in tareas
            for busqueda in tarea.get("busquedas", [])
        )
    )
    es_reparacion_mueble_madera_con_adhesivo = (
        any(termino in contexto_reparacion_mueble for termino in (
            "mesa", "silla", "mueble", "estante", "repisa", "velador",
        ))
        and "madera" in contexto_reparacion_mueble
        and any(termino in contexto_reparacion_mueble for termino in (
            "adhesivo", "pegamento", "cola fria", "encolar",
        ))
    )
    if es_reparacion_mueble_madera_con_adhesivo and not any(
        "sargento" in _normalizar(busqueda) or "prensa" in _normalizar(busqueda)
        for tarea in tareas
        for busqueda in tarea.get("busquedas", [])
    ):
        tareas.append({
            "nombre": "Herramienta de sujeción recomendada",
            "busquedas": ["prensa sargento acero 6 pulgadas"],
            "usos": {
                _normalizar("prensa sargento acero 6 pulgadas"): (
                    "Mantener la unión inmóvil y bajo presión durante el tiempo de "
                    "secado indicado por el fabricante del adhesivo."
                ),
            },
        })
    tareas = _ajustar_radier_a_condiciones_informadas(
        datos, tareas, modo_estandar,
    )
    _ajustar_cuestionario_quincho(datos)
    tareas = _ajustar_proyecto_ceramica(datos, tareas)
    if not proyecto or not tareas:
        return {
            "tipo": "aclaracion",
            "mensaje": (
                "Puedo analizar ese proyecto, pero necesito que me cuentes qué quieres "
                "construir, reparar o instalar y, si corresponde, sus medidas."
            ),
            "productos": [],
            "maestros": [],
            "sugerencias": [
                "Describe el resultado que necesitas",
                "Indica las medidas disponibles",
            ],
        }

    datos_faltantes_iniciales = _lista_textos(
        datos.get("datos_faltantes_proyecto"), 8, 100
    )
    # Incluso una propuesta cerámica solicitada como "estándar" necesita
    # conocer el ambiente: una pieza para baño, cocina, interior seco o
    # exterior no es intercambiable. Una vez indicada la ubicación, el modo
    # estándar puede continuar dejando medidas y base como supuestos visibles.
    if (
        datos.get("_proyecto_ceramica")
        and modo_estandar
        and not datos.get("_ceramica_ambiente")
    ):
        aplicacion = datos.get("_ceramica_aplicacion") or ""
        ubicacion = (
            "UBICACION DEL PISO" if aplicacion == "piso"
            else "UBICACION DE LA CERAMICA"
        )
        return {
            "tipo": "aclaracion_proyecto",
            "mensaje": "\n".join([
                "PROYECTO",
                proyecto,
                "",
                "ANTES DE PREPARAR LA PROPUESTA ESTANDAR",
                "Necesito conocer la habitacion o ambiente para seleccionar una "
                "ceramica compatible.",
                "",
                ubicacion,
                "• Zona humeda: baño, lavadero o logia.",
                "• Cocina: considera humedad, limpieza y transito frecuente.",
                "• Interior seco: dormitorio, living, comedor o pasillo.",
                "• Exterior: terraza, balcon o patio expuesto al clima.",
                "",
                "RESPONDE EN UN MENSAJE",
                "Ejemplo: “Es para la cocina”. Luego preparare la propuesta "
                "estandar completa y dejare visibles los demas supuestos.",
            ]),
            "productos": [],
            "maestros": [],
            "sugerencias": [
                "Es para la cocina",
                "Es para el baño",
                "Es para un dormitorio",
            ],
        }
    if _es_proyecto_mueble(proyecto) and not modo_estandar:
        faltantes_mueble = []
        if not _tiene_tipo_mueble(proyecto):
            faltantes_mueble.append("Tipo y uso del mueble")
        try:
            dimensiones_mueble = (
                int(datos.get("ancho_cm") or 0),
                int(datos.get("alto_cm") or 0),
                int(datos.get("fondo_cm") or 0),
            )
        except (TypeError, ValueError):
            dimensiones_mueble = (0, 0, 0)
        if not all(dimensiones_mueble):
            faltantes_mueble.append(
                "Dimensiones del espacio disponible (ancho, alto y fondo)"
            )
        if faltantes_mueble:
            lineas = [
                "PROYECTO",
                proyecto,
                "",
                "ANTES DE RECOMENDAR PRODUCTOS",
                "Necesito definir la función y el tamaño antes de seleccionar materiales o herrajes.",
                *_preguntas_guiadas(faltantes_mueble, proyecto),
                "",
                "RESPONDE TODO EN UN MENSAJE",
                "Con esos datos prepararé una propuesta estándar sin inventar el tipo de mueble.",
            ]
            return {
                "tipo": "aclaracion_proyecto",
                "mensaje": "\n".join(lineas),
                "productos": [],
                "maestros": [],
                "sugerencias": _sugerencias_respuesta(
                    proyecto, faltantes_mueble,
                )[:3],
            }
    if datos_faltantes_iniciales and not modo_estandar:
        proyecto_normalizado = _normalizar(proyecto)
        es_piso = any(
            termino in proyecto_normalizado
            for termino in (
                "piso flotante", "piso laminado", "piso de ceramica",
                "piso ceramico", "piso de porcelanato", "piso porcelanato",
            )
        )
        es_revestimiento_ceramico = bool(datos.get("_proyecto_ceramica"))
        faltantes_legibles = [
            faltante.strip().lstrip("¿").rstrip("?.")
            for faltante in datos_faltantes_iniciales
        ]
        lineas = [
            "PROYECTO",
            proyecto,
            "",
            "ANTES DE RECOMENDAR PRODUCTOS",
            "Necesito estos datos para preparar una recomendación completa:",
        ]
        sugerencias = faltantes_legibles[:3]
        if es_piso or es_revestimiento_ceramico:
            for faltante in faltantes_legibles:
                clave = _normalizar(faltante)
                if "aplicacion" in clave and any(
                    material in proyecto_normalizado
                    for material in ("ceramica", "porcelanato")
                ):
                    lineas.extend([
                        "",
                        "APLICACION DE LA CERAMICA",
                        "• Piso: requiere una pieza apta para tránsito y para el ambiente indicado.",
                        "• Pared o muro: utiliza un revestimiento mural compatible con el soporte.",
                    ])
                elif "tipo de piso" in clave:
                    lineas.extend([
                        "",
                        "TIPO DE PISO",
                        "• Laminado: aspecto cálido para espacios interiores secos.",
                        "• Vinílico SPC: más resistente a humedad y fácil de limpiar.",
                        "• Porcelanato: rígido, durable y apto para zonas húmedas.",
                        "• No lo sé: indica en qué habitación se instalará y yo elegiré.",
                    ])
                elif any(termino in clave for termino in (
                    "ubicacion", "habitacion", "ambiente", "donde se instalara",
                )):
                    lineas.extend([
                        "",
                        (
                            "UBICACION DEL PISO"
                            if datos.get("_ceramica_aplicacion") == "piso"
                            else "UBICACION DE LA CERAMICA"
                        ),
                        "• Zona húmeda: baño, lavadero o logia.",
                        "• Interior seco: dormitorio, living, comedor o pasillo.",
                        "• Cocina: considera humedad, limpieza y tránsito frecuente.",
                        "• Exterior: terraza, balcón o patio expuesto al clima.",
                    ])
                elif (
                    "estado" not in clave
                    and "seca" not in clave
                    and "humedad" not in clave
                    and (
                    "base" in clave
                    or "superficie actual" in clave
                    or "contrapiso" in clave
                    )
                ):
                    lineas.extend([
                        "",
                        "BASE ACTUAL",
                        "• Hormigón: superficie gris, dura y continua.",
                        "• Madera/OSB: tablas o paneles de madera prensada.",
                        "• Cerámica: palmetas existentes con juntas visibles.",
                        "• No lo sé: describe el color, la textura y las juntas que ves.",
                    ])
                elif "seca" in clave or "humedad" in clave:
                    lineas.extend([
                        "",
                        "HUMEDAD DE LA BASE",
                        "• Confirma si está seca y libre de humedad visible o ascendente.",
                        "• Si hay humedad, no instales todavía: primero debe identificarse y corregirse su origen.",
                    ])
                elif "estado" in clave:
                    lineas.extend([
                        "",
                        "ESTADO DE LA BASE",
                        "• Bueno: está firme, seca y nivelada.",
                        "• Regular: tiene desniveles pequeños o algunas juntas dañadas.",
                        "• Malo: presenta humedad, grietas, piezas sueltas o desniveles fuertes.",
                        "• No lo sé: cuéntame si ves humedad, grietas o desniveles.",
                    ])
                else:
                    lineas.append(f"• {faltante}")
            lineas.extend([
                "",
                "RESPONDE TODO EN UN MENSAJE",
                "Ejemplo: “Es un dormitorio seco, quiero que tú elijas el piso, "
                "la base es de hormigón y está firme, seca y nivelada”.",
            ])
            sugerencias = []
            claves_faltantes = [_normalizar(item) for item in faltantes_legibles]
            if any("aplicacion" in clave for clave in claves_faltantes):
                sugerencias.extend([
                    "La cerámica será para el piso",
                    "La cerámica será para una pared",
                ])
            if any(any(termino in clave for termino in (
                "medida", "dimension", "superficie", "metros cuadrados",
                "ancho", "largo",
            )) for clave in claves_faltantes):
                sugerencias.append("El piso mide 4 x 6 metros")
            if any(any(termino in clave for termino in (
                "ubicacion", "habitacion", "ambiente", "donde se instalara",
            )) for clave in claves_faltantes):
                sugerencias.append("Es para la cocina")
            if any(
                "estado" not in clave
                and any(termino in clave for termino in (
                    "base", "superficie actual", "contrapiso",
                ))
                for clave in claves_faltantes
            ):
                sugerencias.extend([
                    "La base es de hormigón",
                    "No sé identificar la base",
                ])
            if any("estado" in clave for clave in claves_faltantes):
                sugerencias.append("La base está firme, seca y nivelada")
            sugerencias = sugerencias[:3]
        else:
            lineas.extend(_preguntas_guiadas(faltantes_legibles, proyecto))
            lineas.extend([
                "",
                "RESPONDE TODO EN UN MENSAJE",
                "Así podré entregar productos, cantidades y costos en una sola respuesta.",
            ])
            sugerencias = _sugerencias_respuesta(proyecto, faltantes_legibles)
        return {
            "tipo": "aclaracion_proyecto",
            "mensaje": "\n".join(lineas),
            "productos": [],
            "maestros": [],
            "sugerencias": sugerencias[:3],
        }

    material_principal_faltante = ""
    material_principal = _texto_seguro(
        datos.get("material_principal_proyecto"), 100
    )
    # La plantilla cerámica ya contiene el revestimiento solicitado. Evita que
    # la interpretación de Gemini lo inserte nuevamente como "Material
    # principal" y desplace los separadores a una etapa incorrecta.
    if datos.get("_proyecto_ceramica"):
        material_principal = ""
    if material_principal:
        principal_normalizado = _normalizar(material_principal)
        familias_cubierta = {'teja', 'zinc', 'policarbonato'}
        familia_exigida = next((
            familia for familia in familias_cubierta
            if familia in principal_normalizado
        ), None)
        if familia_exigida:
            tareas_filtradas = []
            for tarea in tareas:
                busquedas = [
                    busqueda for busqueda in tarea['busquedas']
                    if not any(
                        familia != familia_exigida
                        and familia in _normalizar(busqueda)
                        for familia in familias_cubierta
                    )
                ]
                if busquedas:
                    tareas_filtradas.append({**tarea, 'busquedas': busquedas})
            tareas = tareas_filtradas
        consultas_principales = _consultas_catalogo_equivalentes(material_principal)
        candidatos_principales = []
        coincidencias_principales = {}
        for consulta_principal in consultas_principales:
            directos = _candidatos_directos(consulta_principal)
            ids_directos = {producto.pk for producto in directos}
            for producto in [
                *directos,
                *(producto for producto in buscar_productos(consulta_principal)
                  if producto.pk not in ids_directos),
            ]:
                if producto.pk not in coincidencias_principales:
                    candidatos_principales.append(producto)
                    coincidencias_principales[producto.pk] = []
                coincidencias_principales[producto.pk].append(consulta_principal)
        principal_disponible = next((
            producto for producto in candidatos_principales
            if producto.stock > 0
            and any(
                _coincidencia_suficiente(producto, consulta_principal)
                for consulta_principal in coincidencias_principales[producto.pk]
            )
        ), None)
        if principal_disponible is None:
            material_principal_faltante = material_principal
        if not any(
            any(
                _normalizar(consulta_principal) in _normalizar(busqueda)
                or _normalizar(busqueda) in _normalizar(consulta_principal)
                for consulta_principal in consultas_principales
            )
            for tarea in tareas for busqueda in tarea["busquedas"]
        ):
            tareas.insert(0, {
                "nombre": "Material principal",
                "busquedas": [material_principal],
            })
            tareas = tareas[:MAX_TAREAS]

    productos = []
    productos_usados = set()
    faltantes = [material_principal_faltante] if material_principal_faltante else []
    faltantes_detalle = []
    sin_stock_detalle = []
    cantidades_calculadas = []
    texto_plan = [proyecto]
    try:
        superficie_m2 = Decimal(str(datos.get("superficie") or 0))
    except Exception:
        superficie_m2 = Decimal("0")
    try:
        ancho_m = Decimal(str(datos.get("ancho_cm") or 0)) / Decimal("100")
        fondo_m = Decimal(str(datos.get("fondo_cm") or 0)) / Decimal("100")
        superficie_planta = ancho_m * fondo_m
        perimetro_m = (ancho_m + fondo_m) * Decimal("2")
        superficie_muros = Decimal(str(datos.get("superficie_muros") or 0))
    except Exception:
        superficie_planta = perimetro_m = superficie_muros = Decimal("0")

    for tarea in tareas:
        texto_plan.append(tarea["nombre"])
        for consulta in tarea["busquedas"]:
            texto_plan.append(consulta)
            consultas_catalogo = _consultas_catalogo_equivalentes(consulta)
            if re.search(r'\b(?:embutid[oa]|empotrad[oa])\b', _normalizar(consulta)):
                consultas_catalogo = [consulta]
            candidatos = []
            coincidencias_catalogo = {}
            for consulta_catalogo in consultas_catalogo:
                candidatos_directos = _candidatos_directos(consulta_catalogo)
                ids_directos = {producto.pk for producto in candidatos_directos}
                candidatos_consulta = candidatos_directos + [
                    producto for producto in buscar_productos(consulta_catalogo)
                    if producto.pk not in ids_directos
                ]
                for candidato in candidatos_consulta:
                    if candidato.pk not in coincidencias_catalogo:
                        candidatos.append(candidato)
                        coincidencias_catalogo[candidato.pk] = []
                    coincidencias_catalogo[candidato.pk].append(consulta_catalogo)
            es_iluminacion = any(termino in contexto_inicial for termino in (
                'iluminacion', 'luminaria', 'foco', 'luces exterior',
            ))
            consulta_normalizada = _normalizar(consulta)
            if es_iluminacion and not any(
                termino in (contexto_usuario + ' ' + contexto_proyecto)
                for termino in ('enchufe', 'tomacorriente')
            ):
                if re.search(r'\b(?:enchufe|tomacorriente)\w*\b', consulta_normalizada):
                    continue
                candidatos = [c for c in candidatos if not re.search(
                    r'\b(?:enchufe|tomacorriente)\w*\b', _normalizar(c.nombre),
                )]
            if es_iluminacion and re.search(r'\bsolar\w*\b', consulta_normalizada):
                candidatos = [c for c in candidatos if re.search(
                    r'\bsolar\w*\b', _normalizar(
                        ' '.join((c.nombre or '', c.descripcion or '', c.uso_recomendado or ''))
                    ),
                )]
            if es_iluminacion and re.search(r'\b(?:embutid[oa]|empotrad[oa])\b', consulta_normalizada):
                candidatos = [c for c in candidatos if re.search(
                    r'\b(?:embutid[oa]|empotrad[oa])\b', _normalizar(
                        ' '.join((c.nombre or '', c.descripcion or '', c.uso_recomendado or ''))
                    ),
                )]
            if es_contexto_gas:
                candidatos = [
                    candidato for candidato in candidatos
                    if not _producto_incompatible_con_gas(candidato)
                ]
            if (
                datos.get("_proyecto_ceramica")
                and "herramienta" not in _normalizar(tarea["nombre"])
            ):
                candidatos = [
                    candidato for candidato in candidatos
                    if "herramienta" not in _normalizar(candidato.categoria)
                ]
            if (
                datos.get("_proyecto_ceramica")
                and _normalizar(tarea["nombre"]) == "revestimiento principal"
            ):
                candidatos = [
                    candidato for candidato in candidatos
                    if _producto_compatible_con_revestimiento_ceramico(
                        candidato, datos, consulta,
                    )
                ]
            if _normalizar(tarea["nombre"]) == "cubierta":
                accesorios_cubierta = {
                    "perfil", "union", "cierre", "tornillo", "golilla",
                    "clavo", "sellador", "silicona", "cinta", "canaleta", "bajada",
                }
                candidatos = [
                    candidato for candidato in candidatos
                    if not (
                        set(_palabras_consulta(candidato.nombre))
                        & accesorios_cubierta
                    )
                ]
            # Si una etapa posterior vuelve a pedir el mismo producto ya
            # seleccionado, no se duplica ni se informa falsamente como ausente.
            if any(
                candidato.pk in productos_usados
                and _normalizar(consulta) in _normalizar(candidato.nombre)
                for candidato in candidatos
            ):
                continue
            if (es_iluminacion and any(
                candidato.pk in productos_usados
                and any(_coincidencia_suficiente(candidato, q)
                        for q in coincidencias_catalogo[candidato.pk])
                for candidato in candidatos
            )):
                continue
            disponibles = [
                candidato for candidato in candidatos
                if (
                    candidato.pk not in productos_usados
                    and not _es_herramienta_equivalente_ya_elegida(
                        candidato, productos,
                    )
                    and candidato.stock > 0
                    and any(
                        _coincidencia_suficiente(candidato, consulta_catalogo)
                        for consulta_catalogo in coincidencias_catalogo[candidato.pk]
                    )
                )
            ]
            # Ya se mostró una herramienta equivalente (por ejemplo una pala)
            # desde otra etapa. No la declares como faltante ni la repitas.
            if (
                not disponibles
                and any(
                    _es_herramienta_equivalente_ya_elegida(candidato, productos)
                    for candidato in candidatos
                )
            ):
                continue
            hay_medidas = any((superficie_m2, superficie_planta, superficie_muros))
            producto = max(
                disponibles,
                key=lambda candidato: (
                    max(
                        _puntaje_directo(candidato, consulta_catalogo)
                        for consulta_catalogo in coincidencias_catalogo[candidato.pk]
                    ),
                    int(bool(
                        hay_medidas
                        and candidato.informacion_tecnica_verificada
                        and candidato.tipo_calculo == "superficie"
                        and candidato.rendimiento
                        and candidato.unidad_rendimiento == "m2_unidad"
                    )),
                ),
                default=None,
            )
            if producto is None:
                agotados = [
                    candidato for candidato in candidatos
                    if (
                        candidato.stock <= 0
                        and any(
                            _coincidencia_suficiente(candidato, consulta_catalogo)
                            for consulta_catalogo in coincidencias_catalogo[candidato.pk]
                        )
                    )
                ]
                if agotados:
                    sin_stock_detalle.append({
                        "nombre": agotados[0].nombre,
                        "etapa": tarea["nombre"],
                        "uso": tarea.get("usos", {}).get(
                            _normalizar(consulta),
                            f"Se utiliza en la etapa «{tarea['nombre']}» del proyecto.",
                        ),
                    })
                    continue
                if consulta not in faltantes:
                    faltantes.append(consulta)
                uso_faltante = tarea.get("usos", {}).get(
                    _normalizar(consulta),
                    f"Se utiliza en la etapa «{tarea['nombre']}» del proyecto.",
                )
                faltantes_detalle.append({
                    "nombre": consulta,
                    "etapa": tarea["nombre"],
                    "uso": uso_faltante,
                })
                continue
            item = producto_publico(producto)
            uso_material = tarea.get("usos", {}).get(
                _normalizar(consulta),
                _texto_seguro(producto.uso_recomendado, 180)
                or f"Se incluye como apoyo para la etapa «{tarea['nombre']}».",
            )
            if (es_iluminacion and 'conduit' in _normalizar(producto.nombre)
                    and re.search(r'\b(?:subterrane\w*|enterrad\w*)\b', _normalizar(uso_material))):
                uso_material = (
                    'Canalizar conductores en una instalación compatible; el uso '
                    'enterrado debe confirmarse en la ficha del fabricante y por '
                    'un instalador eléctrico autorizado.'
                )
            if (es_iluminacion and 'caja estanca' in _normalizar(producto.nombre)
                    and re.search(r'\b(?:suelo|subterrane\w*|enterrad\w*)\b', _normalizar(uso_material))):
                uso_material = (
                    'Proteger conexiones frente a humedad y polvo según la ficha; '
                    'la aptitud para instalación enterrada debe verificarse.'
                )
            if (es_iluminacion and 'estaca' in _normalizar(producto.nombre)):
                uso_material = (
                    'Iluminar senderos o zonas de jardín como alternativa de estaca; '
                    'confirma alimentación, grado de protección y ubicación. '
                    'No es una luminaria empotrada al ras del suelo.'
                )
            es_herramienta_opcional = (
                "herramienta" in _normalizar(tarea["nombre"])
                or "herramienta" in _normalizar(producto.categoria)
            )
            es_nivelacion_opcional = (
                datos.get("_proyecto_ceramica")
                and any(termino in _normalizar(producto.nombre) for termino in (
                    "sistema nivelador", "cunas reutilizables nivelador",
                ))
            )
            item.update({
                "rol": tarea["nombre"],
                "detalle_material": uso_material,
                "uso_en_proyecto": uso_material,
                "carrito_cantidad": 1 if es_herramienta_opcional else 0,
                "recomendacion_orientativa": True,
                "cantidad_pendiente": not es_herramienta_opcional,
                "es_opcional": es_herramienta_opcional or es_nivelacion_opcional,
            })
            if es_reparacion_mueble_madera_con_adhesivo:
                identidad_producto = _normalizar(
                    f"{producto.nombre} {producto.categoria}"
                )
                if any(termino in identidad_producto for termino in (
                    "adhesivo para madera", "cola fria", "pegamento para madera",
                )):
                    item.update({
                        "carrito_cantidad": 1,
                        "cantidad_pendiente": False,
                        "es_alternativa": (
                            "alternativa" in _normalizar(tarea["nombre"])
                        ),
                        "presentacion_sugerida": (
                            "Presentación sugerida: 1 envase. El consumo real depende del "
                            "tamaño y estado de la unión."
                        ),
                    })
                elif "lija" in identidad_producto:
                    item.update({
                        "carrito_cantidad": 1,
                        "cantidad_pendiente": False,
                        "es_opcional": True,
                        "presentacion_sugerida": (
                            "Preparación opcional: 1 paquete, solo si hay residuos de "
                            "adhesivo antiguo que deban retirarse suavemente."
                        ),
                    })
                elif any(termino in identidad_producto for termino in (
                    "tornillo", "escuadra", "perno",
                )):
                    item.update({
                        "carrito_cantidad": 0,
                        "cantidad_pendiente": True,
                        "es_opcional": True,
                        "incluido_en_total": False,
                        "bloquear_carrito": True,
                        "presentacion_sugerida": (
                            "Refuerzo opcional pendiente de verificar dimensiones y tipo "
                            "de unión; no comprar antes de esa comprobación."
                        ),
                    })
            base_calculo = tarea.get("bases", {}).get(
                _normalizar(consulta), 'referencial',
            )
            if base_calculo == 'referencial' and producto.tipo_calculo == 'superficie':
                contexto_base = _normalizar(f"{tarea['nombre']} {consulta}")
                if any(termino in contexto_base for termino in (
                    'cubierta', 'techo', 'techumbre', 'plancha zinc',
                )):
                    base_calculo = 'superficie_cubierta'
                elif any(termino in contexto_base for termino in (
                    'muro', 'muros', 'pared', 'revestimiento vertical',
                )):
                    base_calculo = 'superficie_muros'
                elif any(termino in contexto_base for termino in (
                    'piso', 'radier', 'base', 'baldosa', 'malla', 'polietileno',
                )):
                    base_calculo = 'superficie_piso'
                elif superficie_m2 > 0:
                    base_calculo = 'superficie_general'
            superficie_base = {
                'superficie_piso': superficie_planta or superficie_m2,
                'superficie_cubierta': superficie_planta or superficie_m2,
                'superficie_muros': superficie_muros,
                'superficie_general': superficie_m2,
            }.get(base_calculo, Decimal("0"))
            if (
                superficie_base > 0
                and producto.informacion_tecnica_verificada
                and producto.tipo_calculo == "superficie"
                and producto.rendimiento
                and producto.unidad_rendimiento == "m2_unidad"
            ):
                margen = Decimal(producto.porcentaje_desperdicio or 0) / Decimal("100")
                cantidad = int((
                    superficie_base * (Decimal("1") + margen)
                    / Decimal(producto.rendimiento)
                ).to_integral_value(rounding=ROUND_CEILING))
                if cantidad > 0:
                    item.update({
                        "cantidad_requerida": cantidad,
                        "carrito_cantidad": min(cantidad, producto.stock),
                        "subtotal": cantidad * producto.precio,
                        "recomendacion_orientativa": False,
                        "cantidad_pendiente": False,
                        "detalle_material": (
                            f"{cantidad} unidad(es) para {superficie_base:g} m² de "
                            f"{base_calculo.replace('_', ' ')} con "
                            f"{producto.porcentaje_desperdicio:g}% de margen."
                        ),
                        "base_calculo": base_calculo,
                        "medida_base": f"{superficie_base:g} m²",
                    })
                    cantidades_calculadas.append(
                        f"{cantidad} unidad(es) de {producto.nombre} para "
                        f"{superficie_base:g} m² de {base_calculo.replace('_', ' ')}"
                    )
                    if cantidad > producto.stock:
                        faltantes.append(
                            f"{producto.nombre}: se requieren {cantidad} y hay "
                            f"{producto.stock} en stock"
                        )
            productos.append(item)
            productos_usados.add(producto.pk)

    if datos.get("_consulta_solo_herramientas"):
        herramientas = [
            producto for producto in productos
            if (
                "herramienta" in _normalizar(producto.get("rol"))
                or any(clase in _normalizar(producto.get("categoria")) for clase in (
                    "herramienta", "seguridad",
                ))
            )
        ]
        herramientas_sugeridas = _lista_textos(
            datos.get("herramientas_proyecto"), 3, 100,
        )
        for herramienta in herramientas:
            herramienta["rol"] = "Herramienta recomendada"
            herramienta["es_opcional"] = True
            herramienta["carrito_cantidad"] = 1
        total_herramientas = sum(
            (herramienta.get("precio") or 0 for herramienta in herramientas),
            0,
        )
        return {
            "tipo": "seguimiento_herramientas",
            "modo_orientacion": "propuesta_directa",
            "mensaje": (
                "HERRAMIENTAS PARA TU PROYECTO\n"
                + (
                    "\n".join(
                        f"• {herramienta['nombre']}: "
                        f"{herramienta.get('uso_en_proyecto') or 'apoyo para realizar el trabajo.'}"
                        for herramienta in herramientas
                    )
                    if herramientas
                    else (
                        "ORIENTACIÓN RECOMENDADA\n"
                        + "\n".join(
                            f"• {herramienta}: se usa para realizar esta tarea."
                            for herramienta in herramientas_sugeridas
                        )
                        + "\n\nNo encontré estas herramientas con stock en SFI."
                        if herramientas_sugeridas
                        else "No encontré herramientas suficientemente relacionadas con stock."
                    )
                )
                + (
                    f"\n\nCOSTO OPCIONAL\n{_formatear_clp(total_herramientas)} CLP "
                    "considerando una unidad de cada herramienta."
                    if herramientas else ""
                )
                + "\n\nNo modifiqué los materiales ni las decisiones del proyecto actual."
            ),
            "productos": herramientas,
            "maestros": [],
            "tareas": [],
            "especialidades": [],
            "faltantes_catalogo": [],
            "total_calculado": 0,
            "total_herramientas_opcionales": total_herramientas,
            "calculo_orientativo": True,
            "sugerencias": [
                "Volver al resumen del proyecto",
                "Muéstrame alternativas más económicas",
            ],
        }

    especialidades = _especialidades_validas(
        datos,
        " ".join(texto_plan),
        resolver_especialidad,
    )
    comuna = _texto_seguro(datos.get("comuna_maestro"), 100)
    maestros = []
    maestros_usados = set()
    if comuna:
        for especialidad in especialidades:
            for maestro in buscar_maestros(especialidad, comuna, limite=MAX_MAESTROS):
                if maestro["id"] not in maestros_usados:
                    maestros.append(maestro)
                    maestros_usados.add(maestro["id"])
                if len(maestros) >= MAX_MAESTROS:
                    break
            if len(maestros) >= MAX_MAESTROS:
                break

    datos_faltantes = (
        [] if modo_estandar
        else _lista_textos(datos.get("datos_faltantes_proyecto"), 3, 100)
    )
    proyecto_normalizado = _normalizar(proyecto)
    falta_base_piso = (
        any(termino in proyecto_normalizado for termino in ("piso flotante", "piso laminado"))
        and any(
            "base" in _normalizar(faltante) or "contrapiso" in _normalizar(faltante)
            for faltante in datos_faltantes
        )
    )
    productos_con_cantidad = [
        producto for producto in productos
        if not producto.get("recomendacion_orientativa")
        and producto.get("cantidad_requerida")
        and producto.get("subtotal") is not None
    ]
    total_calculado = sum(
        (producto["subtotal"] for producto in productos_con_cantidad),
        Decimal("0"),
    )
    productos_materiales = [
        producto for producto in productos
        if "herramienta" not in _normalizar(producto.get("rol"))
    ]
    cantidad_referenciales = len(productos_materiales) - len(productos_con_cantidad)
    partes = [
        "PROYECTO\n"
        f"Analicé “{proyecto}” en {len(tareas)} "
        f"{'etapa' if len(tareas) == 1 else 'etapas'}.",
        (
            "RESULTADO\n"
            f"Encontré {len(productos)} producto(s) reales con stock en SFI."
            if productos
            else (
                "RESULTADO\n"
                "No encontré productos con stock suficientemente relacionados."
            )
        ),
    ]
    if productos and not modo_estandar:
        etapas_productos = []
        roles_agregados = set()
        for tarea in tareas:
            nombre_etapa = tarea["nombre"]
            materiales = [
                producto for producto in productos
                if producto.get("rol") == nombre_etapa
            ]
            if not materiales:
                continue
            roles_agregados.add(nombre_etapa)
            etapas_productos.append(nombre_etapa)
            etapas_productos.extend(
                f"• {producto['nombre']} — "
                f"{producto.get('uso_en_proyecto') or producto.get('detalle_material') or 'Apoyo para esta etapa del proyecto.'}"
                for producto in materiales
            )

        # Conserva visibles los productos adicionales que no provengan de una
        # tarea explícita, sin inventarles una etapa ni una finalidad nueva.
        productos_sin_etapa = [
            producto for producto in productos
            if producto.get("rol") not in roles_agregados
        ]
        if productos_sin_etapa:
            etapas_productos.append("Complementos recomendados")
            etapas_productos.extend(
                f"• {producto['nombre']} — "
                f"{producto.get('uso_en_proyecto') or producto.get('detalle_material') or 'Complemento disponible para el proyecto.'}"
                for producto in productos_sin_etapa
            )

        if etapas_productos:
            partes.append(
                "MATERIALES Y PARA QUÉ SE USAN\n"
                + "\n".join(etapas_productos)
            )
    if modo_estandar:
        partes = [(
            "PROPUESTA ESTÁNDAR PARA TU PROYECTO\n"
            f"Preparé una alternativa de “{proyecto}” organizada en {len(tareas)} "
            f"{'etapa' if len(tareas) == 1 else 'etapas'}. "
            "Todos los productos mostrados están disponibles actualmente en SFI. "
            "Es una configuración base: si cambias una medida, material o condición, "
            "indícalo y actualizaré la propuesta."
        )]
        if datos_faltantes_iniciales:
            partes.append(
                "SUPUESTOS DE LA PROPUESTA ESTÁNDAR\n"
                "No detuve la propuesta para pedir estos datos porque solicitaste una "
                "alternativa estándar:\n"
                + "\n".join(
                    f"• {faltante}: se mantiene como referencia y no se usará para "
                    "inventar una cantidad exacta."
                    for faltante in datos_faltantes_iniciales
                )
                + "\nSi indicas alguno de estos datos, actualizaré la misma propuesta "
                "sin perder el resto del contexto."
            )
        condiciones_radier = datos.get("_radier_condiciones") or {}
        if condiciones_radier:
            espesor = (
                condiciones_radier.get("espesor")
                or condiciones_radier.get("espesor_estandar")
            )
            lineas_condiciones = []
            if condiciones_radier.get("espesor_estandar"):
                lineas_condiciones.append(
                    f"• Como no indicaste el espesor, usé {espesor} como referencia "
                    "estándar. Si lo cambias, deben recalcularse materiales y costos."
                )
            elif espesor:
                lineas_condiciones.append(f"• Espesor informado: {espesor}.")
            if condiciones_radier.get("base_hormigon_existente"):
                lineas_condiciones.extend([
                    "• Respeté la base de hormigón existente y excluí materiales "
                    "destinados a preparar terreno natural.",
                    "• Antes de ejecutar una nueva capa deben revisarse adherencia, "
                    "grietas, juntas, desniveles, humedad y diferencias de altura.",
                ])
            if lineas_condiciones:
                partes.append(
                    "CONDICIONES Y SUPUESTOS DE LA PROPUESTA\n"
                    + "\n".join(lineas_condiciones)
                )
        tipo_base_ceramica = datos.get("_ceramica_tipo_base") or ""
        if datos.get("_proyecto_ceramica") and tipo_base_ceramica:
            mensajes_base = {
                "hormigon_radier": (
                    "Confirmaste una base de hormigón, losa o radier. Debe estar curada, "
                    "limpia, firme, seca, nivelada y libre de polvo, grasa, pintura y grietas activas."
                ),
                "mortero_sobrelosa": (
                    "Confirmaste una sobrelosa o mortero de nivelación. Antes de revestir, "
                    "verifica curado, adherencia, humedad, planitud y ausencia de fisuras activas."
                ),
                "ceramica_existente": (
                    "La base es cerámica existente. No debe cubrirse sin comprobar piezas "
                    "sueltas o huecas, adherencia, limpieza y compatibilidad del promotor y adhesivo."
                ),
                "madera_osb": (
                    "La base es madera u OSB. No se considera apta para pegar cerámica "
                    "directamente sin verificar rigidez y definir una placa o sistema de desacople compatible."
                ),
                "fibrocemento": (
                    "La base es fibrocemento. Confirma que la placa, sus fijaciones y juntas "
                    "sean aptas para recibir cerámica en el ambiente indicado."
                ),
                "base_cementicia_probable": (
                    "Por la descripción, la base parece ser de hormigón, radier o mortero "
                    "cementicio. Preparé la propuesta para una base cementicia; si no "
                    "corresponde, indícalo para ajustar los materiales."
                ),
            }
            mensaje_base = mensajes_base.get(tipo_base_ceramica)
            if mensaje_base:
                partes.append("BASE INTERPRETADA\n" + mensaje_base)
        if productos:
            etapas = []
            for tarea in tareas:
                materiales = [
                    producto for producto in productos
                    if producto['rol'] == tarea['nombre']
                ]
                if materiales:
                    etapas.extend([
                        tarea['nombre'],
                        *(f"• {producto['nombre']} — {producto['uso_en_proyecto']}"
                          for producto in materiales),
                    ])
            partes.append("PRODUCTOS POR ETAPA\n" + "\n".join(etapas))
            partes.append(
                f"EN RESUMEN\nEncontré {len(productos)} productos reales con stock para esta propuesta."
            )
    if es_reparacion_mueble_madera_con_adhesivo:
        partes.append(
            "CÓMO ELEGIR EL ADHESIVO\n"
            "Las colas para madera mostradas son alternativas: elige solamente una. "
            "No deben sumarse entre sí. Si la pieza está quebrada, tiene holguras, "
            "combina materiales diferentes o se usa en exterior, la solución debe "
            "revisarse antes de comprar."
        )
        partes.append(
            "CONDICIÓN DE ESTA PROPUESTA\n"
            "Esta recomendación supone que la unión de madera está suelta o se "
            "despegó, pero la madera no está quebrada. Si hay tornillos flojos, una "
            "pieza rota o un encaje desgastado, indícalo antes de comprar porque la "
            "solución cambia."
        )
        partes.append(
            "PROCEDIMIENTO ORIENTATIVO\n"
            "• Separa la unión sin forzar ni quebrar la madera.\n"
            "• Retira solamente residuos sueltos y deja las superficies limpias y secas.\n"
            "• Aplica el adhesivo según las instrucciones del fabricante.\n"
            "• Mantén la unión inmóvil con el sargento durante el curado indicado.\n"
            "• No uses la mesa hasta completar el tiempo de secado."
        )
    if datos_faltantes:
        if falta_base_piso:
            partes.append(
                "PARA CONTINUAR\n"
                "Indica si la base actual es de hormigón, madera/OSB o cerámica.\n"
                "¿Por qué? Esto define la manta niveladora o barrera de humedad adecuada.\n"
                "Puedes responder: “hormigón”, “madera/OSB”, “cerámica” o “no lo sé”."
            )
        else:
            faltantes_legibles = [
                faltante.strip().lstrip("¿").rstrip("?.")
                for faltante in datos_faltantes
            ]
            partes.append(
                "PARA CONTINUAR\n"
                + "\n".join(f"• {faltante}" for faltante in faltantes_legibles)
            )
    else:
        if cantidades_calculadas:
            partes.append(
                "CANTIDADES QUE PUDE CALCULAR\n"
                + "\n".join(f"• {cantidad}" for cantidad in cantidades_calculadas)
                + "\nEstas cantidades usan las fichas verificadas del catálogo. "
                "Los demás materiales quedan como referencia hasta confirmar medidas y condiciones del lugar."
            )
            detalle_total = (
                f"TOTAL CALCULADO\n{_formatear_clp(total_calculado)} CLP por "
                f"{len(productos_con_cantidad)} "
                f"{'material' if len(productos_con_cantidad) == 1 else 'materiales'} "
                "con cantidad verificada."
            )
            if cantidad_referenciales:
                materiales_referenciales = [
                    producto["nombre"] for producto in productos_materiales
                    if producto.get("recomendacion_orientativa")
                ]
                lista_referenciales = "\n".join(
                    f"• {nombre}" for nombre in materiales_referenciales
                )
                detalle_total += (
                    f"\n\nEste es un total parcial: faltan {cantidad_referenciales} "
                    f"{'material referencial' if cantidad_referenciales == 1 else 'materiales referenciales'} "
                    "por cuantificar, por lo que todavía no "
                    "representa el costo completo del proyecto."
                    f"\n\nMATERIALES PENDIENTES DE CUANTIFICAR\n{lista_referenciales}"
                    "\nNo se sumaron porque sus fichas no definen un rendimiento "
                    "compatible con las medidas del proyecto."
                )
            partes.append(detalle_total)
        else:
            partes.append(
                "SOBRE LAS CANTIDADES\n"
                "Son una estimación inicial y pueden ajustarse al confirmar los detalles "
                "de instalación."
            )
    if faltantes:
        detalles_por_nombre = {
            detalle["nombre"]: detalle for detalle in faltantes_detalle
        }
        lineas_faltantes = []
        for faltante in dict.fromkeys(faltantes):
            detalle = detalles_por_nombre.get(faltante)
            if detalle:
                lineas_faltantes.append(
                    f"• {faltante} — {detalle['uso']}"
                )
            else:
                lineas_faltantes.append(f"• {faltante}")
        partes.append(
            "NO DISPONIBLE EN EL CATÁLOGO\n"
            "Estos elementos también se usan para completar el proyecto, pero no están "
            "disponibles actualmente en SFI:\n"
            + "\n".join(lineas_faltantes)
        )
    if sin_stock_detalle:
        partes.append(
            "ENCONTRADO SIN STOCK\n"
            + "\n".join(
                f"• {item['nombre']} — {item['uso']}"
                for item in sin_stock_detalle
            )
        )
    if es_porton_automatico:
        partes.append(
            "IMPORTANTE\n"
            "La hoja, el riel y las ruedas deben dimensionarse según el ancho, peso y recorrido "
            "real del portón. La alimentación, las protecciones y la puesta en servicio deben "
            "ser revisadas por un instalador eléctrico autorizado."
        )
    if es_iluminacion_exterior_con_sensor:
        partes.append(
            "CONEXIÓN ELÉCTRICA\n"
            "La luminaria, el sensor y la canalización son una guía de materiales. "
            "La conexión al circuito existente y la selección de sus protecciones deben "
            "ser verificadas por un electricista autorizado."
        )
    if maestros:
        partes.append(f"También encontré {len(maestros)} maestro(s) aprobado(s) en {comuna}.")

    partes.append(
        "IMPORTANTE\n"
        "Esta propuesta es solo una estimación orientativa basada en los productos y "
        "antecedentes disponibles. Las cantidades, compatibilidad y condiciones de "
        "instalación deben verificarse en terreno. Antes de comprar o ejecutar el "
        "trabajo, consulta con un profesional calificado."
    )

    sugerencias = []
    if falta_base_piso:
        sugerencias.extend([
            "La base es de hormigón",
            "La base es de madera u OSB",
            "La base es de cerámica",
        ])
    elif datos_faltantes:
        sugerencias.append("Completar medidas del proyecto")
    if not datos_faltantes:
        sugerencias.extend([
            "¿Por qué elegiste estos materiales?",
            "Ajustar medidas o materiales del proyecto",
            "¿Qué herramientas necesito para este proyecto?",
            "¿Algún maestro puede ayudarme con este proyecto?",
        ])
    else:
        sugerencias.append("Ajustar el proyecto")

    return {
        "tipo": "plan_proyecto_generico",
        "modo_orientacion": (
            "propuesta_estandar" if modo_estandar else "propuesta_directa"
        ),
        "mensaje": "\n\n".join(partes),
        "productos": productos,
        "maestros": maestros,
        "tareas": tareas,
        "especialidades": especialidades,
        "faltantes_catalogo": list(dict.fromkeys(faltantes)),
        "faltantes_catalogo_detalle": faltantes_detalle,
        "sin_stock_catalogo": sin_stock_detalle,
        "total_calculado": int(total_calculado),
        "total_es_parcial": bool(cantidad_referenciales),
        "calculo_orientativo": True,
        "sugerencias": sugerencias[:4],
    }


def _familia_cubierta_estandar(texto):
    """Clasifica solo las familias de cubierta soportadas por SFI."""
    contexto = _normalizar(texto)
    if "policarbonato" in contexto:
        return "policarbonato"
    if any(termino in contexto for termino in ("zinc", "galvanizada", "metalica")):
        return "zinc"
    if "teja asfaltica" in contexto or "tejas asfalticas" in contexto:
        return "teja_asfaltica"
    if re.search(r"\b(?:arcilla|arciilla|terracota|colonial)\b", contexto):
        return "teja_arcilla"
    return ""


def _tareas_techumbre_estandar(familia):
    """Plantillas aisladas para no delegar una techumbre estandar a Gemini."""
    drenaje = {
        "nombre": "Evacuacion de aguas lluvia",
        "busquedas": [
            "canaleta galvanizada aguas lluvia 125 mm",
            "bajada aguas lluvia PVC 75 mm",
        ],
        "usos_materiales": [
            {
                "busqueda": "canaleta galvanizada aguas lluvia 125 mm",
                "uso": "Recoger el agua que escurre desde el borde de la cubierta.",
            },
            {
                "busqueda": "bajada aguas lluvia PVC 75 mm",
                "uso": "Conducir el agua desde la canaleta hasta una descarga adecuada.",
            },
        ],
        "bases_calculo": ["referencial", "referencial"],
    }
    if familia == "teja_arcilla":
        return [
            {
                "nombre": "Cubierta de teja de arcilla",
                "busquedas": ["teja colonial de arcilla"],
                "usos_materiales": [{
                    "busqueda": "teja colonial de arcilla",
                    "uso": "Cubrir la techumbre con tejas compatibles con la base y pendiente definidas para el proyecto.",
                }],
                "bases_calculo": ["referencial"],
            },
            drenaje,
        ]
    if familia == "policarbonato":
        return [
            {
                "nombre": "Cubierta de policarbonato",
                "busquedas": ["policarbonato alveolar 6 mm 1,05 x 2,90 m"],
                "usos_materiales": [{
                    "busqueda": "policarbonato alveolar 6 mm 1,05 x 2,90 m",
                    "uso": "Formar la cubierta con los alveolos orientados en el sentido de la pendiente.",
                }],
                "bases_calculo": ["superficie_cubierta"],
            },
            {
                "nombre": "Fijacion compatible",
                "busquedas": ["tornillo para policarbonato con golilla pack 100"],
                "usos_materiales": [{
                    "busqueda": "tornillo para policarbonato con golilla pack 100",
                    "uso": "Fijar la plancha sin reemplazar la golilla compatible por una fijacion generica.",
                }],
                "bases_calculo": ["referencial"],
            },
            {
                "nombre": "Perfiles de union y cierre",
                "busquedas": [
                    "perfil H union policarbonato alveolar 6 mm",
                    "perfil U cierre policarbonato alveolar 6 mm",
                ],
                "usos_materiales": [
                    {
                        "busqueda": "perfil H union policarbonato alveolar 6 mm",
                        "uso": "Unir planchas contiguas respetando la dilatacion del sistema.",
                    },
                    {
                        "busqueda": "perfil U cierre policarbonato alveolar 6 mm",
                        "uso": "Proteger y terminar los bordes expuestos de las planchas.",
                    },
                ],
                "bases_calculo": ["referencial", "referencial"],
            },
            {
                "nombre": "Cierre de alveolos",
                "busquedas": [
                    "cinta de aluminio DVP 25 mm gris 10 m",
                    "cinta Filter Tape DVP 25 mm gris 11 m",
                ],
                "usos_materiales": [
                    {
                        "busqueda": "cinta de aluminio DVP 25 mm gris 10 m",
                        "uso": "Cerrar el extremo superior de los alveolos contra agua y suciedad.",
                    },
                    {
                        "busqueda": "cinta Filter Tape DVP 25 mm gris 11 m",
                        "uso": "Proteger el extremo inferior permitiendo evacuar la condensacion.",
                    },
                ],
                "bases_calculo": ["referencial", "referencial"],
            },
            {
                "nombre": "Sellado complementario",
                "busquedas": ["sellador neutro compatible con policarbonato"],
                "usos_materiales": [{
                    "busqueda": "sellador neutro compatible con policarbonato",
                    "uso": "Complementar encuentros puntuales; no reemplaza perfiles, cintas ni holguras de dilatacion.",
                }],
                "bases_calculo": ["referencial"],
            },
            drenaje,
        ]
    if familia == "zinc":
        return [
            {
                "nombre": "Cubierta de zinc",
                "busquedas": ["plancha zinc acanalado 0,35 mm x 3 m"],
                "usos_materiales": [{
                    "busqueda": "plancha zinc acanalado 0,35 mm x 3 m",
                    "uso": "Formar la cubierta metalica respetando traslapos y pendiente de instalacion.",
                }],
                "bases_calculo": ["superficie_cubierta"],
            },
            {
                "nombre": "Fijacion de la cubierta",
                "busquedas": ["tornillo techo autoperforante 12 x 2 pulgadas pack 100"],
                "usos_materiales": [{
                    "busqueda": "tornillo techo autoperforante 12 x 2 pulgadas pack 100",
                    "uso": "Fijar la plancha a una estructura compatible con sello para intemperie.",
                }],
                "bases_calculo": ["referencial"],
            },
            {
                "nombre": "Traslapos y remates",
                "busquedas": ["cinta butilica impermeable", "cumbrera galvanizada"],
                "usos_materiales": [
                    {
                        "busqueda": "cinta butilica impermeable",
                        "uso": "Sellar traslapos y encuentros indicados por el sistema de cubierta.",
                    },
                    {
                        "busqueda": "cumbrera galvanizada",
                        "uso": "Cerrar el encuentro superior de una techumbre a dos aguas.",
                    },
                ],
                "bases_calculo": ["referencial", "referencial"],
            },
            drenaje,
        ]
    if familia == "teja_asfaltica":
        return [
            {
                # El nombre exacto "Cubierta" activa el filtro que excluye
                # clavos, perfiles y sellos de la seleccion principal.
                "nombre": "Cubierta",
                "busquedas": ["teja asfaltica"],
                "usos_materiales": [{
                    "busqueda": "teja asfaltica",
                    "uso": "Formar la terminacion impermeable sobre una base continua compatible.",
                }],
                "bases_calculo": ["superficie_cubierta"],
            },
            {
                "nombre": "Base impermeable",
                "busquedas": ["membrana impermeable para techumbre"],
                "usos_materiales": [{
                    "busqueda": "membrana impermeable para techumbre",
                    "uso": "Proteger la base continua antes de instalar las tejas.",
                }],
                "bases_calculo": ["superficie_cubierta"],
            },
            {
                "nombre": "Fijacion especifica",
                "busquedas": ["clavo terrano para teja asfaltica 1 pulgada"],
                "usos_materiales": [{
                    "busqueda": "clavo terrano para teja asfaltica 1 pulgada",
                    "uso": "Fijar las tejas en la posicion y cantidad indicadas por su fabricante.",
                }],
                "bases_calculo": ["referencial"],
            },
            drenaje,
        ]
    return []


def resolver_proyecto_techumbre(
    datos,
    *,
    buscar_productos,
    producto_publico,
    buscar_maestros,
    resolver_especialidad,
):
    """Valida una techumbre antes de recomendar materiales del catálogo."""
    proyecto = _texto_seguro(datos.get("proyecto"), 120) or "Proyecto de techumbre"
    try:
        ancho_cm = max(0, int(datos.get("ancho_cm") or 0))
        largo_cm = max(0, int(datos.get("fondo_cm") or 0))
        alto_cm = max(0, int(datos.get("alto_cm") or 0))
    except (TypeError, ValueError):
        ancho_cm = largo_cm = alto_cm = 0
    modo_estandar = datos.get("_proyecto_estandar") is True
    material = _normalizar(datos.get("material_estructura"))
    estado = _normalizar(datos.get("estado_estructura"))
    cubierta = _texto_seguro(datos.get("tipo_cubierta"), 100)
    texto = _normalizar(" ".join([proyecto, cubierta]))
    cubierta_recomendada = None

    cubierta_generica = "policarbonato" in texto and not re.search(
        r"\b(?:alveolar|ondulad[oa]|compact[oa]|\d+(?:[.,]\d+)?\s*mm)\b", texto
    )
    if cubierta_generica and (datos.get("_autoriza_recomendacion_cubierta") or modo_estandar):
        candidatas = [
            producto for producto in buscar_productos("policarbonato")
            if producto.stock > 0
            and producto.informacion_tecnica_verificada
            and producto.tipo_calculo == "superficie"
            and producto.rendimiento
            and producto.unidad_rendimiento == "m2_unidad"
        ]
        cubierta_recomendada = next(
            (
                producto for producto in candidatas
                if "alveolar" in _normalizar(producto.nombre)
                and re.search(r"\b6\s*mm\b", _normalizar(producto.nombre))
            ),
            candidatas[0] if candidatas else None,
        )
        if cubierta_recomendada:
            cubierta = cubierta_recomendada.nombre
            texto = _normalizar(" ".join([proyecto, cubierta]))

    # Los datos críticos se reconstruyen para no arrastrar faltantes obsoletos
    # que Gemini pudiera haber conservado después de una respuesta del usuario.
    faltantes = []
    claves_faltantes = set()

    def agregar_faltante(texto_faltante):
        clave = _normalizar(texto_faltante)
        if clave not in claves_faltantes and len(faltantes) < 3:
            faltantes.append(texto_faltante)
            claves_faltantes.add(clave)

    familia_estandar = _familia_cubierta_estandar(texto) if modo_estandar else ""
    if modo_estandar and not familia_estandar and re.search(r"\btejas?\b", texto):
        return {
            "tipo": "aclaracion_proyecto",
            "mensaje": (
                "PROYECTO\nTechumbre estándar de tejas\n\n"
                "¿Qué tipo de teja prefieres: asfáltica, de arcilla u otra? "
                "Las fijaciones y la base varían según el tipo. Si no lo sabes, "
                "indícalo y te orientaré con las opciones disponibles."
            ),
            "productos": [],
            "maestros": [],
            "sugerencias": ["Teja asfáltica", "Teja de arcilla", "No lo sé"],
        }
    if modo_estandar and not familia_estandar:
        return {
            "tipo": "aclaracion_proyecto",
            "mensaje": (
                "PROYECTO\nTechumbre estandar por material\n\n"
                "ANTES DE RECOMENDAR PRODUCTOS\n"
                "Indica el material principal de la cubierta: policarbonato, zinc "
                "o teja asfaltica. Cada sistema utiliza fijaciones, uniones y "
                "sellos diferentes, por lo que no elegire uno sin tu confirmacion."
            ),
            "productos": [],
            "maestros": [],
            "sugerencias": [
                "Quiero una techumbre estandar de policarbonato",
                "Quiero una techumbre estandar de zinc",
                "Quiero una techumbre estandar de teja asfaltica",
            ],
        }

    if not modo_estandar and (not ancho_cm or not largo_cm):
        agregar_faltante("largo y ancho del área a cubrir")
    material_faltante = material not in {"madera", "metal", "hormigon", "otra"}
    estado_faltante = estado not in {"nueva", "reutilizable", "reparar", "reemplazar"}
    if not modo_estandar and material_faltante and estado_faltante:
        agregar_faltante("material y estado de la estructura de apoyo")
    elif not modo_estandar and material_faltante:
        agregar_faltante("material de la estructura de apoyo")
    elif not modo_estandar and estado_faltante:
        agregar_faltante("estado de la estructura de apoyo")
    elif not modo_estandar and estado == "nueva" and not alto_cm:
        agregar_faltante("altura de la estructura nueva")
    if not cubierta:
        agregar_faltante("material, formato y espesor de la cubierta")
    elif "policarbonato" in texto and not re.search(
        r"\b(?:alveolar|ondulad[oa]|compact[oa]|\d+\s*mm)\b", texto
    ):
        agregar_faltante("formato y espesor del policarbonato")

    if faltantes:
        faltantes_legibles = [
            faltante.strip().lstrip("¿").rstrip("?.")
            for faltante in faltantes
        ]
        return {
            "tipo": "aclaracion_proyecto",
            "mensaje": "\n".join([
                "PROYECTO",
                proyecto,
                "",
                "ANTES DE RECOMENDAR PRODUCTOS",
                "Necesito todos estos datos para preparar una recomendación segura:",
                *_preguntas_guiadas(faltantes_legibles, proyecto),
                "",
                "REVISA TAMBIÉN",
                "Confirma que la pendiente y el drenaje existentes sean adecuados.",
                "",
                "RESPONDE TODO EN UN MENSAJE",
                "Si desconoces algo, escribe “no lo sé” y te ayudaré a identificarlo.",
            ]),
            "productos": [],
            "maestros": [],
            "sugerencias": _sugerencias_respuesta(proyecto, faltantes_legibles),
        }

    consulta_cubierta = (
        cubierta_recomendada.nombre
        if cubierta_recomendada
        else cubierta
        if "policarbonato" in texto
        else "plancha zinc acanalado"
        if "zinc" in texto
        else "teja asfaltica"
        if "teja asfaltica" in texto
        else "teja"
        if "teja" in texto
        else cubierta
    )
    consulta_fijacion = {
        "madera": "tornillo para techo de madera",
        "metal": "tornillo autoperforante metal",
        "hormigon": "fijacion para hormigon",
        "otra": "fijacion para techumbre",
    }.get(material, "fijacion para techumbre")
    datos_plan = dict(datos)
    if modo_estandar:
        datos_plan["tareas_proyecto"] = _tareas_techumbre_estandar(familia_estandar)
        datos_plan["material_principal_proyecto"] = ""
        especialidades = ["Techumbre"]
        if material == "madera":
            especialidades.append("Carpinteria")
        elif material == "metal":
            especialidades.append("Soldadura")
        elif material == "hormigon":
            especialidades.append("Albanileria")
        datos_plan["especialidades_proyecto"] = especialidades
        datos_plan["datos_faltantes_proyecto"] = []
        datos_plan["herramientas_proyecto"] = []
        datos_plan["incluir_herramientas"] = False
        resultado = resolver_proyecto_generico(
            datos_plan,
            buscar_productos=buscar_productos,
            producto_publico=producto_publico,
            buscar_maestros=buscar_maestros,
            resolver_especialidad=resolver_especialidad,
        )
        if not ancho_cm or not largo_cm:
            supuesto = (
                "SUPUESTOS DE LA TECHUMBRE ESTANDAR\n"
                "La propuesta define un sistema compatible por material, pero no "
                "inventa cantidades sin ancho y largo. La estructura, pendiente, "
                "apoyos y drenaje deben verificarse en terreno antes de comprar."
            )
            bloques = resultado.get("mensaje", "").split("\n\n")
            bloques.insert(1, supuesto)
            resultado["mensaje"] = "\n\n".join(bloques)
        return resultado

    tareas_techumbre = []
    if estado == "nueva":
        consulta_estructura = {
            "madera": "pino dimensionado 2 x 4 pulgadas",
            "metal": "perfil metalico estructural exterior",
            "hormigon": "material estructural hormigon",
            "otra": "material estructura exterior",
        }[material]
        tareas_techumbre.append({
            "nombre": "Estructura",
            "busquedas": [consulta_estructura],
        })
    consulta_sellado = (
        "sellador neutro compatible con policarbonato"
        if "policarbonato" in texto
        else "cinta butilica impermeable"
        if "zinc" in texto
        else "membrana impermeable para techumbre"
        if "teja" in texto
        else "sellador para techumbre exterior"
    )
    tareas_techumbre.extend([
        {
            "nombre": "Cubierta",
            "busquedas": [consulta_cubierta],
            "usos_materiales": [{
                "busqueda": consulta_cubierta,
                "uso": "Cubrir el área superior y proteger el espacio de la lluvia.",
            }],
            "bases_calculo": ["superficie_cubierta"],
        },
        {
            "nombre": "Fijación compatible",
            "busquedas": [consulta_fijacion],
            "usos_materiales": [{
                "busqueda": consulta_fijacion,
                "uso": "Fijar la cubierta a la estructura de apoyo indicada.",
            }],
            "bases_calculo": ["referencial"],
        },
        {
            "nombre": "Sellado",
            "busquedas": [consulta_sellado],
            "usos_materiales": [{
                "busqueda": consulta_sellado,
                "uso": "Sellar uniones y puntos de fijación expuestos al agua.",
            }],
            "bases_calculo": ["referencial"],
        },
    ])
    if "zinc" in texto:
        tareas_techumbre.append({
            "nombre": "Remates",
            "busquedas": ["cumbrera galvanizada"],
            "usos_materiales": [{
                "busqueda": "cumbrera galvanizada",
                "uso": "Cerrar y proteger el encuentro superior de las aguas del techo.",
            }],
            "bases_calculo": ["referencial"],
        })
    elif "policarbonato" in texto:
        tareas_techumbre.append({
            "nombre": "Perfiles de unión y cierre",
            "busquedas": [
                "perfil H union policarbonato alveolar 6 mm",
                "perfil U cierre policarbonato alveolar 6 mm",
            ],
            "usos_materiales": [
                {
                    "busqueda": "perfil H union policarbonato alveolar 6 mm",
                    "uso": "Unir dos planchas contiguas de policarbonato.",
                },
                {
                    "busqueda": "perfil U cierre policarbonato alveolar 6 mm",
                    "uso": "Cerrar los bordes expuestos de las planchas.",
                },
            ],
            "bases_calculo": ["referencial", "referencial"],
        })
    datos_plan["tareas_proyecto"] = tareas_techumbre
    # En techumbres la cubierta ya tiene una etapa propia. Evita que una
    # interpretación redundante de Gemini la inserte antes como "Material
    # principal" y deje a la etapa Cubierta sin el producto calculable.
    datos_plan["material_principal_proyecto"] = ""
    datos_plan["especialidades_proyecto"] = ["Techumbre"]
    datos_plan["datos_faltantes_proyecto"] = []
    resultado = resolver_proyecto_generico(
        datos_plan,
        buscar_productos=buscar_productos,
        producto_publico=producto_publico,
        buscar_maestros=buscar_maestros,
        resolver_especialidad=resolver_especialidad,
    )
    if datos.get("_consulta_solo_herramientas"):
        herramientas = [
            producto for producto in resultado.get("productos", [])
            if any(clase in _normalizar(producto.get("categoria")) for clase in (
                "herramienta", "seguridad",
            ))
        ]
        for herramienta in herramientas:
            herramienta["rol"] = "Herramienta recomendada"
            herramienta["es_opcional"] = True
            herramienta["carrito_cantidad"] = 1
        total_herramientas = sum(
            (herramienta.get("precio") or 0 for herramienta in herramientas),
            0,
        )
        herramientas_sugeridas = _lista_textos(
            datos.get("herramientas_proyecto"), 3, 100,
        )
        resultado.update({
            "productos": herramientas,
            "mensaje": (
                "HERRAMIENTAS PARA TU TECHUMBRE\n"
                + (
                    "\n".join(
                        f"• {herramienta['nombre']}: "
                        f"{herramienta.get('uso_en_proyecto') or 'apoyo para la instalación.'}"
                        for herramienta in herramientas
                    )
                    if herramientas
                    else (
                        "ORIENTACIÓN RECOMENDADA\n"
                        + "\n".join(
                            f"• {herramienta}: se usa para realizar esta tarea."
                            for herramienta in herramientas_sugeridas
                        )
                        + "\n\nNo encontré estas herramientas con stock en SFI."
                        if herramientas_sugeridas
                        else "No encontré herramientas suficientemente relacionadas con stock."
                    )
                )
                + (
                    f"\n\nCOSTO OPCIONAL DE HERRAMIENTAS\n"
                    f"{_formatear_clp(total_herramientas)} CLP considerando una unidad de cada una."
                    if herramientas else ""
                )
                + "\n\nLas herramientas son opcionales y no se suman al total de materiales. "
                  "Para trabajar en altura utiliza protección contra caídas y evaluación profesional."
            ),
            "total_calculado": 0,
            "total_herramientas_opcionales": total_herramientas,
            "faltantes_catalogo": [],
            "sugerencias": ["Volver al resumen del proyecto", "Agregar herramientas al carrito"],
        })
        return resultado
    superficie = round((ancho_cm * largo_cm) / 10000, 2)
    for item in resultado.get("productos", []):
        if _normalizar(item.get("rol")) != "cubierta":
            continue
        producto = Producto.objects.filter(pk=item.get("id"), activo=True).first()
        if not (
            producto
            and producto.informacion_tecnica_verificada
            and producto.tipo_calculo == "superficie"
            and producto.rendimiento
            and producto.unidad_rendimiento == "m2_unidad"
        ):
            continue
        cobertura = Decimal(producto.rendimiento)
        margen = Decimal(producto.porcentaje_desperdicio or 0) / Decimal("100")
        superficie_calculo = Decimal(str(superficie)) * (Decimal("1") + margen)
        cantidad = int(
            (superficie_calculo / cobertura).to_integral_value(rounding=ROUND_CEILING)
        )
        if cantidad < 1:
            continue
        item.update({
            "cantidad_requerida": cantidad,
            "carrito_cantidad": min(cantidad, producto.stock),
            "subtotal": cantidad * producto.precio,
            "recomendacion_orientativa": False,
            "detalle_material": (
                f"{cantidad} unidad(es) para {superficie:g} m², incluyendo "
                f"{producto.porcentaje_desperdicio:g}% de margen; "
                f"cada unidad cubre {producto.rendimiento:g} m²."
            ),
        })
        if cantidad > producto.stock:
            resultado.setdefault("faltantes_catalogo", []).append(
                f"{producto.nombre}: se requieren {cantidad} y hay {producto.stock} en stock"
            )

    resultado["superficie_m2"] = superficie
    datos_considerados = (
        "DATOS CONSIDERADOS\n"
        f"El área informada es de {superficie:g} m²."
    )
    if cubierta_recomendada:
        datos_considerados += (
            " "
            f"Como pediste una recomendación, seleccioné {cubierta_recomendada.nombre} "
            "por ser una cubierta disponible con ficha técnica verificada."
        )
    bloques_mensaje = resultado["mensaje"].split("\n\n")
    bloques_mensaje.insert(1, datos_considerados)
    resultado["mensaje"] = "\n\n".join(bloques_mensaje)
    productos_con_cantidad = [
        producto for producto in resultado.get("productos", [])
        if not producto.get("recomendacion_orientativa")
        and producto.get("cantidad_requerida")
        and producto.get("subtotal") is not None
    ]
    total_calculado = sum(
        (producto["subtotal"] for producto in productos_con_cantidad),
        Decimal("0"),
    )
    resultado["total_calculado"] = total_calculado
    if productos_con_cantidad:
        productos_materiales = [
            producto for producto in resultado.get("productos", [])
            if "herramienta" not in _normalizar(producto.get("rol"))
        ]
        cantidad_referenciales = (
            len(productos_materiales) - len(productos_con_cantidad)
        )
        resumen_total = (
            f"\n\nTOTAL CALCULADO\n{_formatear_clp(total_calculado)} CLP por "
            f"{len(productos_con_cantidad)} "
            f"{'material' if len(productos_con_cantidad) == 1 else 'materiales'} "
            "con cantidad verificada."
        )
        if cantidad_referenciales:
            materiales_referenciales = [
                producto["nombre"] for producto in productos_materiales
                if producto.get("recomendacion_orientativa")
            ]
            lista_referenciales = "\n".join(
                f"• {nombre}" for nombre in materiales_referenciales
            )
            resumen_total += (
                f"\n\nEs un total parcial: faltan {cantidad_referenciales} "
                f"{'material referencial' if cantidad_referenciales == 1 else 'materiales referenciales'} "
                "por cuantificar."
                f"\n\nMATERIALES PENDIENTES DE CUANTIFICAR\n{lista_referenciales}"
                "\nNo se sumaron porque sus fichas no definen un rendimiento "
                "compatible con las medidas del proyecto."
            )
        if "TOTAL CALCULADO" not in resultado["mensaje"]:
            resultado["mensaje"] += resumen_total
    return resultado
