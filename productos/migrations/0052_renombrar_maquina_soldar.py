from django.db import migrations


SKU_SOLDADORA = 'SFI-SOL-MAQ-MMA200'
NOMBRE_ANTERIOR = 'Soldadora inverter MMA 200 A 220 V'
NOMBRE_NUEVO = 'Máquina de soldar inverter MMA 200 A 220 V'


def renombrar_maquina_soldar(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.filter(sku=SKU_SOLDADORA).update(nombre=NOMBRE_NUEVO)


def restaurar_nombre_soldadora(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.filter(sku=SKU_SOLDADORA).update(nombre=NOMBRE_ANTERIOR)


class Migration(migrations.Migration):
    dependencies = [('productos', '0051_tope_mecanico_porton')]

    operations = [
        migrations.RunPython(renombrar_maquina_soldar, restaurar_nombre_soldadora),
    ]
