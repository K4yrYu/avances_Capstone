from django.db import migrations


IMAGENES_POR_SKU = {
    'TEST-ADH-SEL-PC': 'productos/catalogo_extendido/TEST-ADH-SEL-PC.jpg',
    'TEST-AIS-EPS-50': 'productos/catalogo_extendido/TEST-AIS-EPS-50.jpg',
    'TEST-AIS-LAN-12': 'productos/catalogo_extendido/TEST-AIS-LAN-12.jpg',
    'TEST-ALB-ARE-25': 'productos/catalogo_extendido/TEST-ALB-ARE-25.jpg',
    'TEST-ALB-CEM-25': 'productos/catalogo_extendido/TEST-ALB-CEM-25.jpg',
    'TEST-ALB-GRA-25': 'productos/catalogo_extendido/TEST-ALB-GRA-25.jpg',
    'TEST-ALB-LAD-FIS': 'productos/catalogo_extendido/TEST-ALB-LAD-FIS.jpg',
    'TEST-ALB-MAL-C92': 'productos/catalogo_extendido/TEST-ALB-MAL-C92.jpg',
    'TEST-CON-BLO-14': 'productos/catalogo_extendido/TEST-CON-BLO-14.jpg',
    'TEST-CON-OSB-111': 'productos/catalogo_extendido/TEST-CON-OSB-111.jpg',
}


def asignar_imagenes(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    for sku, imagen in IMAGENES_POR_SKU.items():
        Producto.objects.filter(sku=sku).update(imagen=imagen)


def retirar_imagenes(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    for sku, imagen in IMAGENES_POR_SKU.items():
        Producto.objects.filter(sku=sku, imagen=imagen).update(imagen='')


class Migration(migrations.Migration):
    dependencies = [
        ('productos', '0025_catalogo_tecnico_extendido'),
    ]

    operations = [
        migrations.RunPython(asignar_imagenes, retirar_imagenes),
    ]
