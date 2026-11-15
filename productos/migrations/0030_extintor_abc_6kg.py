from django.db import migrations


SKU_EXTINTOR = 'SFI-SEG-EXT-ABC6'


def agregar_extintor(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Proveedor = apps.get_model('productos', 'Proveedor')
    proveedor = Proveedor.objects.filter(
        nombre='Proveedor General SFI',
        activo=True,
    ).first()

    uso = (
        'Protección inicial frente a principios de incendio de clases A, B y C '
        'en viviendas, talleres, bodegas y zonas de quincho. Debe permanecer '
        'señalizado, accesible y con sus mantenciones vigentes.'
    )
    Producto.objects.update_or_create(
        sku=SKU_EXTINTOR,
        defaults={
            'nombre': 'Extintor ABC de polvo químico seco 6 kg',
            'descripcion': (
                'Extintor portátil multipropósito con 6 kg de polvo químico '
                'seco para respuesta inicial ante fuegos clase A, B y C. '
                'Incluye manómetro, manguera de descarga y soporte mural.'
            ),
            'precio': 49990,
            'imagen': '',
            'stock': 20,
            'stock_minimo': 5,
            'controla_vencimiento': False,
            'categoria': 'Seguridad',
            'activo': True,
            'marca': 'Genérico SFI',
            'modelo': 'ABC-PQS-6KG',
            'ambiente_uso': 'interior_exterior',
            'proveedor_id': proveedor.pk if proveedor else None,
            'unidad_venta': 'unidad',
            'contenido': '1.000',
            'unidad_contenido': 'unidad',
            'tipo_calculo': 'unidad',
            'rendimiento': None,
            'unidad_rendimiento': '',
            'porcentaje_desperdicio': '0.00',
            'uso_recomendado': uso,
            'especificaciones': {
                'Agente extintor': 'Polvo químico seco multipropósito ABC',
                'Carga nominal': '6 kg',
                'Clases de fuego': 'A, B y C',
                'Accionamiento': 'Manual',
                'Control de presión': 'Manómetro visible',
                'Descarga': 'Manguera flexible',
                'Instalación': 'Soporte mural en ubicación señalizada y accesible',
                'Mantención': 'Revisar presión, sello y vigencia según la etiqueta del equipo',
                'Advertencia': (
                    'Uso inicial únicamente; evacuar y contactar a Bomberos '
                    'si el fuego no puede controlarse de forma segura.'
                ),
                'Verificación pendiente': (
                    'Confirmar certificación, presión, alcance y tiempo de '
                    'descarga en la ficha oficial del fabricante antes de publicar.'
                ),
            },
            'informacion_tecnica_verificada': False,
        },
    )


def retirar_extintor(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.filter(sku=SKU_EXTINTOR).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('productos', '0029_catalogo_proyectos_faltantes'),
    ]

    operations = [
        migrations.RunPython(agregar_extintor, retirar_extintor),
    ]
