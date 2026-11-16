from django.db import migrations


PRODUCTOS_SOLDADURA = [
    {
        'sku': 'SFI-SOL-MAQ-MMA200',
        'nombre': 'Soldadora inverter MMA 200 A 220 V',
        'precio': 149990,
        'stock': 12,
        'stock_minimo': 3,
        'categoria': 'Herramientas',
        'modelo': 'MMA-200-SFI',
        'contenido': '1.000',
        'unidad_contenido': 'unidad',
        'unidad_venta': 'unidad',
        'tipo_calculo': 'unidad',
        'uso': (
            'Equipo para uniones por soldadura manual de arco con electrodo revestido '
            'en trabajos de acero compatibles. La conexión eléctrica y el procedimiento '
            'deben ser realizados por una persona capacitada.'
        ),
        'especificaciones': {
            'Proceso': 'MMA / electrodo revestido',
            'Alimentación declarada': '220 V monofásica',
            'Corriente máxima declarada': '200 A',
            'Rango de electrodo declarado': '1,6 a 4,0 mm',
            'Incluye': 'Portaelectrodo y pinza de masa según presentación',
        },
    },
    {
        'sku': 'SFI-SOL-MAS-AUTO-DIN11',
        'nombre': 'Máscara de soldar fotosensible DIN 9 a 13',
        'precio': 39990,
        'stock': 25,
        'stock_minimo': 5,
        'categoria': 'Seguridad',
        'modelo': 'AUTO-DIN9-13-SFI',
        'contenido': '1.000',
        'unidad_contenido': 'unidad',
        'unidad_venta': 'unidad',
        'tipo_calculo': 'unidad',
        'uso': (
            'Protección facial y visual durante la soldadura de arco. Debe ajustarse '
            'correctamente y utilizarse junto con los demás elementos de protección personal.'
        ),
        'especificaciones': {
            'Tipo de filtro declarado': 'Auto oscurecimiento',
            'Rango de sombra declarado': 'DIN 9 a 13',
            'Protección': 'Ojos y rostro frente a radiación y proyecciones de soldadura',
            'Ajuste': 'Arnés regulable',
        },
    },
    {
        'sku': 'SFI-SOL-ELE-E6013-25-1KG',
        'nombre': 'Electrodo E6013 2,5 mm caja 1 kg',
        'precio': 6990,
        'stock': 60,
        'stock_minimo': 10,
        'categoria': 'Ferretería',
        'modelo': 'E6013-25-1KG-SFI',
        'contenido': '1.000',
        'unidad_contenido': 'kg',
        'unidad_venta': 'caja',
        'tipo_calculo': 'peso',
        'uso': 'Consumible para realizar cordones de soldadura MMA en acero compatible.',
        'especificaciones': {
            'Clasificación declarada': 'E6013',
            'Diámetro declarado': '2,5 mm',
            'Presentación': 'Caja de 1 kg',
            'Aplicación': 'Soldadura manual de arco en acero compatible',
        },
    },
    {
        'sku': 'SFI-SOL-ELE-E7018-32-1KG',
        'nombre': 'Electrodo E7018 3,2 mm caja 1 kg',
        'precio': 8990,
        'stock': 45,
        'stock_minimo': 8,
        'categoria': 'Ferretería',
        'modelo': 'E7018-32-1KG-SFI',
        'contenido': '1.000',
        'unidad_contenido': 'kg',
        'unidad_venta': 'caja',
        'tipo_calculo': 'peso',
        'uso': 'Consumible para uniones de acero que requieran electrodo de bajo hidrógeno según el procedimiento definido.',
        'especificaciones': {
            'Clasificación declarada': 'E7018',
            'Diámetro declarado': '3,2 mm',
            'Presentación': 'Caja de 1 kg',
            'Almacenamiento': 'Mantener seco según indicaciones del fabricante',
        },
    },
    {
        'sku': 'SFI-SOL-POR-300A',
        'nombre': 'Portaelectrodo aislado 300 A',
        'precio': 8990,
        'stock': 30,
        'stock_minimo': 5,
        'categoria': 'Herramientas',
        'modelo': 'PORTA-300A-SFI',
        'contenido': '1.000',
        'unidad_contenido': 'unidad',
        'unidad_venta': 'unidad',
        'tipo_calculo': 'unidad',
        'uso': 'Sujeta el electrodo durante la soldadura manual de arco y permite su conexión al cable de trabajo.',
        'especificaciones': {
            'Capacidad declarada': '300 A',
            'Aislación': 'Mango aislado',
            'Uso': 'Equipos MMA compatibles',
        },
    },
    {
        'sku': 'SFI-SOL-PIN-MAS-300A',
        'nombre': 'Pinza de masa 300 A para soldadura',
        'precio': 5990,
        'stock': 35,
        'stock_minimo': 5,
        'categoria': 'Herramientas',
        'modelo': 'MASA-300A-SFI',
        'contenido': '1.000',
        'unidad_contenido': 'unidad',
        'unidad_venta': 'unidad',
        'tipo_calculo': 'unidad',
        'uso': 'Conecta el retorno eléctrico desde la pieza de trabajo al equipo de soldadura.',
        'especificaciones': {
            'Capacidad declarada': '300 A',
            'Uso': 'Retorno de corriente en equipos MMA compatibles',
            'Contacto': 'Mordaza metálica con resorte',
        },
    },
    {
        'sku': 'SFI-SOL-GUA-CUERO-14',
        'nombre': 'Guantes de soldador de cuero 14 pulgadas',
        'precio': 9990,
        'stock': 50,
        'stock_minimo': 8,
        'categoria': 'Seguridad',
        'modelo': 'GUA-SOL-14-SFI',
        'contenido': '1.000',
        'unidad_contenido': 'unidad',
        'unidad_venta': 'unidad',
        'tipo_calculo': 'unidad',
        'uso': 'Protegen las manos y parte del antebrazo frente a chispas y calor incidental durante trabajos de soldadura.',
        'especificaciones': {
            'Material declarado': 'Cuero',
            'Largo declarado': '14 pulgadas',
            'Presentación': 'Par',
            'Uso': 'Protección complementaria para soldadura',
        },
    },
    {
        'sku': 'SFI-SOL-DEL-CUERO-90',
        'nombre': 'Pechera de cuero para soldador 90 cm',
        'precio': 14990,
        'stock': 25,
        'stock_minimo': 5,
        'categoria': 'Seguridad',
        'modelo': 'DEL-SOL-90-SFI',
        'contenido': '1.000',
        'unidad_contenido': 'unidad',
        'unidad_venta': 'unidad',
        'tipo_calculo': 'unidad',
        'uso': 'Protección complementaria del torso frente a chispas y proyecciones durante la soldadura.',
        'especificaciones': {
            'Material declarado': 'Cuero',
            'Largo declarado': '90 cm',
            'Uso': 'Protección de torso para soldadura',
        },
    },
    {
        'sku': 'SFI-SOL-CEP-ACO-4',
        'nombre': 'Cepillo manual de acero 4 hileras',
        'precio': 3490,
        'stock': 70,
        'stock_minimo': 10,
        'categoria': 'Herramientas',
        'modelo': 'CEP-ACO-4-SFI',
        'contenido': '1.000',
        'unidad_contenido': 'unidad',
        'unidad_venta': 'unidad',
        'tipo_calculo': 'unidad',
        'uso': 'Limpia escoria, óxido superficial y residuos antes o después del cordón de soldadura.',
        'especificaciones': {
            'Cerdas declaradas': 'Acero',
            'Configuración declarada': '4 hileras',
            'Uso': 'Preparación y limpieza manual de superficies metálicas',
        },
    },
]


