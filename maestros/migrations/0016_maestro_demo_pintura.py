from datetime import date

from django.contrib.auth.hashers import make_password
from django.db import migrations
from django.utils import timezone


USERNAME = "demo_camila_rojas_pintura"


def crear_maestra_pintura(apps, schema_editor):
    Usuario = apps.get_model("usuarios", "Usuario")
    Especialidad = apps.get_model("maestros", "Especialidad")
    PerfilMaestro = apps.get_model("maestros", "PerfilMaestro")
    TrabajoRealizado = apps.get_model("maestros", "TrabajoRealizado")

    especialidad, _ = Especialidad.objects.get_or_create(
        nombre="Pintura",
        defaults={
            "descripcion": "Preparación y pintura de superficies interiores y exteriores.",
            "activa": True,
            "tipo_licencia": "NINGUNA",
        },
    )
    usuario, _ = Usuario.objects.update_or_create(
        username=USERNAME,
        defaults={
            "first_name": "Camila",
            "last_name": "Rojas",
            "email": "camila.rojas.pintura@example.invalid",
            "rut": "26000103-5",
            "telefono": "+56970002103",
            "password": make_password(None),
            "is_active": True,
            "email_confirmado": True,
        },
    )
    perfil, _ = PerfilMaestro.objects.update_or_create(
        usuario=usuario,
        defaults={
            "descripcion_profesional": (
                "Maestra pintora especializada en preparación de muros y madera, "
                "pintura interior, esmaltes al agua y terminaciones residenciales."
            ),
            "anos_experiencia": 9,
            "region": "RM",
            "comuna": "Providencia",
            "zonas_trabajo": "Providencia, Ñuñoa, Santiago, Las Condes",
            "disponible": True,
            "estado": "APROBADO",
            "observacion_admin": "",
            "fecha_aprobacion": timezone.now(),
        },
    )
    perfil.especialidades.set([especialidad])
    trabajo, _ = TrabajoRealizado.objects.update_or_create(
        maestro=perfil,
        titulo="Renovación de dormitorio y superficies de madera",
        defaults={
            "descripcion": (
                "Preparación, lijado y aplicación de esmalte al agua en muros y "
                "elementos de madera, respetando los tiempos de secado."
            ),
            "comuna": "Providencia",
            "fecha": date(2026, 9, 18),
            "publicado": True,
        },
    )
    trabajo.especialidades.set([especialidad])


def eliminar_maestra_pintura(apps, schema_editor):
    Usuario = apps.get_model("usuarios", "Usuario")
    Usuario.objects.filter(username=USERNAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("maestros", "0015_maestros_demo_techumbre"),
    ]

    operations = [
        migrations.RunPython(crear_maestra_pintura, eliminar_maestra_pintura),
    ]
