from django.db import migrations


IMAGENES = {
    'SFI-ELE-ADA-EU-CL-10A': (
        'productos/Adaptador_enchufe_europeo_a_chileno_Schuko_10A_250V.jpg'
    ),
    'SFI-ELE-ADA-EUROAM-10A': (
        'productos/Adaptador_euroamericano_Vimar_2P_10A_250V.jpg'
    ),
    'SFI-ELE-ADA-UNIV-VIAJE': (
        'productos/Adaptador_universal_viaje_US_EU_UK_AU_10A_250V.jpg'
    ),
}


def asociar_imagenes(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    for sku, imagen in IMAGENES.items():
        Producto.objects.filter(sku=sku).update(imagen=imagen)


def retirar_imagenes(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.filter(sku__in=IMAGENES).update(imagen='')


class Migration(migrations.Migration):
    dependencies = [('productos', '0071_adaptadores_de_enchufe')]

    operations = [migrations.RunPython(asociar_imagenes, retirar_imagenes)]
