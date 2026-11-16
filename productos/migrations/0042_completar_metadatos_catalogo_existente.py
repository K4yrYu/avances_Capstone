import re
from decimal import Decimal, InvalidOperation

from django.db import migrations


def _contenido_desde_texto(texto):
    coincidencia = re.search(
        r'(\d+(?:[.,]\d+)?)\s*(m²|m2|kg|gr|g|ml|litros?|litro|l|metros?|metro|m|unidades?|unidad)\b',
        str(texto or '').casefold(),
    )
    if not coincidencia:
        return Decimal('1.000'), 'unidad'
    try:
        cantidad = Decimal(coincidencia.group(1).replace(',', '.'))
    except InvalidOperation:
        return Decimal('1.000'), 'unidad'
    unidad = coincidencia.group(2)
    equivalencias = {
        'm²': 'm2', 'm2': 'm2', 'kg': 'kg', 'gr': 'g', 'g': 'g',
        'ml': 'ml', 'litro': 'l', 'litros': 'l', 'l': 'l',
        'metro': 'm', 'metros': 'm', 'm': 'm',
        'unidad': 'unidad', 'unidades': 'unidad',
    }
    return cantidad, equivalencias.get(unidad, 'unidad')


def completar_metadatos(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Proveedor = apps.get_model('productos', 'Proveedor')
    proveedor = Proveedor.objects.filter(nombre='Proveedor General SFI', activo=True).first()

    for producto in Producto.objects.filter(activo=True).order_by('pk'):
        cambios = []
        if not producto.sku:
            base_sku = f'SFI-LEG-{producto.pk:05d}'
            sku = base_sku
            consecutivo = 1
            while Producto.objects.filter(sku=sku).exclude(pk=producto.pk).exists():
                consecutivo += 1
                sku = f'{base_sku}-{consecutivo}'
            producto.sku = sku
            cambios.append('sku')
        if not producto.marca:
            producto.marca = 'Genérico SFI'
            cambios.append('marca')
        if not producto.modelo:
            producto.modelo = producto.sku
            cambios.append('modelo')
        if producto.proveedor_id is None and proveedor:
            producto.proveedor_id = proveedor.pk
            cambios.append('proveedor')
        if producto.contenido is None or not producto.unidad_contenido:
            contenido, unidad = _contenido_desde_texto(
                f'{producto.nombre} {producto.descripcion}'
            )
            producto.contenido = contenido
            producto.unidad_contenido = unidad
            cambios.extend(['contenido', 'unidad_contenido'])
        if cambios:
            producto.save(update_fields=list(dict.fromkeys(cambios)))


def reversa_no_destructiva(apps, schema_editor):
    # Los campos completados se convierten en parte de la ficha comercial;
    # no se eliminan al revertir para no destruir datos administrados.
    pass


class Migration(migrations.Migration):
    dependencies = [('productos', '0041_catalogo_fichas_completas_proyectos')]
    operations = [migrations.RunPython(completar_metadatos, reversa_no_destructiva)]
