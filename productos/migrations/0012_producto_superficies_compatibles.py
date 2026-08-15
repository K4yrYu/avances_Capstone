from django.db import migrations, models


def clasificar_superficies(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    pinturas = Producto.objects.filter(
        models.Q(categoria='Pinturas') | models.Q(tipo_calculo='pintura')
    )
    latex = ['estuco', 'hormigon', 'ladrillo', 'fibrocemento', 'pasta_muro', 'yeso', 'yeso_carton']
    for producto in pinturas.iterator():
        texto = f'{producto.nombre} {producto.descripcion}'.casefold()
        if 'piscina' in texto:
            superficies = ['piscina_estanque', 'hormigon']
        elif 'fachada' in texto:
            superficies = ['estuco', 'hormigon', 'ladrillo', 'fibrocemento']
        elif 'semibrillo' in texto:
            superficies = ['estuco', 'hormigon', 'ladrillo', 'fibrocemento', 'metal_galvanizado']
        elif 'satinado' in texto:
            superficies = ['hormigon', 'pasta_muro', 'estuco']
        elif 'passol' in texto:
            superficies = ['yeso_carton', 'fibrocemento', 'madera', 'hormigon', 'yeso', 'ladrillo', 'estuco']
        else:
            superficies = latex
        producto.superficies_compatibles = superficies
        producto.save(update_fields=['superficies_compatibles'])


def revertir_superficies(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.update(superficies_compatibles=[])


class Migration(migrations.Migration):

    dependencies = [
        ('productos', '0011_producto_ambiente_uso'),
    ]

    operations = [
        migrations.AddField(
            model_name='producto',
            name='superficies_compatibles',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(clasificar_superficies, revertir_superficies),
    ]
