from django.db import migrations


def restaurar_criterio_tecnico(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')

    # Un producto sin ficha tÃ©cnica validada no debe ofrecer cÃ¡lculos, ni
    # siquiera unitarios, como si fueran recomendaciÃ³n tÃ©cnica. Se mantiene
    # visible y disponible para compra, pero vuelve a estado pendiente.
    for producto in Producto.objects.filter(activo=True, informacion_tecnica_verificada=False):
        especificaciones = producto.especificaciones if isinstance(producto.especificaciones, dict) else {}
        especificaciones.pop('CÃ¡lculo disponible', None)
        producto.tipo_calculo = 'ninguno'
        producto.especificaciones = especificaciones
        producto.save(update_fields=['tipo_calculo', 'especificaciones'])


def reversa_no_destructiva(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [('productos', '0044_habilitar_calculo_unitario_catalogo')]

    operations = [migrations.RunPython(restaurar_criterio_tecnico, reversa_no_destructiva)]
