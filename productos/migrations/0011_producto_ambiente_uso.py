from django.db import migrations, models


def clasificar_pinturas(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    pinturas = Producto.objects.filter(
        models.Q(categoria='Pinturas') | models.Q(tipo_calculo='pintura')
    )
    for producto in pinturas.iterator():
        texto = ' '.join((
            producto.nombre or '',
            producto.descripcion or '',
            producto.uso_recomendado or '',
        )).casefold()
        if 'piscina' in texto or 'estanque' in texto:
            ambiente = 'especial'
        elif 'fachada' in texto:
            ambiente = 'exterior'
        elif any(frase in texto for frase in (
            'interior y exterior',
            'interior o exterior',
            'interiores y exteriores',
            'interiores o exteriores',
        )):
            ambiente = 'interior_exterior'
        elif 'interior' in texto:
            ambiente = 'interior'
        elif 'exterior' in texto:
            ambiente = 'exterior'
        else:
            ambiente = 'especial'
        producto.ambiente_uso = ambiente
        producto.save(update_fields=['ambiente_uso'])


def revertir_clasificacion(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.update(ambiente_uso='no_aplica')


class Migration(migrations.Migration):

    dependencies = [
        ('productos', '0010_proveedores_y_pinturas_color'),
    ]

    operations = [
        migrations.AddField(
            model_name='producto',
            name='ambiente_uso',
            field=models.CharField(
                choices=[
                    ('no_aplica', 'No aplica'),
                    ('interior', 'Interior'),
                    ('exterior', 'Exterior'),
                    ('interior_exterior', 'Interior y exterior'),
                    ('especial', 'Uso especial o t\u00e9cnico'),
                ],
                default='no_aplica',
                max_length=20,
            ),
        ),
        migrations.RunPython(clasificar_pinturas, revertir_clasificacion),
    ]
