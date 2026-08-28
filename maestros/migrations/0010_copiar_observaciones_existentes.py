from django.db import migrations


def copiar_observaciones(apps, schema_editor):
    PerfilMaestro = apps.get_model("maestros", "PerfilMaestro")
    ApelacionMaestro = apps.get_model("maestros", "ApelacionMaestro")
    ObservacionMaestro = apps.get_model("maestros", "ObservacionMaestro")

    tipos_por_estado = {
        "RECHAZADO": "RECHAZO",
        "SUSPENDIDO": "SUSPENSION",
    }
    for perfil in PerfilMaestro.objects.exclude(observacion_admin="").iterator():
        observacion = ObservacionMaestro.objects.create(
            perfil_id=perfil.pk,
            tipo=tipos_por_estado.get(perfil.estado, "HISTORICA"),
            texto=perfil.observacion_admin,
        )
        ObservacionMaestro.objects.filter(pk=observacion.pk).update(
            creada_en=perfil.actualizado_en
        )

    for apelacion in ApelacionMaestro.objects.exclude(observacion_admin="").iterator():
        tipo = (
            "REACTIVACION"
            if apelacion.estado == "ACEPTADA"
            else "APELACION_RECHAZADA"
        )
        observacion = ObservacionMaestro.objects.create(
            perfil_id=apelacion.perfil_id,
            tipo=tipo,
            texto=apelacion.observacion_admin,
            registrada_por_id=apelacion.revisada_por_id,
        )
        fecha = apelacion.resuelta_en or apelacion.enviada_en
        ObservacionMaestro.objects.filter(pk=observacion.pk).update(creada_en=fecha)


class Migration(migrations.Migration):
    dependencies = [
        ("maestros", "0009_observacionmaestro"),
    ]

    operations = [
        migrations.RunPython(copiar_observaciones, migrations.RunPython.noop),
    ]
