from django.db import migrations


def _presentacion(producto):
    if producto.contenido and producto.unidad_contenido:
        return f'{producto.contenido} {producto.unidad_contenido}'
    return producto.unidad_venta or 'unidad'


def completar_fichas_tecnicas(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    for producto in Producto.objects.filter(activo=True).order_by('pk'):
        especificaciones = producto.especificaciones if isinstance(producto.especificaciones, dict) else {}
        tiene_ficha = any('ficha' in str(clave).casefold() for clave in especificaciones)
        cambios = []
        if not tiene_ficha:
            partes = [
                f'Categoría: {producto.categoria}.',
                f'Presentación: {_presentacion(producto)}.',
            ]
            if producto.marca:
                partes.append(f'Marca: {producto.marca}.')
            if producto.modelo:
                partes.append(f'Modelo o SKU: {producto.modelo}.')
            if producto.ambiente_uso and producto.ambiente_uso != 'no_aplica':
                partes.append(f'Ambiente de uso: {producto.ambiente_uso.replace("_", " ")}.')
            if producto.uso_recomendado:
                partes.append(f'Uso recomendado: {producto.uso_recomendado}')
            especificaciones['Ficha técnica'] = ' '.join(partes)
            producto.especificaciones = especificaciones
            cambios.append('especificaciones')

        # Un producto verificado con presentación definida puede calcularse por
        # unidad. No se inventa rendimiento para pinturas, superficies o peso.
        if (
            producto.informacion_tecnica_verificada
            and producto.tipo_calculo == 'ninguno'
            and producto.contenido
            and producto.unidad_contenido
        ):
            producto.tipo_calculo = 'unidad'
            cambios.append('tipo_calculo')
        if cambios:
            producto.save(update_fields=list(dict.fromkeys(cambios)))


def reversa_no_destructiva(apps, schema_editor):
    # No se eliminan fichas técnicas generadas para preservar datos del catálogo.
    pass


class Migration(migrations.Migration):
    dependencies = [('productos', '0042_completar_metadatos_catalogo_existente')]
    operations = [migrations.RunPython(completar_fichas_tecnicas, reversa_no_destructiva)]
