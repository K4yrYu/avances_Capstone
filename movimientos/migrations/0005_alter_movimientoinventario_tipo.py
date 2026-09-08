from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('movimientos', '0004_loteinventario_fecha_ingreso')]

    operations = [
        migrations.AlterField(
            model_name='movimientoinventario',
            name='tipo',
            field=models.CharField(
                choices=[
                    ('inicial', 'Stock inicial'), ('solicitud', 'En proceso'),
                    ('entrada', 'Entrada'), ('salida', 'Salida'),
                    ('ajuste', 'Ajuste'), ('reajuste', 'Reajuste de información'),
                    ('modificacion', 'Modificación'), ('eliminacion', 'Eliminación'),
                    ('incidencia', 'Incidencia'),
                ],
                db_index=True,
                max_length=20,
            ),
        ),
    ]
