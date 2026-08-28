import re
import unicodedata

from django.db.models import Prefetch
from django.urls import reverse

from maestros.models import Especialidad, PerfilMaestro


def _normalizar(valor):
    texto = unicodedata.normalize("NFKD", str(valor or "").casefold())
    sin_tildes = "".join(
        caracter for caracter in texto if not unicodedata.combining(caracter)
    )
    return " ".join(sin_tildes.split())


def _comunas_perfil(perfil):
    valores = [perfil.comuna]
    valores.extend(re.split(r"[,;\n]+", perfil.zonas_trabajo or ""))
    comunas = []
    conocidas = set()
    for valor in valores:
        comuna = " ".join(str(valor or "").split())
        clave = _normalizar(comuna)
        if comuna and clave not in conocidas:
            conocidas.add(clave)
            comunas.append(comuna)
    return comunas


def buscar_maestros(especialidad, comuna=None, limite=5):
    """Devuelve profesionales públicos usando coincidencias completas normalizadas."""
    especialidad_buscada = _normalizar(especialidad)
    comuna_buscada = _normalizar(comuna)
    try:
        limite = max(0, min(int(limite), 5))
    except (TypeError, ValueError):
        limite = 5
    if not especialidad_buscada or limite == 0:
        return []

    especialidades_activas = Especialidad.objects.filter(activa=True).order_by("nombre")
    perfiles = (
        PerfilMaestro.objects.filter(
            estado=PerfilMaestro.Estado.APROBADO,
            disponible=True,
            especialidades__activa=True,
        )
        .select_related("usuario")
        .prefetch_related(Prefetch("especialidades", queryset=especialidades_activas))
        .distinct()
        .order_by("-anos_experiencia", "usuario__first_name", "usuario__last_name", "pk")
    )

    resultados = []
    ids_incluidos = set()
    for perfil in perfiles:
        especialidades = [item.nombre for item in perfil.especialidades.all()]
        if especialidad_buscada not in {_normalizar(item) for item in especialidades}:
            continue
        comunas = _comunas_perfil(perfil)
        if comuna_buscada and comuna_buscada not in {_normalizar(item) for item in comunas}:
            continue
        if perfil.pk in ids_incluidos:
            continue
        ids_incluidos.add(perfil.pk)
        resultados.append({
            "id": perfil.pk,
            "nombre": perfil.usuario.get_full_name() or perfil.usuario.username,
            "foto": perfil.foto_publica_url,
            "especialidades": especialidades,
            "anos_experiencia": perfil.anos_experiencia,
            "comunas": comunas,
            "disponible": True,
            "url": reverse("maestros:detalle", args=[perfil.pk]),
        })
        if len(resultados) >= limite:
            break
    return resultados
