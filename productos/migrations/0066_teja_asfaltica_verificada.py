from decimal import Decimal

from django.db import migrations


SKU = "IKO-CAMBRIDGE-4221029"


def crear_producto(apps, schema_editor):
    Producto = apps.get_model("productos", "Producto")
    Producto.objects.update_or_create(
        sku=SKU,
        defaults={
            "nombre": "Teja asfaltica laminada IKO Cambridge Cafe Tabaco paquete 3,10 m2",
            "descripcion": (
                "Teja asfaltica laminada de dos piezas, reforzada con fibra de "
                "vidrio y destinada a cubiertas inclinadas sobre un sistema base compatible."
            ),
            "precio": 34990,
            "imagen": "",
            "stock": 36,
            "stock_minimo": 5,
            "categoria": "Techumbre",
            "marca": "IKO",
            "modelo": "Cambridge 4221029",
            "ambiente_uso": "exterior",
            "superficies_compatibles": ["base continua para techumbre"],
            "activo": True,
            "unidad_venta": "paquete",
            "contenido": Decimal("3.100"),
            "unidad_contenido": "m2",
            "tipo_calculo": "superficie",
            "rendimiento": Decimal("3.100"),
            "unidad_rendimiento": "m2_unidad",
            "porcentaje_desperdicio": Decimal("10.00"),
            "uso_recomendado": (
                "Cubiertas inclinadas residenciales y construcciones livianas, con "
                "membrana base, inicio, cumbrera y fijaciones compatibles."
            ),
            "especificaciones": {
                "material": "asfalto reforzado con fibra de vidrio",
                "diseno": "laminado dimensional de dos piezas",
                "color": "cafe tabaco",
                "cobertura_paquete_m2": 3.1,
                "unidades_paquete": 20,
                "fuente_tecnica_fabricante": "https://www.iko.com/na/wp-content/uploads/2024/12/4220XXX_IKO_TDS_Cambridge_SP.pdf",
                "fuente_catalogo_chile": "https://www.triplee.cl/teja-asfaltica-doble-cafe-tabaco-iko-cambridge-18392.html",
                "fecha_consulta_fuente": "2026-11-20",
            },
            "informacion_tecnica_verificada": True,
        },
    )


def eliminar_producto(apps, schema_editor):
    Producto = apps.get_model("productos", "Producto")
    Producto.objects.filter(sku=SKU).delete()


class Migration(migrations.Migration):
    dependencies = [("productos", "0065_complementos_techumbre_estandar")]

    operations = [migrations.RunPython(crear_producto, eliminar_producto)]
