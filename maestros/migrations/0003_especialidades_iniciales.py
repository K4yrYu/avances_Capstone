from django.db import migrations


ESPECIALIDADES = (
    ("Albañilería", "Construcción, reparación y terminaciones en muros y estructuras."),
    ("Carpintería", "Fabricación, instalación y reparación de elementos de madera."),
    ("Cerámica y revestimientos", "Instalación y reparación de pisos y revestimientos."),
    ("Climatización", "Instalación y mantenimiento de sistemas de climatización."),
    ("Electricidad", "Instalaciones, reparaciones y mantenimiento eléctrico."),
    ("Gasfitería", "Instalaciones y reparaciones de agua y artefactos sanitarios."),
    ("Impermeabilización", "Tratamiento preventivo y reparación de filtraciones."),
    ("Instalaciones sanitarias", "Redes sanitarias, desagües y soluciones domiciliarias."),
    ("Jardinería", "Mantención y habilitación de jardines y espacios exteriores."),
    ("Pintura", "Preparación y pintura de superficies interiores y exteriores."),
    ("Soldadura", "Fabricación y reparación de estructuras metálicas."),
    ("Techumbre", "Instalación, mantención y reparación de techos y cubiertas."),
    ("Yesería y tabiquería", "Tabiques, cielos y terminaciones en yeso-cartón."),
)


def crear_especialidades(apps, schema_editor):
    Especialidad = apps.get_model("maestros", "Especialidad")
    for nombre, descripcion in ESPECIALIDADES:
        Especialidad.objects.get_or_create(
            nombre=nombre,
            defaults={"descripcion": descripcion, "activa": True},
        )


class Migration(migrations.Migration):
    dependencies = [("maestros", "0002_perfilmaestro_region")]

    operations = [migrations.RunPython(crear_especialidades, migrations.RunPython.noop)]
