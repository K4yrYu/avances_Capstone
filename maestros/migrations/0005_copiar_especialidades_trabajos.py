from django.db import migrations


def copiar_especialidades(apps, schema_editor):
    TrabajoRealizado = apps.get_model("maestros", "TrabajoRealizado")
    through = TrabajoRealizado.especialidades.through
    relaciones = [
        through(
            trabajorealizado_id=trabajo.id,
            especialidad_id=trabajo.especialidad_id,
        )
        for trabajo in TrabajoRealizado.objects.exclude(especialidad_id=None)
    ]
    through.objects.bulk_create(relaciones, ignore_conflicts=True)


class Migration(migrations.Migration):
    dependencies = [("maestros", "0004_trabajorealizado_especialidades")]

    operations = [migrations.RunPython(copiar_especialidades, migrations.RunPython.noop)]
