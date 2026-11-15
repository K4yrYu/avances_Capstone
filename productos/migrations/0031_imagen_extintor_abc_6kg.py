from django.db import migrations


SKU_EXTINTOR = 'SFI-SEG-EXT-ABC6'
RUTA_IMAGEN = 'productos/extintor_ABC_polvo_quimico_seco_6kg.webp'


def asociar_imagen_extintor(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.filter(sku=SKU_EXTINTOR).update(imagen=RUTA_IMAGEN)


def retirar_asociacion_imagen(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.filter(
        sku=SKU_EXTINTOR,
        imagen=RUTA_IMAGEN,
    ).update(imagen='')


class Migration(migrations.Migration):
    dependencies = [
        ('productos', '0030_extintor_abc_6kg'),
    ]

    operations = [
        migrations.RunPython(asociar_imagen_extintor, retirar_asociacion_imagen),
    ]
