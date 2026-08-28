"""
Sinónimos ferreteros chilenos y expansión semántica de consultas.

Mapea términos coloquiales, técnicos y alternativos a las palabras
que realmente aparecen en los nombres y descripciones del catálogo SFI.
La búsqueda de productos usa este módulo para ampliar la consulta del
usuario antes de buscar, mejorando el recall sin sacrificar precisión.
"""

import re
import unicodedata


def _normalizar(texto):
    texto = unicodedata.normalize('NFKD', str(texto).lower())
    return ''.join(c for c in texto if not unicodedata.combining(c))


# ---------------------------------------------------------------------------
# 1. SINÓNIMOS DIRECTOS
#
# Clave: término que podría escribir el usuario (normalizado, sin tildes).
# Valor: tupla de palabras del catálogo que deben inyectarse en la búsqueda.
#
# Regla: las palabras de expansión deben existir literalmente en al menos un
# nombre, descripción o uso_recomendado de un producto activo.
# ---------------------------------------------------------------------------

SINONIMOS: dict[str, tuple[str, ...]] = {
    # ── Herramientas de medición ──
    'flexometro':       ('cinta', 'metrica'),
    'wincha':           ('cinta', 'metrica'),
    'huincha':          ('cinta', 'metrica'),
    'metro':            ('cinta', 'metrica'),
    'medir':            ('cinta', 'metrica'),

    # ── Taladro y perforación ──
    'atornillador':     ('taladro',),
    'destornillador':   ('taladro',),
    'atornillar':       ('taladro',),
    'perforadora':      ('taladro', 'percutor'),
    'perforar':         ('taladro', 'percutor'),
    'broca':            ('taladro',),
    'rotomartillo':     ('taladro', 'percutor'),
    'drill':            ('taladro',),

    # ── Martillo ──
    'combo':            ('martillo',),
    'mazo':             ('martillo',),
    'maceta':           ('martillo',),
    'clavar':           ('martillo', 'clavo'),

    # ── Sierra / corte ──
    'serrucho':         ('sierra',),
    'cortar':           ('sierra',),
    'trozar':           ('sierra',),
    'disco':            ('sierra', 'circular'),

    # ── Gasfitería / grifería ──
    'grifo':            ('combinacion', 'lavaplatos', 'monomando'),
    'griferia':         ('combinacion', 'lavaplatos', 'monomando'),
    'llave agua':       ('combinacion', 'lavaplatos', 'monomando'),
    'canilla':          ('combinacion', 'lavaplatos', 'monomando'),
    'grifo lavamanos':  ('monomando', 'lavamanos'),
    'llave cocina':     ('combinacion', 'lavaplatos'),
    'llave lavamanos':  ('monomando', 'lavamanos'),

    # ── Fijaciones ──
    'bulón':            ('perno', 'hexagonal'),
    'bulon':            ('perno', 'hexagonal'),
    'perno':            ('perno', 'hexagonal', 'tornillo'),
    'tirafondo':        ('tornillo',),
    'tornillo':         ('tornillo', 'perno'),
    'fijacion':         ('tornillo', 'perno', 'clavo', 'anclaje'),
    'ancla':            ('anclaje', 'fijacion'),

    # ── Pintura ──
    'pintura':          ('pintura', 'latex', 'esmalte'),
    'latex':            ('pintura', 'latex', 'esmalte'),
    'oleo':             ('pintura', 'latex', 'esmalte'),
    'tempera':          ('latex',),
    'tineta':           ('pintura', 'latex'),
    'tarro pintura':    ('pintura', 'latex', 'esmalte'),
    'barnizar':         ('barniz',),
    'lacar':            ('barniz',),
    'vitrificar':       ('barniz',),
    'proteger madera':  ('barniz',),
    'impermeabilizar':  ('membrana', 'impermeable'),
    'impermeabilizante': ('membrana', 'impermeable'),
    'sello humedad':    ('membrana', 'impermeable'),
    'sellante':         ('silicona',),
    'sellar':           ('silicona',),

    # ── Madera ──
    'tabla':            ('pino', 'dimensionado', 'tablero'),
    'tablon':           ('pino', 'dimensionado', 'tablero'),
    'liston':           ('pino', 'dimensionado'),
    'viga':             ('pino', 'dimensionado'),
    'madera':           ('pino', 'dimensionado', 'tablero'),

    # ── Cerámica / revestimientos ──
    'azulejo':          ('ceramica', 'porcelanato'),
    'baldosa':          ('ceramica', 'porcelanato'),
    'palmeta':          ('ceramica', 'porcelanato'),
    'pegar azulejo':    ('adhesivo', 'ceramico'),
    'pegar ceramica':   ('adhesivo', 'ceramico'),
    'pegamento ceramica': ('adhesivo', 'ceramico'),
    'pegamento':        ('adhesivo', 'ceramico'),
    'junta ceramica':   ('frague',),
    'rellenar junta':   ('frague',),
    'fraguar':          ('frague',),
    'juntura':          ('frague',),
    'rejunte':          ('frague',),

    # ── Baño / sanitarios ──
    'inodoro':          ('sanitario',),
    'excusado':         ('sanitario',),
    'wc':               ('sanitario',),
    'taza bano':        ('sanitario',),
    'vanitorio':        ('mueble', 'lavamanos'),
    'regadera':         ('ducha', 'kit'),
    'tina':             ('ducha', 'kit'),
    'ducha telefono':   ('ducha', 'kit'),

    # ── Clavo ──
    'clavo':            ('clavo', 'corriente'),
    'punta':            ('clavo', 'corriente'),
    'puntilla':         ('clavo', 'corriente'),

    # ── Lija ──
    'lijar':            ('lija',),
    'lija':             ('lija',),
    'papel lija':       ('lija',),

    # ── Escuadras ──
    'mensula':          ('escuadra',),
    'soporte':          ('escuadra',),
    'bracket':          ('escuadra',),
}


