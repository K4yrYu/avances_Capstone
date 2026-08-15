import unicodedata

from productos.models import Producto


ETIQUETAS_CONTEXTO = {
    'interior': 'interior',
    'exterior': 'exterior',
    'piscina': 'piscina',
}


def _normalizar(valor):
    texto = unicodedata.normalize('NFKD', str(valor or '').casefold())
    return ''.join(caracter for caracter in texto if not unicodedata.combining(caracter))


def detectar_contexto_pintura(datos):
    tipo_superficie = str(datos.get('tipo_superficie') or '')
    texto = _normalizar(
        ' '.join([
            str(datos.get('proyecto') or ''),
            str(datos.get('consulta_producto') or ''),
            str(datos.get('respuesta') or ''),
        ])
    )
    if tipo_superficie == 'piscina_estanque' or 'piscina' in texto or 'estanque' in texto:
        return 'piscina'
    ambiente = str(datos.get('ambiente') or '')
    if ambiente in {'interior', 'exterior'}:
        return ambiente
    return ''


def pinturas_compatibles(contexto, color='', limite=6):
    if contexto not in ETIQUETAS_CONTEXTO:
        return []
    candidatas = list(
        Producto.objects.filter(
            activo=True,
            categoria='Pinturas',
            stock__gt=0,
            color_hex__gt='',
            informacion_tecnica_verificada=True,
        ).order_by('precio', 'nombre')
    )
    compatibles = []
    for producto in candidatas:
        es_piscina = (
            producto.tipo_pintura == 'caucho_clorado'
            or 'piscina_estanque' in producto.superficies_compatibles
        )
        if contexto == 'piscina' and es_piscina:
            compatibles.append(producto)
        elif contexto == 'interior' and not es_piscina and producto.ambiente_uso in {
            'interior', 'interior_exterior',
        }:
            compatibles.append(producto)
        elif contexto == 'exterior' and not es_piscina and producto.ambiente_uso in {
            'exterior', 'interior_exterior',
        }:
            compatibles.append(producto)

    color_buscado = _normalizar(color)
    if color_buscado:
        coincidencias = [
            producto for producto in compatibles
            if color_buscado in _normalizar(producto.color)
            or color_buscado in _normalizar(producto.nombre)
        ]
        if coincidencias:
            compatibles = coincidencias

    prioridad_ambiente = {
        'interior': {'interior': 0, 'interior_exterior': 1},
        'exterior': {'exterior': 0, 'interior_exterior': 1},
        'piscina': {'especial': 0},
    }
    compatibles.sort(key=lambda producto: (
        prioridad_ambiente[contexto].get(producto.ambiente_uso, 2),
        producto.precio,
        producto.color,
        producto.nombre,
    ))
    return compatibles[:limite]


def color_publico(producto):
    return {
        'id': producto.id,
        'nombre': producto.nombre,
        'marca': producto.marca,
        'color': producto.color,
        'color_hex': producto.color_hex,
        'ambiente': producto.get_ambiente_uso_display(),
        'terminacion': producto.get_terminacion_display(),
        'precio': producto.precio,
        'stock': producto.stock,
        'imagen': producto.imagen.url if producto.imagen else '',
        'url': f'/productos/{producto.id}/',
    }
