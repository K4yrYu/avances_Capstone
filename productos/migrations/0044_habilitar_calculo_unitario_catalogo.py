from django.db import migrations


def habilitar_calculo_unitario_seguro(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')

    # Los productos sin rendimiento tÃ©cnico validado se cotizan por unidad.
    # No se marca su ficha como verificada ni se inventa cobertura: solamente
    # se habilita cantidad Ã— precio para que el catÃ¡logo completo sea usable.
    for producto in Producto.objects.filter(activo=True, informacion_tecnica_verificada=False).exclude(
        tipo_calculo='unidad'
    ):
        if not producto.contenido or not producto.unidad_contenido:
            continue

        especificaciones = producto.especificaciones if isinstance(producto.especificaciones, dict) else {}
        tipo_anterior = producto.tipo_calculo
        if tipo_anterior != 'ninguno':
            especificaciones.setdefault(
                'CÃ¡lculo disponible',
                'CotizaciÃ³n unitaria (cantidad Ã— precio). El rendimiento tÃ©cnico debe validarse con el proveedor.',
            )

        producto.tipo_calculo = 'unidad'
        producto.especificaciones = especificaciones
        producto.save(update_fields=['tipo_calculo', 'especificaciones'])


def reversa_no_destructiva(apps, schema_editor):
    # No se restaura un tipo anterior para no borrar la trazabilidad del catÃ¡logo.
    pass


class Migration(migrations.Migration):
    dependencies = [('productos', '0043_fichas_tecnicas_y_calculos_validos')]

    operations = [migrations.RunPython(habilitar_calculo_unitario_seguro, reversa_no_destructiva)]
