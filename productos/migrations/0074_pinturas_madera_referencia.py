from django.db import migrations


def agregar_referencias(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    referencias = (
        ('SFI-REF-PIN-KOL-STD-MAT', 'Esmalte al agua KOLOR Standard interior mate blanco 1 galón', 'blanco', 'mate', 'interior', 'pintura_kolor_standard_mate_blanco.jpg', 'https://www.sodimac.cl/sodimac-cl/articulo/115579159/esmalte-al-agua-1-galones-mate-blanco/115579192'),
        ('SFI-REF-PIN-KOL-STD-SB', 'Esmalte al agua KOLOR Standard interior semibrillo blanco 1 galón', 'blanco', 'semibrillo', 'interior', 'pintura_kolor_standard_semibrillo_blanco.jpg', 'https://www.sodimac.cl/sodimac-cl/articulo/115578754/esmalte-al-agua-1-galones-semibrillante-blanco/115578786'),
        ('SFI-REF-PIN-KOL-PHO-SAT', 'Esmalte al agua KOLOR Photio interior satinado blanco 1 galón', 'blanco', 'satinado', 'interior', 'pintura_kolor_photio_satinado_blanco.jpg', 'https://www.sodimac.cl/sodimac-cl/articulo/140324994/esmalte-al-agua-para-interior-tecnologia-photio-1-galones-satinado-blanco/140324995'),
        ('SFI-REF-PIN-KOL-EXT-DEEP', 'Esmalte al agua KOLOR exterior mate base Deep 1 galón', '', 'mate', 'exterior', 'pintura_kolor_exterior_mate_base_deep.jpg', 'https://www.sodimac.cl/sodimac-cl/articulo/115579844/esmalte-al-agua-kolor-exterior-mate-base-deep-1-galon-antimoho/115579855'),
        ('SFI-REF-PIN-KOL-ANT-NAR', 'Pintura antimicrobiana KOLOR semibrillante naranjo Ulm 1 galón', 'naranjo ulm', 'semibrillo', 'interior', 'pintura_kolor_antimicrobiana_naranjo_ulm.jpg', 'https://www.falabella.com/falabella-cl/product/110575157/pintura-antimicrobiana-1-galones-semibrillante-naranjo-ulm/110575158'),
    )
    for sku, nombre, color, terminacion, ambiente, imagen, fuente in referencias:
        Producto.objects.get_or_create(sku=sku, defaults={
            'nombre': nombre,
            'descripcion': 'Pintura de referencia para madera preparada y otras superficies indicadas por el fabricante.',
            'precio': 1,
            'stock': 0,
            'activo': False,
            'categoria': 'Pinturas',
            'marca': 'KOLOR',
            'imagen': 'productos/' + imagen,
            'unidad_venta': 'unidad',
            'contenido': '3.785',
            'unidad_contenido': 'L',
            'color': color,
            'terminacion': terminacion,
            'tipo_pintura': 'esmalte_agua',
            'ambiente_uso': ambiente,
            'superficies_compatibles': ['madera'],
            'uso_recomendado': 'Pintar madera preparada en condiciones compatibles con la ficha del fabricante.',
            'especificaciones': {
                'Fuente de referencia': fuente,
                'Estado comercial': 'Referencia desactivada; precio y stock de SFI pendientes.',
                'Precio de 1 CLP': 'Marcador técnico obligatorio; no es precio de venta.',
                'Verificación pendiente': 'Confirmar ficha oficial, terminación, contenido, uso, rendimiento y certificaciones antes de activar.',
            },
            'informacion_tecnica_verificada': False,
            'tipo_calculo': 'ninguno',
        })


class Migration(migrations.Migration):
    dependencies = [('productos', '0073_soquetes_referencia')]
    operations = [migrations.RunPython(agregar_referencias, migrations.RunPython.noop)]
