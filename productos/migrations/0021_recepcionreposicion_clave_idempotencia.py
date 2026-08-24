import uuid

from django.db import migrations, models


def completar_claves(apps, schema_editor):
    Recepcion = apps.get_model('productos', 'RecepcionReposicion')
    for recepcion in Recepcion.objects.filter(clave_idempotencia='').iterator():
        recepcion.clave_idempotencia = f'legacy-{recepcion.pk}-{uuid.uuid4().hex}'
        recepcion.save(update_fields=['clave_idempotencia'])


class Migration(migrations.Migration):

    dependencies = [
        ('productos', '0020_alter_solicitudreposicion_estado_recepcionreposicion_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='recepcionreposicion',
            name='clave_idempotencia',
            field=models.CharField(default='', max_length=100),
            preserve_default=False,
        ),
        migrations.RunPython(completar_claves, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='recepcionreposicion',
            name='clave_idempotencia',
            field=models.CharField(max_length=100, unique=True),
        ),
    ]
