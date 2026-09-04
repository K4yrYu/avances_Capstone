import re
import unicodedata

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

    herramientas = _lista_textos(datos.get("herramientas_proyecto"), 3, 80)
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

    productos = []
    productos_usados = set()
    faltantes = []
    texto_plan = [proyecto]

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