def cargar_catalogo_soldadura(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Proveedor = apps.get_model('productos', 'Proveedor')
    proveedor = Proveedor.objects.filter(
        nombre='Proveedor General SFI', activo=True,
    ).first()

    for registro in PRODUCTOS_SOLDADURA:
        datos = dict(registro)
        sku = datos.pop('sku')
        uso = datos.pop('uso')
        especificaciones = datos.pop('especificaciones')
        Producto.objects.update_or_create(
            sku=sku,
            defaults={
                **datos,
                'descripcion': uso,
                'imagen': '',
                'activo': True,
                'marca': 'Genérico SFI',
                'ambiente_uso': 'especial',
                'proveedor_id': proveedor.pk if proveedor else None,
                'rendimiento': None,
                'unidad_rendimiento': '',
                'porcentaje_desperdicio': '0.00',
                'uso_recomendado': uso,
                'especificaciones': {
                    **especificaciones,
                    'Estado de ficha': 'Datos de catálogo interno; validar con proveedor antes de compra técnica.',
                    'Seguridad': 'Usar protección personal adecuada y ventilación. Para estructuras o instalaciones eléctricas, consultar personal capacitado.',
                },
                'informacion_tecnica_verificada': False,
            },
        )


def retirar_catalogo_soldadura(apps, schema_editor):
    Producto = apps.get_model('productos', 'Producto')
    Producto.objects.filter(sku__startswith='SFI-SOL-').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('productos', '0031_imagen_extintor_abc_6kg'),
    ]

    operations = [
        migrations.RunPython(cargar_catalogo_soldadura, retirar_catalogo_soldadura),
    ]
