from datetime import date

from django.contrib.auth.hashers import make_password
from django.db import migrations
from django.utils import timezone


MAESTROS_TECHUMBRE = (
    {
        "username": "demo_diego_morales_techumbre",
        "nombre": "Diego",
        "apellido": "Morales",
        "email": "diego.morales.techumbre@example.invalid",
        "rut": "26000101-9",
        "telefono": "+56970002101",
        "experiencia": 12,
        "comuna": "Huechuraba",
        "zonas": "Huechuraba, Quilicura, Conchalí, Recoleta",
        "especialidades": (
            "Techumbre",
            "Carpintería",
            "Impermeabilización",
        ),
        "descripcion": (
            "Maestro de techumbre especializado en cubiertas de policarbonato, "
            "teja asfáltica, reparación de filtraciones e impermeabilización "
            "residencial. Atiende proyectos menores y mantenciones en el sector norte "
            "de Santiago."
        ),
        "trabajo": {
            "titulo": "Renovación de cubierta de policarbonato",
            "descripcion": (
                "Reemplazo de planchas de policarbonato, perfiles de unión, cintas "
                "de cierre y sellos compatibles, con revisión de pendiente y drenaje."
            ),
            "comuna": "Huechuraba",
            "fecha": date(2026, 8, 14),
        },
    },
    {
        "username": "demo_sebastian_fuentes_techumbre",
        "nombre": "Sebastián",
        "apellido": "Fuentes",
        "email": "sebastian.fuentes.techumbre@example.invalid",
        "rut": "26000102-7",
        "telefono": "+56970002102",
        "experiencia": 15,
        "comuna": "Maipú",
        "zonas": "Maipú, Cerrillos, Estación Central, Santiago",
        "especialidades": (
            "Techumbre",
            "Soldadura",
            "Impermeabilización",
        ),
        "descripcion": (
            "Maestro de techumbre especializado en cubiertas de zinc y soluciones "
            "metálicas, hojalatería, evacuación de aguas lluvia y reparación "
            "de filtraciones en viviendas."
        ),
        "trabajo": {
            "titulo": "Reparación de techumbre metálica y canaletas",
            "descripcion": (
                "Reposición de planchas de zinc, fijaciones y sellos, junto con "
                "mantención de canaletas y bajadas de aguas lluvia."
            ),
            "comuna": "Maipú",
            "fecha": date(2026, 7, 22),
        },
    },
)


def crear_maestros_techumbre(apps, schema_editor):
    Usuario = apps.get_model("usuarios", "Usuario")
    Especialidad = apps.get_model("maestros", "Especialidad")
    PerfilMaestro = apps.get_model("maestros", "PerfilMaestro")
    TrabajoRealizado = apps.get_model("maestros", "TrabajoRealizado")

    for datos in MAESTROS_TECHUMBRE:
        usuario, _ = Usuario.objects.update_or_create(
            username=datos["username"],
            defaults={
                "first_name": datos["nombre"],
                "last_name": datos["apellido"],
                "email": datos["email"],
                "rut": datos["rut"],
                "telefono": datos["telefono"],
                "password": make_password(None),
                "is_active": True,
                "email_confirmado": True,
            },
        )
        especialidades = list(Especialidad.objects.filter(
            nombre__in=datos["especialidades"],
            activa=True,
        ))
        perfil, _ = PerfilMaestro.objects.update_or_create(
            usuario=usuario,
            defaults={
                "descripcion_profesional": datos["descripcion"],
                "anos_experiencia": datos["experiencia"],
                "region": "RM",
                "comuna": datos["comuna"],
                "zonas_trabajo": datos["zonas"],
                "disponible": True,
                "estado": "APROBADO",
                "observacion_admin": "",
                "fecha_aprobacion": timezone.now(),
            },
        )
        perfil.especialidades.set(especialidades)
        trabajo_datos = datos["trabajo"]
        trabajo, _ = TrabajoRealizado.objects.update_or_create(
            maestro=perfil,
            titulo=trabajo_datos["titulo"],
            defaults={
                "descripcion": trabajo_datos["descripcion"],
                "comuna": trabajo_datos["comuna"],
                "fecha": trabajo_datos["fecha"],
                "publicado": True,
            },
        )
        trabajo.especialidades.set(
            [item for item in especialidades if item.nombre == "Techumbre"]
        )


def eliminar_maestros_techumbre(apps, schema_editor):
    Usuario = apps.get_model("usuarios", "Usuario")
    Usuario.objects.filter(
        username__in=[item["username"] for item in MAESTROS_TECHUMBRE]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("maestros", "0014_agregar_instalaciones_gas"),
    ]

    operations = [
        migrations.RunPython(
            crear_maestros_techumbre,
            eliminar_maestros_techumbre,
        ),
    ]
