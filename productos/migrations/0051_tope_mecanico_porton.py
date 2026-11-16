from django.db import migrations


PRODUCTO_TOPE_PORTON = {
    'sku': 'SFI-PORT-TOP-MEC-01',
    'nombre': 'Tope mecánico para portón corredera con goma',
    'descripcion': (
        'Limita el recorrido de un portón corredera y amortigua el cierre al final del riel. '
        'Debe instalarse en una estructura y riel compatibles.'
    ),
    'precio': 12990,
    'stock': 24,
    'categoria': 'Ferretería',
    'uso_recomendado': (
        'Detener mecánicamente el desplazamiento final de portones correderos manuales '
        'o automatizados, como complemento del sistema de seguridad.'
    ),
    'especificaciones': {
        'Tipo': 'Tope mecánico de fin de recorrido',
        'Aplicación': 'Portón corredera',
        'Amortiguación': 'Goma de impacto',
        'Montaje': 'Sobre riel o estructura compatible según el sistema instalado',
        'Uso recomendado': 'Limitar el recorrido de apertura o cierre del portón',
        'Importante': 'No reemplaza la regulación de límites ni dispositivos de seguridad del motor.',
    },
}


def cargar_tope_porton(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Proveedor = apps.get_model('productos', 'Proveedor')
    proveedor = Proveedor.objects.filter(nombre='Proveedor General SFI', activo=True).first()
    Producto.objects.update_or_create(
        sku=PRODUCTO_TOPE_PORTON['sku'],
        defaults={
            'nombre': PRODUCTO_TOPE_PORTON['nombre'],
            'descripcion': PRODUCTO_TOPE_PORTON['descripcion'],
            'precio': PRODUCTO_TOPE_PORTON['precio'],
            'stock': PRODUCTO_TOPE_PORTON['stock'],
            'stock_minimo': 5,
            'categoria': PRODUCTO_TOPE_PORTON['categoria'],
            'marca': 'Genérico SFI',
            'modelo': PRODUCTO_TOPE_PORTON['sku'],
            'imagen': '',
            'activo': True,
            'ambiente_uso': 'exterior',
            'superficies_compatibles': [],
            'tipo_pintura': 'no_aplica',
            'terminacion': 'no_aplica',
            'propiedades_pintura': [],
            'preparaciones_recomendadas': [],
            'unidad_venta': 'unidad',
            'contenido': '1.000',
            'unidad_contenido': 'unidad',
            'tipo_calculo': 'unidad',
            'rendimiento': None,
            'unidad_rendimiento': '',
            'porcentaje_desperdicio': '0.00',
            'proveedor_id': proveedor.pk if proveedor else None,
            'uso_recomendado': PRODUCTO_TOPE_PORTON['uso_recomendado'],
            'especificaciones': PRODUCTO_TOPE_PORTON['especificaciones'],
            'informacion_tecnica_verificada': True,
        },
    )


def retirar_tope_porton(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.filter(sku=PRODUCTO_TOPE_PORTON['sku']).delete()


class Migration(migrations.Migration):
    dependencies = [('productos', '0050_componentes_riego_por_goteo')]

    operations = [
        migrations.RunPython(cargar_tope_porton, retirar_tope_porton),
    ]
