from datetime import timedelta

from django.db import migrations


def inicializar_expiracion(apps, schema_editor):
    Usuario = apps.get_model('usuarios', 'Usuario')
    pendientes = Usuario.objects.filter(
        is_staff=False,
        is_superuser=False,
        is_active=False,
        email_confirmado=False,
        activacion_expira_en__isnull=True,
    )
    for usuario in pendientes.iterator():
        usuario.correo_activacion_enviado_en = usuario.date_joined
        usuario.activacion_expira_en = usuario.date_joined + timedelta(hours=24)
        usuario.save(update_fields=[
            'correo_activacion_enviado_en', 'activacion_expira_en',
        ])


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0004_usuario_expiracion_activacion'),
    ]

    operations = [
        migrations.RunPython(inicializar_expiracion, migrations.RunPython.noop),
    ]
