"""Interpreta problemas cotidianos sin consultar ni inventar datos del catálogo."""

import re
import unicodedata


CORRECCIONES = {
    'clabos': 'clavos', 'clabo': 'clavo', 'aujero': 'agujero',
    'aujeros': 'agujeros', 'abujero': 'agujero', 'abujeros': 'agujeros',
    'filtraccion': 'filtracion', 'taladroo': 'taladro',
}


def normalizar_lenguaje_cotidiano(valor):
    texto = unicodedata.normalize('NFKD', str(valor or '').lower())
    texto = ''.join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r'[^a-z0-9\s]', ' ', texto)
    return ' '.join(CORRECCIONES.get(p, p) for p in texto.split())


SITUACIONES = (
    {
        'codigo': 'riesgo_gas', 'tipo': 'riesgo',
        'patrones': (r'\b(?:olor|huele|fuga|escape)\b.{0,25}\bgas\b',),
        'mensaje': ('Esto puede ser una fuga de gas. No enciendas ni apagues '
                    'interruptores, no uses fuego y aléjate del área.'),
        'especialidad': 'Gasfitería',
    },
    {
        'codigo': 'riesgo_electrico', 'tipo': 'riesgo',
        'patrones': (
            r'\b(?:chispa|chispas|humo|olor a quemado)\b.{0,35}\b(?:enchufe|cable|interruptor|tablero|electric)',
            r'\b(?:enchufe|cable|interruptor|tablero)\b.{0,35}\b(?:chispa|chispas|humo|quemado|caliente)',
        ),
        'mensaje': ('Hay señales de un posible riesgo eléctrico. No manipules la '
                    'conexión ni el punto afectado.'),
        'especialidad': 'Electricidad',
    },
    {
        'codigo': 'riesgo_estructural', 'tipo': 'riesgo',
        'patrones': (r'\b(?:techo|muro|pared|viga|estructura)\b.{0,35}\b(?:cediendo|hundido|hundiendo|por caer|se mueve mucho)',),
        'mensaje': ('La descripción puede indicar un problema estructural. No '
                    'permanezcas bajo la zona ni intentes apuntalarla.'),
        'especialidad': 'Construcción',
    },
    {
        'codigo': 'clavar', 'tipo': 'producto_directo',
        'patrones': (r'\b(?:poner|meter|clavar|afirmar|fijar)\b.{0,24}\bclavos?\b', r'\bclavar\b'),
        'consulta': 'martillo', 'uso': 'clavar o poner clavos',
    },
    {
        'codigo': 'atornillar', 'tipo': 'producto_directo',
        'patrones': (r'\b(?:poner|apretar|soltar|sacar|quitar)\b.{0,24}\btornillos?\b',),
        'consulta': 'destornillador', 'uso': 'trabajar con tornillos',
    },
    {
        'codigo': 'perforar', 'tipo': 'aclaracion',
        'patrones': (r'\b(?:hacer|abrir)\b.{0,18}\b(?:agujeros?|hoyos?)\b', r'\bperforar\b'),
        'contexto': 'Para perforar sin dañar la superficie',
        'preguntas': ('¿Es hormigón, ladrillo, madera, metal o cerámica?',
                      '¿Qué diámetro y profundidad aproximados necesitas?',
                      '¿Es para colgar algo? Indica su peso aproximado.'),
        'sugerencias': ('Es un muro de hormigón', 'Es madera', 'Es cerámica'),
    },
    {
        'codigo': 'cortar_madera', 'tipo': 'aclaracion',
        'patrones': (r'\b(?:cortar|trozar|achicar)\b.{0,30}\b(?:madera|tabla|tablero|melamina)',),
        'contexto': 'Para elegir una herramienta y hoja compatibles',
        'preguntas': ('¿Es madera maciza, tablero, terciado o melamina?',
                      '¿Cuál es su espesor aproximado?',
                      '¿Necesitas un corte recto o curvo y será un uso ocasional o frecuente?'),
        'sugerencias': ('Madera maciza y corte recto', 'Melamina y corte recto'),
    },
    {
        'codigo': 'lijar', 'tipo': 'aclaracion',
        'patrones': (r'\b(?:dejar|hacer)\b.{0,18}\blis[oa]\b', r'\b(?:lijar|sacar asperezas|quitar asperezas)'),
        'contexto': 'Para elegir el abrasivo correcto',
        'preguntas': ('¿La superficie es madera, metal, muro u otro material?',
                      '¿Quieres quitar pintura, nivelar o dar terminación fina?',
                      '¿Qué tamaño aproximado tiene el área?'),
        'sugerencias': ('Es madera y quiero dejarla suave', 'Es metal con pintura vieja'),
    },
    {
        'codigo': 'desague_obstruido', 'tipo': 'aclaracion',
        'patrones': (
            r'\b(?:agua|lavamanos|lavaplatos|ducha|tina)\b.{0,30}\b(?:no baja|baja lento|tapado|atascado)',
            r'\b(?:destapar|desatascar)\b.{0,25}\b(?:lavamanos|lavaplatos|ducha|tina|desague)',
        ),
        'contexto': 'Primero hay que identificar el alcance de la obstrucción',
        'preguntas': ('¿Ocurre en lavamanos, lavaplatos, ducha, tina o varios desagües?',
                      '¿El agua baja lentamente o está completamente detenida?',
                      '¿Hay olor fuerte, retorno de agua o una fuga visible?'),
        'sugerencias': ('Es el lavaplatos y baja lento', 'Es la ducha y no baja'),
        'especialidad': 'Gasfitería',
    },
    {
        'codigo': 'filtracion_techo', 'tipo': 'aclaracion',
        'patrones': (
            r'\b(?:techo|techumbre)\b.{0,35}\b(?:filtra|filtracion|gotea|pasa agua|entra agua)',
            r'\b(?:filtra|filtracion|gotea|pasa agua|entra agua)\b.{0,35}\b(?:techo|techumbre)',
        ),
        'contexto': 'La filtración puede provenir de la cubierta, una unión o el drenaje',
        'preguntas': ('¿La cubierta es zinc, policarbonato, teja u otro material?',
                      '¿Dónde aparece el agua y ocurre solo con lluvia?',
                      '¿Ves una plancha rota, tornillo suelto, unión abierta o canaleta rebalsada?'),
        'sugerencias': ('Es techo de zinc', 'Es policarbonato', 'No identifico el origen'),
        'especialidad': 'Techumbre',
    },
    {
        'codigo': 'humedad_muro', 'tipo': 'aclaracion',
        'patrones': (r'\b(?:pared|muro)\b.{0,35}\b(?:negra|negro|humeda|humedo|moho|hongos?)',
                     r'\b(?:moho|hongos?|humedad)\b.{0,25}\b(?:pared|muro)'),
        'contexto': 'Antes de cubrir la mancha hay que encontrar el origen de la humedad',
        'preguntas': ('¿Es un muro interior o exterior y qué hay al otro lado?',
                      '¿Aparece con lluvia, cerca de una tubería o por condensación?',
                      '¿La pintura está inflada, el muro mojado o solo hay manchas?'),
        'sugerencias': ('Aparece cuando llueve', 'Está junto a una tubería', 'Parece condensación'),
    },
    {
        'codigo': 'grieta', 'tipo': 'aclaracion',
        'patrones': (r'\b(?:tapar|rellenar|arreglar|reparar)\b.{0,25}\b(?:grieta|trizadura|fisura)',
                     r'\b(?:grieta|trizadura|fisura)\b.{0,25}\b(?:pared|muro|piso|techo)'),
        'contexto': 'La reparación depende de la superficie y del movimiento de la grieta',
        'preguntas': ('¿Está en muro, cielo, piso u otra superficie y de qué material es?',
                      '¿Qué ancho y largo aproximados tiene?',
                      '¿Ha crecido, atraviesa el muro o reaparece después de repararla?'),
        'sugerencias': ('Es una fisura fina en yeso-cartón', 'Es una grieta en hormigón'),
    },
    {
        'codigo': 'puerta_roza', 'tipo': 'aclaracion',
        'patrones': (r'\bpuerta\b.{0,35}\b(?:topa|topando|roza|rozando|arrastra|no cierra)',),
        'contexto': 'Hay que distinguir entre bisagras sueltas, hinchazón y desnivel',
        'preguntas': ('¿Roza arriba, abajo o al costado de la cerradura?',
                      '¿Es de madera, metal u otro material?',
                      '¿Las bisagras están sueltas o cambió después de humedad?'),
        'sugerencias': ('Roza contra el piso', 'Las bisagras están sueltas'),
        'especialidad': 'Carpintería',
    },
    {
        'codigo': 'objeto_suelto', 'tipo': 'aclaracion',
        'patrones': (r'\b(?:se solto|esta suelto|esta suelta|se mueve)\b',),
        'contexto': 'Para recomendar una fijación segura necesito identificar el soporte',
        'preguntas': ('¿Qué objeto se soltó?',
                      '¿Estaba fijado a hormigón, ladrillo, madera, metal o yeso-cartón?',
                      '¿Cuánto pesa aproximadamente y conserva sus fijaciones?'),
        'sugerencias': ('Es una repisa en muro', 'Es una bisagra de madera'),
    },
    {
        'codigo': 'oxido', 'tipo': 'aclaracion',
        'patrones': (r'\b(?:quitar|sacar|evitar|proteger)\b.{0,25}\boxido\b',
                     r'\b(?:se oxida|esta oxidado|esta oxidada)'),
        'contexto': 'El tratamiento cambia según el metal, el daño y la exposición',
        'preguntas': ('¿Qué objeto o superficie metálica está oxidada?',
                      '¿Está en interior, exterior o con humedad permanente?',
                      '¿El óxido es superficial o ya debilitó/perforó el metal?'),
        'sugerencias': ('Es metal exterior con óxido superficial', 'El metal está perforado'),
    },
    {
        'codigo': 'proteger_madera', 'tipo': 'aclaracion',
        'patrones': (r'\b(?:proteger|cuidar|sellar)\b.{0,30}\bmadera\b.{0,30}\b(?:agua|lluvia|humedad|exterior|sol)',
                     r'\bmadera\b.{0,30}\b(?:no se moje|no le entre agua|dure afuera)'),
        'contexto': 'Para elegir una protección compatible necesito conocer la exposición',
        'preguntas': ('¿Estará en interior o exterior y recibirá lluvia o sol directo?',
                      '¿Está nueva, pintada, barnizada o deteriorada?',
                      '¿Quieres mantener la veta visible o aplicar un color cubriente?'),
        'sugerencias': ('Es madera nueva para exterior', 'Quiero mantener la veta visible'),
    },
)


def detectar_situacion_cotidiana(mensaje):
    """Devuelve la primera situación inequívoca; los riesgos tienen prioridad."""
    texto = normalizar_lenguaje_cotidiano(mensaje)
    for situacion in SITUACIONES:
        if any(re.search(patron, texto) for patron in situacion['patrones']):
            return {**situacion, 'texto_normalizado': texto}
    return None
