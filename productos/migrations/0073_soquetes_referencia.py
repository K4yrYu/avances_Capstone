from django.db import migrations


def agregar_soquetes(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    referencias = (
        {
            'sku': 'SFI-REF-SOQ-CER-E27',
            'nombre': 'Soquete portalámpara cerámica base recta E27 blanco',
            'descripcion': 'Portalámpara de cerámica blanco, con base recta y rosca E27.',
            'imagen': 'productos/soquete_halux_ceramica_e27.jpg',
            'precio': 2190,
            'fuente': 'https://www.sodimac.cl/sodimac-cl/articulo/110217743/Portalampara-ceramica-base-recta-blanco/110217746',
        },
        {
            'sku': 'SFI-REF-SOQ-PLA-E27',
            'nombre': 'Soquete portalámpara plástico presión E27 blanco',
            'descripcion': 'Portalámpara de plástico blanco de presión, compatible con ampolletas E27.',
            'imagen': 'productos/soquete_halux_plastico_e27.jpg',
            'precio': 1790,
            'fuente': 'https://www.sodimac.cl/sodimac-cl/articulo/110239785/Portalampara-plastico-presion-blanco/110239795',
        },
    )
    for referencia in referencias:
        datos = dict(referencia)
        sku = datos.pop('sku')
        fuente = datos.pop('fuente')
        Producto.objects.get_or_create(sku=sku, defaults={
            **datos,
            'stock': 0,
            'activo': False,
            'categoria': 'Iluminación',
            'marca': 'Halux',
            'unidad_venta': 'unidad',
            'contenido': '1.000',
            'unidad_contenido': 'unidad',
            'uso_recomendado': 'Sostener una ampolleta de rosca E27 compatible en un portalámpara apropiado.',
            'especificaciones': {
                'Rosca': 'E27',
                'Color': 'Blanco',
                'Fuente de referencia': fuente,
                'Estado': 'Referencia: precio y stock de SFI pendientes de confirmar.',
                'Seguridad': 'Verificar límites eléctricos, certificación y compatibilidad antes de usar.',
            },
            'informacion_tecnica_verificada': False,
            'tipo_calculo': 'ninguno',
        })


class Migration(migrations.Migration):
    dependencies = [('productos', '0072_imagenes_adaptadores_de_enchufe')]
    operations = [migrations.RunPython(agregar_soquetes, migrations.RunPython.noop)]
