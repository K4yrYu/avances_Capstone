from django.db import migrations, models


def asignar_roles_existentes(apps, schema_editor):
    Usuario = apps.get_model('usuarios', 'Usuario')
    Usuario.objects.filter(is_staff=True).update(rol='administrador')
    Usuario.objects.filter(is_staff=False).update(rol='cliente')


class Migration(migrations.Migration):
    dependencies = [('usuarios', '0005_inicializar_expiracion_registros_pendientes')]

    operations = [
        migrations.AddField(
            model_name='usuario',
            name='rol',
            field=models.CharField(
                choices=[
                    ('cliente', 'Cliente'),
                    ('repartidor', 'Repartidor'),
                    ('retiros', 'Encargado de retiros'),
                    ('administrador', 'Administrador'),
                ],
                default='cliente',
                max_length=20,
            ),
        ),
        migrations.RunPython(asignar_roles_existentes, migrations.RunPython.noop),
    ]
