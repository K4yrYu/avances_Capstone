from django.db import migrations


USUARIOS_DEMO = (
    'demo_pedro_gonzalez',
    'demo_carlos_munoz',
    'demo_maria_soto',
    'demo_jorge_rojas',
    'demo_daniela_silva',
    'demo_luis_perez',
    'demo_andrea_torres',
    'demo_miguel_castro',
    'demo_roberto_vidal',
    'demo_carolina_reyes',
    'demo_pablo_herrera',
    'demo_ricardo_fuentes',
    'demo_pedro_carpintero',
    'demo_carlos_carpintero',
    'demo_maria_pintora',
    'demo_jorge_pintor',
    'demo_daniela_pintora',
    'demo_luis_gasfiter',
    'demo_andrea_electricista',
    'demo_miguel_ceramista',
    'demo_roberto_albanil',
    'demo_carolina_yeseria',
    'demo_pablo_jardinero',
    'demo_ricardo_techumbre',
    'demo_pintor_pendiente',
    'demo_carpintero_no_disponible',
)


def eliminar_maestros_demo(apps, schema_editor):
    Usuario = apps.get_model('usuarios', 'Usuario')
    Usuario.objects.filter(username__in=USUARIOS_DEMO).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('maestros', '0009_alinear_maestros_demo_ia'),
        ('usuarios', '0003_alter_usuario_email'),
    ]

    operations = [
        migrations.RunPython(eliminar_maestros_demo, migrations.RunPython.noop),
    ]
