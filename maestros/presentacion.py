import unicodedata

from django.templatetags.static import static


AVATAR_MAESTRO = "maestros/img/maestro_default.svg"
PROYECTO_DEFAULT = "maestros/demo/proyecto_default.svg"


def _normalizar(texto):
    texto = unicodedata.normalize("NFKD", (texto or "").casefold())
    return "".join(caracter for caracter in texto if not unicodedata.combining(caracter))


def avatar_maestro_url():
    return static(AVATAR_MAESTRO)


def imagen_proyecto_url(especialidades, titulo=""):
    nombres = {_normalizar(nombre) for nombre in especialidades}
    titulo_normalizado = _normalizar(titulo)

    def tiene(especialidad):
        return any(especialidad in nombre for nombre in nombres)

    if tiene("carpinteria"):
        archivo = (
            "carpinteria-mueble.svg"
            if any(palabra in titulo_normalizado for palabra in ("mueble", "cocina"))
            else "carpinteria-repisa.svg"
        )
    elif tiene("pintura"):
        archivo = (
            "pintura-fachada.svg"
            if any(palabra in titulo_normalizado for palabra in ("fachada", "exterior"))
            else "pintura-interior.svg"
        )
    else:
        archivos = {
            "gasfiteria": "gasfiteria.svg",
            "electricidad": "electricidad.svg",
            "ceramica y revestimientos": "ceramica.svg",
            "albanileria": "albanileria.svg",
            "yeseria y tabiqueria": "tabiqueria.svg",
            "jardineria": "jardineria.svg",
            "techumbre": "techumbre.svg",
        }
        archivo = next(
            (
                archivo_especialidad
                for especialidad, archivo_especialidad in archivos.items()
                if tiene(especialidad)
            ),
            None,
        )

    return static(f"maestros/demo/{archivo}") if archivo else static(PROYECTO_DEFAULT)
