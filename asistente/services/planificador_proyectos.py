import re
import unicodedata
from decimal import Decimal, ROUND_CEILING

from maestros.models import Especialidad
from productos.models import Producto


MAX_TAREAS = 6
MAX_BUSQUEDAS = 8
MAX_PRODUCTOS = 6
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
        cupo = MAX_BUSQUEDAS - total_busquedas
        busquedas = busquedas[:cupo]
        if nombre and busquedas:
            tareas.append({"nombre": nombre, "busquedas": busquedas})
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

    material_principal = _texto_seguro(
        datos.get("material_principal_proyecto"), 100
    )
    if material_principal:
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
            return {
                "tipo": "proyecto_no_valido",
                "mensaje": (
                    f"Proyecto no válido por falta de materiales: no encontré "
                    f"“{material_principal}” con stock en SFI. No mostraré postes, "
                    "fijaciones ni herramientas porque, sin el material principal, "
                    "el proyecto no puede completarse como fue solicitado."
                ),
                "productos": [],
                "maestros": [],
                "faltantes_catalogo": [material_principal],
                "sugerencias": [
                    "Cambiar el material principal",
                    "Ver productos disponibles",
                    "Reformular el proyecto",
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
            item.update({
                "rol": tarea["nombre"],
                "detalle_material": f"Referencia encontrada para: {consulta}.",
                "carrito_cantidad": 1,
                "recomendacion_orientativa": True,
            })
            if (
                superficie_m2 > 0
                and producto.informacion_tecnica_verificada
                and producto.tipo_calculo == "superficie"
                and producto.rendimiento
                and producto.unidad_rendimiento == "m2_unidad"
            ):
                margen = Decimal(producto.porcentaje_desperdicio or 0) / Decimal("100")
                cantidad = int((
                    superficie_m2 * (Decimal("1") + margen)
                    / Decimal(producto.rendimiento)
                ).to_integral_value(rounding=ROUND_CEILING))
                if cantidad > 0:
                    item.update({
                        "cantidad_requerida": cantidad,
                        "carrito_cantidad": min(cantidad, producto.stock),
                        "subtotal": cantidad * producto.precio,
                        "recomendacion_orientativa": False,
                        "detalle_material": (
                            f"{cantidad} unidad(es) para {superficie_m2:g} m² con "
                            f"{producto.porcentaje_desperdicio:g}% de margen."
                        ),
                    })
                    cantidades_calculadas.append(
                        f"{cantidad} unidad(es) de {producto.nombre}"
                    )
                    if cantidad > producto.stock:
                        faltantes.append(
                            f"{producto.nombre}: se requieren {cantidad} y hay "
                            f"{producto.stock} en stock"
                        )
            productos.append(item)
            productos_usados.add(producto.pk)
            if len(productos) >= MAX_PRODUCTOS:
                break
        if len(productos) >= MAX_PRODUCTOS:
            break

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

    datos_faltantes = _lista_textos(datos.get("datos_faltantes_proyecto"), 5, 100)
    partes = [
        f"Analicé “{proyecto}” en {len(tareas)} etapa(s).",
        (
            f"Encontré {len(productos)} producto(s) reales con stock en SFI."
            if productos
            else "No encontré productos con stock suficientemente relacionados."
        ),
    ]
    if datos_faltantes:
        partes.append(
            "Para calcular cantidades exactas todavía necesito: "
            + ", ".join(datos_faltantes)
            + "."
        )
    else:
        if cantidades_calculadas:
            partes.append(
                "Cantidades calculadas con fichas verificadas: "
                + ", ".join(cantidades_calculadas)
                + ". Los demás materiales permanecen como referencia."
            )
        else:
            partes.append(
                "Las cantidades mostradas son referenciales hasta validar medidas y rendimiento."
            )
    if faltantes:
        partes.append("No encontré en el catálogo: " + ", ".join(faltantes) + ".")
    if maestros:
        partes.append(f"También encontré {len(maestros)} maestro(s) aprobado(s) en {comuna}.")

    sugerencias = []
    if datos_faltantes:
        sugerencias.append("Completar medidas del proyecto")
    if especialidades and not comuna:
        sugerencias.append(f"Buscar maestro de {especialidades[0]}")
    sugerencias.extend(["Ver alternativas de productos", "Ajustar el proyecto"])

    return {
        "tipo": "plan_proyecto_generico",
        "mensaje": " ".join(partes),
        "productos": productos,
        "maestros": maestros,
        "tareas": tareas,
        "especialidades": especialidades,
        "faltantes_catalogo": faltantes,
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

    # Los datos críticos se reconstruyen para no arrastrar faltantes obsoletos
    # que Gemini pudiera haber conservado después de una respuesta del usuario.
    faltantes = []
    claves_faltantes = set()

    def agregar_faltante(texto_faltante):
        clave = _normalizar(texto_faltante)
        if clave not in claves_faltantes and len(faltantes) < 5:
            faltantes.append(texto_faltante)
            claves_faltantes.add(clave)

    if not ancho_cm or not largo_cm:
        agregar_faltante("largo y ancho del área a cubrir")
    if material not in {"madera", "metal", "hormigon", "otra"}:
        agregar_faltante("material de la estructura de apoyo")
    if estado not in {"nueva", "reutilizable", "reparar", "reemplazar"}:
        agregar_faltante("estado de la estructura existente")
    if estado == "nueva" and not alto_cm:
        agregar_faltante("altura de la estructura nueva")
    if not cubierta:
        agregar_faltante("material, formato y espesor de la cubierta")
    elif "policarbonato" in texto and not re.search(
        r"\b(?:alveolar|ondulad[oa]|compact[oa]|\d+\s*mm)\b", texto
    ):
        agregar_faltante("formato y espesor del policarbonato")

    if faltantes:
        return {
            "tipo": "aclaracion_proyecto",
            "mensaje": (
                f"Para preparar {proyecto} con materiales compatibles del catálogo necesito: "
                + ", ".join(faltantes)
                + ". También confirma que la pendiente y el drenaje existentes son adecuados. "
                "Con esos datos revisaré solo productos con stock y no asumiré fijaciones."
            ),
            "productos": [],
            "maestros": [],
            "sugerencias": [
                "Indicar medidas del techo",
                "Indicar estructura y cubierta",
                "Buscar maestro de Techumbre",
            ],
        }

    consulta_cubierta = "policarbonato" if "policarbonato" in texto else cubierta
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
    tareas_techumbre.extend([
        {"nombre": "Cubierta", "busquedas": [consulta_cubierta]},
        {"nombre": "Fijación compatible", "busquedas": [consulta_fijacion]},
        {
            "nombre": "Sellado",
            "busquedas": [
                "sellador policarbonato"
                if "policarbonato" in texto
                else f"sellador {cubierta}"
            ],
        },
    ])
    datos_plan["tareas_proyecto"] = tareas_techumbre
    datos_plan["especialidades_proyecto"] = ["Techumbre"]
    datos_plan["datos_faltantes_proyecto"] = []
    resultado = resolver_proyecto_generico(
        datos_plan,
        buscar_productos=buscar_productos,
        producto_publico=producto_publico,
        buscar_maestros=buscar_maestros,
        resolver_especialidad=resolver_especialidad,
    )
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
        + resultado["mensaje"]
        + resumen_cantidad
        + " Las cantidades sin ficha técnica verificada siguen siendo referenciales. "
          "Confirma formato útil y traslapes indicados por el fabricante antes de comprar."
    )
    return resultado
