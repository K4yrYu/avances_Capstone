from django.db import migrations


IMAGENES = {
    'COR-CNAWHAG15QV': 'productos/Cerámica_muro_Natural_White_blanca_brillante_30_x_59_cm.png',
    'COR-HARMONY-BEIGE-27X45': 'productos/Cerámica_muro_Harmony_beige_27_x_45_cm_caja_170_m².jpg',
    'COR-HARMONY-GRIS-27X45': 'productos/Cerámica_muro_Harmony_gris_27_x_45_cm_caja_170_m².png',
    'COR-IAGADCP14KC': 'productos/Cerámica_Agadir_azul_geométrica_45_x_45_cm.webp',
    'COR-ICEMGCO16DI': 'productos/Cerámica_muro_Cemento_G8_Plata_30_x_60_cm.png',
    'COR-ICEMGCP16BE': 'productos/Cerámica_muro_Cemento_G8_Taupe_30_x_60_cm.png',
    'COR-ICEMPCP14KI': 'productos/Cerámica-Cemento-G8-Antislip-gris-45-x-45-cm-caja-2_08-m².jpg',
    'COR-IINDICP16BN': 'productos/Cerámica_muro_Indigo_beige_mármol_30_x_60_cm.jpg',
    'COR-IVEANCP14KV': 'productos/Cerámica_Venice_Antislip_blanca_45_x_45_cm.png',
    'COR-MAIRENA-BEIGE-45': 'productos/Cerámica_Mairena_beige_antideslizante_45_x_45_cm_caja_208_m².jpg',
    'COR-MAIRENA-OXIDO-45': 'productos/Cerámica_Mairena_óxido_antideslizante_45_x_45_cm_caja_208_m².jpg',
    'COR-SOLANA-BEIGE-45': 'productos/Cerámica_Solana_beige_antideslizante_45_x_45_cm_caja_208_m².png',
    'COR-VENETO-GRIS-45': 'productos/Cerámica_Veneto_gris_antideslizante_45_x_45_cm_caja_208_m².jpg',
    'DVP-3012110001800': 'productos/Cinta_de_aluminio_DVP_25_mm_gris_10_m_para_policarbonato.webp',
    'DVP-3012110003800': 'productos/Cinta_Filter_Tape_DVP_25_mm_gris_11_m.webp',
    'IKO-CAMBRIDGE-4221029': 'productos/teja-asfaltica-cafe-3-1m2-1x1-1-768x768.webp',
    'SFI-ADH-AFX-PIN-500': 'productos/Cola_fría_Afix_madera_pintable_500_g.png',
    'SFI-ADH-AGO-CON-118': 'productos/Adhesivo_de_contacto_Agorex_1-32_galon.webp',
    'SFI-ADH-AGO-PRO-1000': 'productos/Agorex_Profesional_cola_fría_extra_rápida_1_kg.png',
    'SFI-ADH-ECC-9': 'productos/Adhesivo_transparente_Éccole_para_calzado_9_g.png',
    'SFI-ADH-GOT-GEL-3': 'productos/Adhesivo_instantáneo_La_Gotita_Gel_3_g.png',
    'SFI-ADH-GOT-LIQ-2': 'productos/Adhesivo_instantáneo_La_Gotita_líquido_2_ml.webp',
    'SFI-ADH-POX-MET-14': 'productos/Adhesivo_epóxico_Poxipol_metálico_10_minutos_14_ml.webp',
    'SFI-ADH-POXIL-70': 'productos/Masilla_epóxica_Poxilina_10_minutos_70_g.webp',
    'SFI-ADH-PUL-MON-50': 'productos/Adhesivo_de_montaje_El_Pulpito_50_g.webp',
    'SFI-ADH-SIK-232-500': 'productos/SikaBond-232_cola_fría_profesional_para_madera_500_g.webp',
    'SFI-ADH-WAL-MAD-250': 'productos/Adhesivo_cola_fría_para_madera_Waltek_250_g.webp',
    'SFI-PFL-BONN-300': 'productos/Piso_laminado_Bonn_Café_AC3_6_mm_caja_300_m².png',
    'SFI-PFL-DANUBE-190': 'productos/Piso_fotolaminado_River_Danube_AC4_8_mm_caja_190_m².webp',
    'SFI-PFL-ESSEN-296': 'productos/Piso_laminado_Essen_Café_Claro_AC3_6_mm_caja_296_m².png',
    'SFI-PFL-EVOKE-244': 'productos/Piso_flotante_Evoke_Concrete_AC4_8_mm_caja_244_m².png',
    'SFI-PFL-GANGES-190': 'productos/Piso_fotolaminado_River_Ganges_AC4_8_mm_caja_190_m²_5i1A9l8.webp',
    'SFI-PFL-GRAFITO-244': 'productos/Piso_flotante_Roble_Grafito_AC4_8_mm_caja_244_m².webp',
    'SFI-PFL-KIT-INST': 'productos/Kit_de_instalación_para_piso_laminado.png',
    'SFI-PFL-KRONOTEX-213': 'productos/Piso_flotante_Kronotex_Roble_Marrón_AC4_8_mm_caja_213_m².png',
    'SFI-PFL-MARENGO-244': 'productos/Piso_flotante_Gris_Marengo_AC4_8_mm_caja_244_m².png',
    'SFI-PFL-MISTY-238': 'productos/Piso_laminado_Misty_Gris_AC3_7_mm_caja_238_m².png',
    'SFI-PFL-PER-T-200': 'productos/Perfil_T_níquel_mate_20_x_8_mm_x_2_m.webp',
    'SFI-PFL-VAP-AQUA-40': 'productos/Barrera_de_vapor_polietileno_Aquastop_rollo_40_m².webp',
    'SFI-PFL-WALNUT-244': 'productos/Piso_flotante_Walnut_AC4_8_mm_caja_244_m².webp',
    'SFI-TEC-CLA-TER-1KG': 'productos/Clavo_terrano_para_teja_asfaltica_1_pulgada_bolsa_1_kg.png',
}


def asociar_imagenes(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    for sku, imagen in IMAGENES.items():
        Producto.objects.filter(sku=sku).update(imagen=imagen)


def retirar_asociaciones(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    for sku, imagen in IMAGENES.items():
        Producto.objects.filter(sku=sku, imagen=imagen).update(imagen='')


class Migration(migrations.Migration):
    dependencies = [
        ('productos', '0067_categoria_ceramicas'),
    ]

    operations = [
        migrations.RunPython(asociar_imagenes, retirar_asociaciones),
    ]
