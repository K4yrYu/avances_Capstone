from django.db import migrations


IMAGENES_POR_SKU = {
    'SFI-500-ELE-INT-SIM-10': 'productos/catalogo_guia/interruptor-simple-10a.jpg',
    'SFI-500-ELE-CIN-AIS-20': 'productos/catalogo_guia/cinta-aisladora-pvc.jpg',
    'SFI-500-ELE-EXT-10': 'productos/catalogo_guia/alargador-electrico-10m.jpg',
    'SFI-500-HER-CAL-60': 'productos/catalogo_guia/caladora-650w.jpg',
    'SFI-500-HER-BRO-JUE-5': 'productos/catalogo_guia/juego-brocas-concreto.jpg',
    'SFI-500-HER-PIS-CALOR': 'productos/catalogo_guia/pistola-calor-2000w.jpg',
    'SFI-500-HER-CRIM-TERM': 'productos/catalogo_guia/pinza-crimpeadora.jpg',
    'SFI-500-HER-PEL-CAB': 'productos/catalogo_guia/pelacables-automatico.jpg',
    'SFI-500-HER-PRO-VOL': 'productos/catalogo_guia/probador-voltaje-sin-contacto.jpg',
    'SFI-500-HER-MUL-DIG': 'productos/catalogo_guia/multimetro-digital.jpg',
}


def asignar_imagenes(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    for sku, ruta in IMAGENES_POR_SKU.items():
        Producto.objects.filter(sku=sku, imagen='').update(imagen=ruta)


def retirar_imagenes(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    for sku, ruta in IMAGENES_POR_SKU.items():
        Producto.objects.filter(sku=sku, imagen=ruta).update(imagen='')


class Migration(migrations.Migration):
    dependencies = [('productos', '0048_catalogo_proyectos_500')]

    operations = [migrations.RunPython(asignar_imagenes, retirar_imagenes)]
