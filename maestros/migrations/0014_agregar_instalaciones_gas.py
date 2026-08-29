from django.db import migrations


NOMBRE_ESPECIALIDAD = "Instalaciones de gas"


def agregar_instalaciones_gas(apps, schema_editor):
    Especialidad = apps.get_model("maestros", "Especialidad")
    especialidad, _ = Especialidad.objects.get_or_create(
        nombre=NOMBRE_ESPECIALIDAD,
        defaults={
            "descripcion": (
                "Instalación, mantención y reparación de redes y artefactos "
                "de gas autorizadas por la SEC."
            ),
            "activa": True,
            "tipo_licencia": "SEC_GAS",
        },
    )

    campos_actualizados = []
    if not especialidad.activa:
        especialidad.activa = True
        campos_actualizados.append("activa")
    if especialidad.tipo_licencia != "SEC_GAS":
        especialidad.tipo_licencia = "SEC_GAS"
        campos_actualizados.append("tipo_licencia")
    if not especialidad.descripcion:
        especialidad.descripcion = (
            "Instalación, mantención y reparación de redes y artefactos "
            "de gas autorizadas por la SEC."
        )
        campos_actualizados.append("descripcion")
    if campos_actualizados:
        especialidad.save(update_fields=campos_actualizados)


def revertir_instalaciones_gas(apps, schema_editor):
    Especialidad = apps.get_model("maestros", "Especialidad")
    Especialidad.objects.filter(
        nombre=NOMBRE_ESPECIALIDAD,
        tipo_licencia="SEC_GAS",
    ).update(tipo_licencia="NINGUNA")


class Migration(migrations.Migration):
    dependencies = [
        ("maestros", "0013_configurar_licencias_especialidades"),
    ]

    operations = [
        migrations.RunPython(agregar_instalaciones_gas, revertir_instalaciones_gas),
    ]
