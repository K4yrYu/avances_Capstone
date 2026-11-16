from django.db import migrations


SKU = 'SFI-TEC-TAP-WET-DYN-1KG'


def registrar_tapagoteras_wet(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Proveedor = apps.get_model('productos', 'Proveedor')
    proveedor = Proveedor.objects.filter(nombre='Proveedor General SFI', activo=True).first()
    Producto.objects.update_or_create(
        sku=SKU,
        defaults={
            'nombre': 'Tapagoteras Wet Dynal bajo lluvia 1 kg',
            'descripcion': (
                'Sello asfáltico negro listo para usar, formulado para sellar orificios, '
                'fisuras y grietas en techumbres. Puede aplicarse sobre superficies secas '
                'o húmedas, incluso bajo lluvia, siguiendo la ficha del fabricante.'
            ),
            'precio': 13990,
            'imagen': 'productos/Tapagoteras_Wet_Sella_Techos_Bajo_Lluvia_Dynal_1kg.webp',
            'stock': 6,
            'stock_minimo': 2,
            'categoria': 'Adhesivos',
            'marca': 'Dynal',
            'modelo': 'Tapagoteras Wet 1/4 GL',
            'color': 'Negro',
            'ambiente_uso': 'exterior',
            'superficies_compatibles': [
                'metal_galvanizado', 'fibrocemento', 'hormigon',
            ],
            'proveedor': proveedor,
            'unidad_venta': 'envase',
            'contenido': '1.000',
            'unidad_contenido': 'kg',
            'tipo_calculo': 'superficie',
            'rendimiento': '1.000',
            'unidad_rendimiento': 'm2_kg',
            'capas_recomendadas': 1,
            'porcentaje_desperdicio': '10.00',
            'uso_recomendado': (
                'Sellado puntual de orificios, fisuras y grietas en techumbres deterioradas '
                'y superficies compatibles, secas o húmedas.'
            ),
            'especificaciones': {
                'Tipo': 'Sello asfáltico en pasta',
                'Presentación': '1 kg / 1/4 galón',
                'Color': 'Negro',
                'Rendimiento declarado': '1 kg/m² en capa de 1 mm',
                'Aplicación': 'Espátula o herramienta similar',
                'Secado al tacto': '3 horas',
                'Secado total': '24 horas',
                'Advertencia': (
                    'Producto con solvente: mantener alejado de llamas y utilizar '
                    'ventilación y protección personal adecuada.'
                ),
                'Fuente técnica': 'Ficha técnica Tapagotera Wet, Dynal Industrial',
            },
            'informacion_tecnica_verificada': True,
            'activo': True,
        },
    )


def retirar_tapagoteras_wet(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.filter(sku=SKU).delete()


class Migration(migrations.Migration):
    dependencies = [('productos', '0053_asociar_imagenes_existentes_por_nombre')]

    operations = [
        migrations.RunPython(registrar_tapagoteras_wet, retirar_tapagoteras_wet),
    ]