# ---------------------------------------------------------------------------
# 2. CONCEPTOS RELACIONADOS (intenciones → palabras de catálogo)
#
# Cuando varias palabras juntas forman una intención, se inyectan estas
# palabras adicionales como boost contextual.
# ---------------------------------------------------------------------------

CONCEPTOS_RELACIONADOS: list[tuple[tuple[str, ...], tuple[str, ...]]] = [
    # (palabras clave que deben aparecer juntas, expansiones)
    (('colgar', 'cuadro'),      ('taladro', 'tornillo', 'fijacion')),
    (('colgar', 'repisa'),      ('taladro', 'escuadra', 'tornillo', 'tablero')),
    (('pintar', 'pared'),       ('pintura', 'latex', 'esmalte')),
    (('pintar', 'muro'),        ('pintura', 'latex', 'esmalte')),
    (('pintar', 'pieza'),       ('pintura', 'latex', 'esmalte')),
    (('pintar', 'fachada'),     ('pintura', 'fachada', 'hidrorrepelente')),
    (('arreglar', 'bano'),      ('ceramica', 'adhesivo', 'frague', 'sanitario')),
    (('renovar', 'bano'),       ('ceramica', 'adhesivo', 'frague', 'sanitario')),
    (('instalar', 'ceramica'),  ('adhesivo', 'frague', 'separador', 'ceramica')),
    (('armar', 'mueble'),       ('tornillo', 'pino', 'tablero', 'taladro')),
    (('armar', 'estante'),      ('tornillo', 'pino', 'tablero', 'escuadra')),
    (('hacer', 'repisa'),       ('tablero', 'escuadra', 'tornillo', 'barniz')),
    (('reparar', 'fuga'),       ('combinacion', 'lavaplatos', 'monomando', 'silicona')),
    (('cambiar', 'llave'),      ('combinacion', 'lavaplatos', 'monomando')),
    (('pintar', 'piscina'),     ('pintura', 'piscina', 'caucho')),
]


def expandir_consulta(palabras: list[str]) -> tuple[list[str], set[str]]:
    """Expande una lista de palabras tokenizadas con sinónimos ferreteros.

    Retorna:
        (palabras_expandidas, sinonimos_agregados)
        - palabras_expandidas: lista original + sinónimos (sin duplicados, orden estable).
        - sinonimos_agregados: set de palabras que fueron añadidas por sinónimo o concepto.
          Sirve para que el buscador aplique un scoring diferenciado (menor que las originales).
    """
    originales = set(palabras)
    agregados: set[str] = set()

    # ── Expansión por sinónimos directos ──
    for palabra in palabras:
        normalizada = _normalizar(palabra)
        if normalizada in SINONIMOS:
            for sinonimo in SINONIMOS[normalizada]:
                if sinonimo not in originales:
                    agregados.add(sinonimo)

    # ── Expansión por frases de dos palabras ──
    texto_completo = ' '.join(_normalizar(p) for p in palabras)
    for frase, sinonimos in SINONIMOS.items():
        if ' ' in frase and frase in texto_completo:
            for sinonimo in sinonimos:
                if sinonimo not in originales:
                    agregados.add(sinonimo)

    # ── Expansión por conceptos relacionados ──
    palabras_norm = {_normalizar(p) for p in palabras}
    for claves, expansiones in CONCEPTOS_RELACIONADOS:
        if all(any(c in p for p in palabras_norm) for c in claves):
            for expansion in expansiones:
                if expansion not in originales:
                    agregados.add(expansion)

    # Construir lista final: originales primero, luego sinónimos
    resultado = list(palabras)
    for sinonimo in sorted(agregados):
        if sinonimo not in originales:
            resultado.append(sinonimo)

    return resultado, agregados
