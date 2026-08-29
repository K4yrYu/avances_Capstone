from django.db import migrations


ELECTRICAS = (
    "Electricidad",
    "Instalaciones eléctricas",
    "Electricista",
)

GAS = (
    "Instalaciones de gas",
    "Instalador de gas",
    "Gasista",
)


def configurar_licencias(apps, schema_editor):
    Especialidad = apps.get_model("maestros", "Especialidad")
    Especialidad.objects.filter(nombre__in=ELECTRICAS).update(
        tipo_licencia="SEC_ELECTRICA"
    )
    Especialidad.objects.filter(nombre__in=GAS).update(tipo_licencia="SEC_GAS")


def revertir_configuracion(apps, schema_editor):
    Especialidad = apps.get_model("maestros", "Especialidad")
    Especialidad.objects.filter(
        nombre__in=ELECTRICAS,
        tipo_licencia="SEC_ELECTRICA",
    ).update(tipo_licencia="NINGUNA")
    Especialidad.objects.filter(
        nombre__in=GAS,
        tipo_licencia="SEC_GAS",
    ).update(tipo_licencia="NINGUNA")


class Migration(migrations.Migration):
    dependencies = [
        ("maestros", "0012_especialidad_tipo_licencia_documentomaestro_and_more"),
    ]

    operations = [
        migrations.RunPython(configurar_licencias, revertir_configuracion),
    ]
