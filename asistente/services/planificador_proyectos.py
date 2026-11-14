import re
import unicodedata
from decimal import Decimal, ROUND_CEILING

from maestros.models import Especialidad
from productos.models import Producto


MAX_TAREAS = 8
MAX_BUSQUEDAS = 18
MAX_ESPECIALIDADES = 3
MAX_MAESTROS = 5


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
    return [
        palabra for palabra in re.findall(r'[a-z0-9-]+', _normalizar(consulta))
        if len(palabra) >= 3 and palabra not in omitidas
    ]


def _textos_producto(producto):
    nombre = _normalizar(producto.nombre)
    identificacion = _normalizar(
        ' '.join([producto.sku or '', producto.marca, producto.categoria])
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
        if "material" in clave and "estado" in clave and "estructura" in clave:
            lineas.extend([
                "• Indica si la estructura es de madera, metal, hormigón u otro material.",
                "• Señala si está firme y reutilizable, necesita reparación o será reemplazada.",
                "• Si será nueva, agrega la altura aproximada en metros.",
                "• Si no sabes evaluarla, descríbela o adjunta una fotografía; no asumiré su capacidad.",
            ])
        elif "vano" in clave or (
            "puerta" in clave
            and any(termino in clave for termino in ("medida", "ancho", "alto"))
        ):
            lineas.extend([
                "• Indica ancho × alto en centímetros; por ejemplo: 80 × 200 cm.",
                "• Mide el vano en la parte superior, central e inferior y usa la medida menor.",
                "• Indica también el espesor del muro o marco si lo conoces.",
                "• Si no puedes medirlo, adjunta una fotografía junto a una cinta métrica.",
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
                "• Si no lo sabes, adjunta una fotografía del marco completo.",
            ])
        elif "estado" in clave:
            lineas.extend([
                "• Bueno: firme, seco, nivelado y sin daños visibles.",
                "• Regular: tiene daños o desniveles menores.",
                "• Malo: presenta humedad, grietas, piezas sueltas o deformación.",
                "• No lo sé: describe los daños visibles o adjunta una fotografía.",
            ])
        elif any(termino in clave for termino in ("medida", "ancho", "largo", "alto", "altura", "superficie", "area")):
            if any(termino in contexto for termino in ("mueble", "repisa", "estante", "gabinete")):
                lineas.extend([
                    "• Indica ancho × alto × fondo en centímetros; por ejemplo: 120 × 80 × 35 cm.",
                    "• Señala si las medidas corresponden al espacio disponible o al mueble terminado.",
                    "• Si hay obstáculos, indica su posición o adjunta una fotografía.",
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
                "• No lo sé: describe color, textura y dureza, o adjunta una fotografía.",
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
                "• No lo sé: describe el resultado que buscas o adjunta una fotografía.",
            ])
    return lineas


def _sugerencias_respuesta(proyecto, faltantes):
    """Entrega ejemplos de respuesta útiles, nunca acciones ajenas al cuestionario."""
    contexto = _normalizar(proyecto)
    claves = " ".join(_normalizar(item) for item in faltantes)

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
            sugerencias.append("No sé evaluar la estructura; adjuntaré una fotografía")
        sugerencias.append("Usa una opción estándar disponible y deja lo estructural como referencia")
        return [item for item in sugerencias if item][:3]

    if any(termino in contexto for termino in ("puerta", "ventana")):
        return [
            "Es interior seco; el vano mide 80 × 200 cm; cambiaré hoja y marco",
            "Es exterior protegida; mide 90 × 200 cm; conservaré el marco",
            "No sé evaluar el marco; adjuntaré una fotografía",
        ]
    if any(termino in contexto for termino in ("mueble", "repisa", "estante", "gabinete")):
        return [
            "El espacio mide 120 × 80 × 35 cm; elige tú el material",
            "Son medidas del mueble terminado y el ambiente es interior seco",
            "No sé identificar el material; adjuntaré una fotografía",
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
            "No sé identificar la base; adjuntaré una fotografía",
        ]

    return [
        "Responderé las medidas y condiciones en un solo mensaje",
        "Elige tú las preferencias no críticas con productos disponibles",
        "No sé identificarlo; adjuntaré una fotografía",
    ]


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
        busquedas = _lista_textos(tarea.get("busquedas"), 3, 80)
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
                'perimetro', 'referencial',
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

    herramientas = (
        _lista_textos(datos.get("herramientas_proyecto"), 3, 80)
        if datos.get("incluir_herramientas") is True
        else []
    )
    herramientas = herramientas[:max(0, MAX_BUSQUEDAS - total_busquedas)]
    if herramientas:
        tareas.append({"nombre": "Herramientas recomendadas", "busquedas": herramientas})
    return tareas[:MAX_TAREAS]


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
        datos.get("datos_faltantes_proyecto"), 3, 100
    )
    modo_estandar = (
        datos.get("_proyecto_estandar") is True
        or datos.get("modo_orientacion") == "propuesta_estandar"
    )
    if datos_faltantes_iniciales and not modo_estandar:
        proyecto_normalizado = _normalizar(proyecto)
        es_piso = any(
            termino in proyecto_normalizado
            for termino in ("piso flotante", "piso laminado")
        )
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
        if es_piso:
            for faltante in faltantes_legibles:
                clave = _normalizar(faltante)
                if "tipo de piso" in clave:
                    lineas.extend([
                        "",
                        "1. TIPO DE PISO",
                        "• Laminado: aspecto cálido para espacios interiores secos.",
                        "• Vinílico SPC: más resistente a humedad y fácil de limpiar.",
                        "• Porcelanato: rígido, durable y apto para zonas húmedas.",
                        "• No lo sé: indica en qué habitación se instalará y yo elegiré.",
                    ])
                elif "base" in clave or "superficie actual" in clave or "contrapiso" in clave:
                    lineas.extend([
                        "",
                        "2. BASE ACTUAL",
                        "• Hormigón: superficie gris, dura y continua.",
                        "• Madera/OSB: tablas o paneles de madera prensada.",
                        "• Cerámica: palmetas existentes con juntas visibles.",
                        "• No lo sé: describe lo que ves o adjunta una fotografía.",
                    ])
                elif "estado" in clave:
                    lineas.extend([
                        "",
                        "3. ESTADO DE LA BASE",
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
            sugerencias = [
                "No sé qué piso elegir; es un dormitorio seco",
                "La base es de hormigón y está en buen estado",
                "No sé identificar la base",
            ]
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

    material_principal = _texto_seguro(
        datos.get("material_principal_proyecto"), 100
    )
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
        candidatos_principales = _candidatos_directos(material_principal)
        ids_principales = {producto.pk for producto in candidatos_principales}
        candidatos_principales.extend(
            producto for producto in buscar_productos(material_principal)
            if producto.pk not in ids_principales
        )
        principal_disponible = next((
            producto for producto in candidatos_principales
            if producto.stock > 0
            and _coincidencia_suficiente(producto, material_principal)
        ), None)
        if principal_disponible is None:
            etapas_orientativas = []
            for tarea in tareas:
                materiales_etapa = ", ".join(tarea.get("busquedas", []))
                if materiales_etapa:
                    etapas_orientativas.append(
                        f"• {tarea['nombre']}: {materiales_etapa}."
                    )
            return {
                "tipo": "plan_proyecto_sin_producto",
                "mensaje": "\n".join([
                    "ORIENTACIÓN PARA TU PROYECTO",
                    f"Puedo ayudarte a planificar “{proyecto}” aunque SFI no tenga todos "
                    "los productos necesarios.",
                    "",
                    "ETAPAS Y ELEMENTOS A CONSIDERAR",
                    *(etapas_orientativas or [
                        "• Revisa preparación, estructura, fijaciones y terminaciones "
                        "según las condiciones reales del lugar."
                    ]),
                    "",
                    "NO DISPONIBLE EN SFI",
                    f"No encontré “{material_principal}” con stock. Por eso no mostraré "
                    "un sustituto como si fuera equivalente ni calcularé su precio.",
                    "",
                    "Puedes continuar consultando etapas, medidas, herramientas, "
                    "profesionales o alternativas compatibles para este mismo proyecto.",
                ]),
                "productos": [],
                "maestros": [],
                "faltantes_catalogo": [material_principal],
                "sugerencias": [
                    "Ver alternativas compatibles disponibles",
                    "¿Qué herramientas necesito?",
                    "¿Qué maestro realiza este trabajo?",
                ],
            }
        if not any(
            _normalizar(material_principal) == _normalizar(busqueda)
            for tarea in tareas for busqueda in tarea["busquedas"]
        ):
            tareas.insert(0, {
                "nombre": "Material principal",
                "busquedas": [material_principal],
            })
            tareas = tareas[:MAX_TAREAS]

    productos = []
    productos_usados = set()
    faltantes = []
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
            candidatos = _candidatos_directos(consulta)
            ids_candidatos = {producto.pk for producto in candidatos}
            candidatos.extend(
                producto for producto in buscar_productos(consulta)
                if producto.pk not in ids_candidatos
            )
            if _normalizar(tarea["nombre"]) == "cubierta":
                accesorios_cubierta = {
                    "perfil", "union", "cierre", "tornillo", "golilla",
                    "sellador", "silicona", "cinta", "canaleta", "bajada",
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
                and _coincidencia_suficiente(candidato, consulta)
                for candidato in candidatos
            ):
                continue
            disponibles = [
                candidato for candidato in candidatos
                if (
                    candidato.pk not in productos_usados
                    and candidato.stock > 0
                    and _coincidencia_suficiente(candidato, consulta)
                )
            ]
            producto = max(
                disponibles,
                key=lambda candidato: _puntaje_directo(candidato, consulta),
                default=None,
            )
            if producto is None:
                faltantes.append(consulta)
                continue
            item = producto_publico(producto)
            uso_material = tarea.get("usos", {}).get(
                _normalizar(consulta),
                _texto_seguro(producto.uso_recomendado, 180)
                or f"Se incluye como apoyo para la etapa «{tarea['nombre']}».",
            )
            item.update({
                "rol": tarea["nombre"],
                "detalle_material": uso_material,
                "uso_en_proyecto": uso_material,
                "carrito_cantidad": 1,
                "recomendacion_orientativa": True,
            })
            base_calculo = tarea.get("bases", {}).get(
                _normalizar(consulta), 'referencial',
            )
            superficie_base = {
                'superficie_piso': superficie_planta or superficie_m2,
                'superficie_cubierta': superficie_planta or superficie_m2,
                'superficie_muros': superficie_muros,
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
            if "herramienta" in _normalizar(producto.get("rol"))
        ]
        for herramienta in herramientas:
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
                    else "No encontré herramientas suficientemente relacionadas con stock."
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
        f"Analicé “{proyecto}” en {len(tareas)} etapa(s).",
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
    if modo_estandar:
        partes = [(
            "PROPUESTA ESTÁNDAR PARA TU PROYECTO\n"
            f"Preparé una alternativa de “{proyecto}” organizada en {len(tareas)} etapas. "
            "Todos los productos mostrados están disponibles actualmente en SFI."
        )]
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
                nombres_referenciales = ", ".join(
                    producto["nombre"] for producto in productos_materiales
                    if producto.get("recomendacion_orientativa")
                )
                detalle_total += (
                    f"\nEste es un total parcial: faltan {cantidad_referenciales} "
                    f"{'material referencial' if cantidad_referenciales == 1 else 'materiales referenciales'} "
                    "por cuantificar, por lo que todavía no "
                    "representa el costo completo del proyecto."
                    f"\nPendientes: {nombres_referenciales}. No se sumaron porque su ficha "
                    "no define un rendimiento compatible con las medidas del proyecto."
                )
            partes.append(detalle_total)
        else:
            partes.append(
                "SOBRE LAS CANTIDADES\n"
                "Son una estimación inicial y pueden ajustarse al confirmar los detalles "
                "de instalación."
            )
    if faltantes:
        partes.append(
            "NO DISPONIBLE EN EL CATÁLOGO\n"
            "No encontré en el catálogo: " + ", ".join(faltantes) + "."
        )
    if maestros:
        partes.append(f"También encontré {len(maestros)} maestro(s) aprobado(s) en {comuna}.")

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
            "Muéstrame alternativas más económicas",
            "¿Qué herramientas necesito para este proyecto?",
        ])
    else:
        sugerencias.append("Ajustar el proyecto")

    return {
        "tipo": "plan_proyecto_generico",
        "modo_orientacion": datos.get("modo_orientacion") or (
            "propuesta_estandar" if modo_estandar else "propuesta_directa"
        ),
        "mensaje": "\n\n".join(partes),
        "productos": productos,
        "maestros": maestros,
        "tareas": tareas,
        "especialidades": especialidades,
        "faltantes_catalogo": faltantes,
        "total_calculado": int(total_calculado),
        "total_es_parcial": bool(cantidad_referenciales),
        "calculo_orientativo": True,
        "sugerencias": sugerencias[:3],
    }


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
    material = _normalizar(datos.get("material_estructura"))
    estado = _normalizar(datos.get("estado_estructura"))
    cubierta = _texto_seguro(datos.get("tipo_cubierta"), 100)
    texto = _normalizar(" ".join([proyecto, cubierta]))
    cubierta_recomendada = None

    cubierta_generica = "policarbonato" in texto and not re.search(
        r"\b(?:alveolar|ondulad[oa]|compact[oa]|\d+(?:[.,]\d+)?\s*mm)\b", texto
    )
    if cubierta_generica and datos.get("_autoriza_recomendacion_cubierta"):
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

    if not ancho_cm or not largo_cm:
        agregar_faltante("largo y ancho del área a cubrir")
    material_faltante = material not in {"madera", "metal", "hormigon", "otra"}
    estado_faltante = estado not in {"nueva", "reutilizable", "reparar", "reemplazar"}
    if material_faltante and estado_faltante:
        agregar_faltante("material y estado de la estructura de apoyo")
    elif material_faltante:
        agregar_faltante("material de la estructura de apoyo")
    elif estado_faltante:
        agregar_faltante("estado de la estructura de apoyo")
    elif estado == "nueva" and not alto_cm:
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
        else "policarbonato"
        if "policarbonato" in texto
        else "plancha zinc acanalado"
        if "zinc" in texto
        else "teja"
        if "teja" in texto
        else cubierta
    )
    consulta_fijacion = {
        "madera": "tornillo para techo de madera",
        "metal": "tornillo autoperforante metal",
        "hormigon": "fijacion para hormigon",
        "otra": "fijacion para techumbre",
    }[material]
    datos_plan = dict(datos)
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
            if "herramienta" in _normalizar(producto.get("rol"))
        ]
        for herramienta in herramientas:
            herramienta["es_opcional"] = True
            herramienta["carrito_cantidad"] = 1
        total_herramientas = sum(
            (herramienta.get("precio") or 0 for herramienta in herramientas),
            0,
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
                    else "No encontré herramientas suficientemente relacionadas con stock."
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
    cantidades_calculadas = []
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
        cantidades_calculadas.append(f"{cantidad} unidad(es) de {producto.nombre}")
        if cantidad > producto.stock:
            resultado.setdefault("faltantes_catalogo", []).append(
                f"{producto.nombre}: se requieren {cantidad} y hay {producto.stock} en stock"
            )

    resultado["superficie_m2"] = superficie
    resumen_cantidad = (
        " Cantidad calculada: " + ", ".join(cantidades_calculadas) + "."
        if cantidades_calculadas else ""
    )
    resultado["mensaje"] = (
        f"El área informada es de {superficie:g} m². "
        + (
            f"Como pediste una recomendación, seleccioné {cubierta_recomendada.nombre} "
            "por ser una cubierta disponible con ficha técnica verificada. "
            if cubierta_recomendada else ""
        )
        + resultado["mensaje"]
        + resumen_cantidad
        + " Antes de instalar, confirma la solución final con un profesional."
    )
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
            nombres_referenciales = ", ".join(
                producto["nombre"] for producto in productos_materiales
                if producto.get("recomendacion_orientativa")
            )
            resumen_total += (
                f"\nEs un total parcial: faltan {cantidad_referenciales} "
                f"{'material referencial' if cantidad_referenciales == 1 else 'materiales referenciales'} "
                "por cuantificar."
                f"\nPendientes: {nombres_referenciales}. No se sumaron porque su ficha "
                "no define un rendimiento compatible con las medidas del proyecto."
            )
        if "TOTAL CALCULADO" not in resultado["mensaje"]:
            resultado["mensaje"] += resumen_total
    return resultado
