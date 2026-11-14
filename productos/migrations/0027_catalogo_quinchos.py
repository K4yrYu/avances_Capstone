from django.db import migrations


PRODUCTOS_QUINCHO = [
    dict(sku='TEST-QNC-RAD-MAL-C92', nombre='Malla ACMA C-92 2,60 x 5 m', precio=39990, stock=28, categoria='Construcción', contenido='13.000', unidad='m2', calculo='superficie', rendimiento='13.000', medida='2,60 x 5 m; superficie 13 m²', uso='Refuerzo de radieres de hormigón según diseño y condición del terreno.'),
    dict(sku='TEST-QNC-RAD-POL-100', nombre='Polietileno construcción 200 micras 4 x 25 m', precio=44990, stock=18, categoria='Construcción', contenido='100.000', unidad='m2', calculo='superficie', rendimiento='100.000', medida='Espesor 200 micras; rollo 4 x 25 m', uso='Barrera bajo radier sobre una base preparada, con traslapes definidos por el proyecto.'),
    dict(sku='TEST-QNC-RAD-BAS-25', nombre='Base estabilizada para radier saco 25 kg', precio=3990, stock=160, categoria='Construcción', contenido='25.000', unidad='kg', calculo='peso', medida='Saco 25 kg', uso='Preparación y compactación de la base bajo radieres y pavimentos.'),
    dict(sku='TEST-QNC-ALB-MOR-25', nombre='Mortero pega ladrillos saco 25 kg', precio=5990, stock=130, categoria='Construcción', contenido='25.000', unidad='kg', calculo='superficie', rendimiento='1.500', medida='Saco 25 kg; rendimiento referencial 1,5 m²', uso='Asentado de ladrillos de albañilería compatibles sobre una base adecuada.'),
    dict(sku='TEST-QNC-FOG-LAD-REF', nombre='Ladrillo refractario 23 x 11 x 3 cm', precio=1890, stock=420, categoria='Construcción', contenido='1.000', unidad='unidad', calculo='unidad', medida='23 x 11 x 3 cm', uso='Revestimiento interior de sectores de fuego diseñados para material refractario.'),
    dict(sku='TEST-QNC-FOG-MOR-05', nombre='Mortero refractario balde 5 kg', precio=12990, stock=45, categoria='Adhesivos', contenido='5.000', unidad='kg', calculo='peso', medida='Balde 5 kg', uso='Unión de ladrillos refractarios en zonas de fuego compatibles.'),
    dict(sku='TEST-QNC-MET-TUB-8060', nombre='Perfil tubular acero 80 x 80 x 3 mm x 6 m', precio=54990, stock=24, categoria='Construcción', contenido='6.000', unidad='m', calculo='longitud', medida='80 x 80 x 3 mm; largo 6 m', uso='Pilares o estructura metálica únicamente según cálculo y protección anticorrosiva.'),
    dict(sku='TEST-QNC-MET-COS-100', nombre='Perfil costanera acero 100 x 50 x 2 mm x 6 m', precio=32990, stock=32, categoria='Construcción', contenido='6.000', unidad='m', calculo='longitud', medida='100 x 50 x 2 mm; largo 6 m', uso='Costaneras de cubierta según cálculo estructural y separación de apoyos.'),
    dict(sku='TEST-QNC-MET-ELE-1K', nombre='Electrodo soldadura E6013 2,5 mm caja 1 kg', precio=6990, stock=55, categoria='Ferretería', contenido='1.000', unidad='kg', calculo='unidad', medida='Diámetro 2,5 mm; caja 1 kg', uso='Soldadura de acero compatible realizada con procedimiento y protección adecuados.'),
    dict(sku='TEST-QNC-MET-ANC-M12', nombre='Perno anclaje expansión M12 x 120 mm pack 4', precio=8990, stock=70, categoria='Ferretería', contenido='4.000', unidad='unidad', calculo='unidad', medida='M12 x 120 mm; pack 4 unidades', uso='Anclaje de placas metálicas a hormigón cuando el diseño lo autorice.'),
    dict(sku='TEST-QNC-CIE-FIB-08', nombre='Plancha fibrocemento exterior 8 mm 1,20 x 2,40 m', precio=24990, stock=38, categoria='Construcción', contenido='2.880', unidad='m2', calculo='superficie', rendimiento='2.880', medida='8 mm; 1,20 x 2,40 m', uso='Cielos o revestimientos exteriores protegidos con estructura y fijaciones compatibles.'),
    dict(sku='TEST-QNC-TER-BAL-144', nombre='Baldosa exterior antideslizante 40 x 40 cm caja 1,44 m²', precio=23990, stock=44, categoria='Construcción', contenido='1.440', unidad='m2', calculo='superficie', rendimiento='1.440', medida='Palmeta 40 x 40 cm; caja 1,44 m²', uso='Terminación de pisos exteriores sobre una base firme, nivelada y preparada.'),
]


def cargar_productos_quincho(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    for registro in PRODUCTOS_QUINCHO:
        datos = dict(registro)
        sku = datos.pop('sku')
        medida = datos.pop('medida')
        uso = datos.pop('uso')
        unidad = datos.pop('unidad')
        calculo = datos.pop('calculo')
        rendimiento = datos.pop('rendimiento', None)
        Producto.objects.update_or_create(sku=sku, defaults={
            **datos,
            'descripcion': uso,
            'imagen': '',
            'stock_minimo': 5,
            'marca': 'Genérico SFI',
            'activo': True,
            'unidad_venta': 'unidad',
            'unidad_contenido': unidad,
            'tipo_calculo': calculo,
            'rendimiento': rendimiento,
            'unidad_rendimiento': 'm2_unidad' if calculo == 'superficie' else '',
            'porcentaje_desperdicio': '10.00' if calculo == 'superficie' else '0.00',
            'uso_recomendado': uso,
            'especificaciones': {
                'Medidas o presentación': medida,
                'Uso en proyecto': uso,
                'Origen del registro': 'Catálogo de prueba para quinchos SFI 13-11-2026',
            },
            'informacion_tecnica_verificada': True,
        })


def retirar_productos_quincho(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.filter(sku__startswith='TEST-QNC-').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('productos', '0026_imagenes_catalogo_extendido'),
    ]

    operations = [
        migrations.RunPython(cargar_productos_quincho, retirar_productos_quincho),
    ]
