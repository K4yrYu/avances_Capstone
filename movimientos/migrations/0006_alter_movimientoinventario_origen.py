from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('movimientos', '0005_alter_movimientoinventario_tipo')]

    operations = [
        migrations.AlterField(
            model_name='movimientoinventario',
            name='origen',
            field=models.CharField(
                choices=[
                    ('stock_inicial', 'Stock inicial'), ('reposicion', 'Reposición'),
                    ('venta', 'Venta'), ('ajuste_manual', 'Ajuste manual'),
                    ('merma', 'Merma'), ('edicion_producto', 'Edición de producto'),
                    ('eliminacion_producto', 'Eliminación de producto'),
                ],
                db_index=True,
                max_length=30,
            ),
        ),
    ]
