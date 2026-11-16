from django.db import migrations


IMAGENES_POR_SKU = {
    'SFI-SOL-MAQ-MMA200': 'productos/Soldadora_inverter_MMA_200_A_220_V.webp',
    'SFI-SOL-MAS-AUTO-DIN11': 'productos/Máscara_de_soldar_fotosensible_DIN_9_a_13.webp',
    'SFI-SOL-ELE-E6013-25-1KG': 'productos/Electrodo_E6013_25_mm_caja_1_kg.webp',
    'SFI-SOL-POR-300A': 'productos/Portaelectrodo_aislado_300_A.webp',
    'SFI-SOL-PIN-MAS-300A': 'productos/Pinza_de_masa_300_A_para_soldadura.webp',
    'SFI-SOL-GUA-CUERO-14': 'productos/Guantes_de_soldador_de_cuero_14_pulgadas.jpg',
    'SFI-SOL-DEL-CUERO-90': 'productos/Pechera_de_cuero_para_soldador_90_cm.png',
    'SFI-SOL-CEP-ACO-4': 'productos/Cepillo_manual_de_acero_4_hileras.webp',
    'SFI-JAR-MAC-PLA-25': 'productos/Macetero_plástico_redondo_terracota_25_cm.webp',
    'SFI-JAR-MAC-PLA-35': 'productos/Macetero_plástico_redondo_terracota_35_cm.webp',
    'SFI-JAR-MAC-REC-50': 'productos/Macetero_rectangular_plástico_grafito_50_x_20_x_18_cm.jpg',
    'SFI-JAR-MAC-CER-30': 'productos/Macetero_cerámico_esmaltado_30_cm.webp',
    'SFI-JAR-MAC-CEM-40': 'productos/Macetero_de_cemento_gris_40_cm.webp',
    'SFI-JAR-MAC-TEX-30': 'productos/Macetero_textil_geotextil_30_L_con_asas.webp',
    'SFI-JAR-PLA-MAC-30': 'productos/Plato_recolector_para_macetero_30_cm_terracota.jpg',
    'SFI-JAR-PIC-2500': 'productos/Picota_jardinera_acero_25_kg_mango_fibra.jpg',
    'SFI-JAR-CAR-90L': 'productos/Carretilla_acero_90_L_rueda_neumática.jpg',
    'SFI-JAR-AZA-120': 'productos/Azadón_acero_120_mm_mango_madera.webp',
    'SFI-JAR-RAS-14': 'productos/Rastrillo_metálico_14_dientes_mango_madera.jpg',
    'SFI-JAR-GUA-NIT-M': 'productos/Guantes_de_jardinería_nitrilo_talla_M.jpg',
}


def asociar_imagenes(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    for sku, ruta in IMAGENES_POR_SKU.items():
        Producto.objects.filter(sku=sku, imagen='').update(imagen=ruta)


def retirar_asociaciones(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    for sku, ruta in IMAGENES_POR_SKU.items():
        Producto.objects.filter(sku=sku, imagen=ruta).update(imagen='')


class Migration(migrations.Migration):
    dependencies = [
        ('productos', '0034_herramientas_jardineria_movimiento_tierra'),
    ]

    operations = [
        migrations.RunPython(asociar_imagenes, retirar_asociaciones),
    ]
