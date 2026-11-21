from decimal import Decimal

from django.db import migrations


PRODUCTOS = (
    {
        "sku": "DVP-3012110003800",
        "nombre": "Cinta Filter Tape DVP 25 mm gris 11 m",
        "marca": "DVP",
        "modelo": "3012110003800",
        "precio": 20360,
        "stock": 35,
        "contenido": "11.000",
        "descripcion": (
            "Cinta ventilada para proteger el extremo inferior de planchas de "
            "policarbonato alveolar contra polvo e insectos, permitiendo evacuar "
            "condensacion."
        ),
        "uso_recomendado": (
            "Cierre inferior de alveolos en cubiertas de policarbonato; debe "
            "instalarse con el perfil de cierre compatible del sistema."
        ),
        "especificaciones": {
            "familia": "cierre ventilado para policarbonato alveolar",
            "posicion_instalacion": "extremo inferior de la plancha",
            "ancho_mm": 25,
            "largo_m": 11,
            "fuente_tecnica": "https://www.dvp.cl/policarbonatos/perfiles-y-accesorios/cinta-filter-tape-25mm-gris-11mts-3012110003800.html",
        },
    },
    {
        "sku": "DVP-3012110001800",
        "nombre": "Cinta de aluminio DVP 25 mm gris 10 m para policarbonato",
        "marca": "DVP",
        "modelo": "3012110001800",
        "precio": 2290,
        "stock": 40,
        "contenido": "10.000",
        "descripcion": (
            "Cinta de aluminio para sellar el extremo superior de planchas de "
            "policarbonato alveolar y evitar el ingreso de agua y suciedad."
        ),
        "uso_recomendado": (
            "Cierre superior de alveolos en cubiertas de policarbonato; debe "
            "instalarse con el perfil de cierre compatible del sistema."
        ),
        "especificaciones": {
            "familia": "cierre estanco para policarbonato alveolar",
            "posicion_instalacion": "extremo superior de la plancha",
            "ancho_mm": 25,
            "largo_m": 10,
            "fuente_tecnica": "https://www.dvp.cl/policarbonatos/perfiles-y-accesorios/cinta-aluminio-25mm-gris-10mts-3012110001800.html",
        },
    },
    {
        "sku": "SFI-TEC-CLA-TER-1KG",
        "nombre": "Clavo terrano para teja asfaltica 1 pulgada bolsa 1 kg",
        "marca": "Fixser",
        "modelo": "Clavo terrano 1 pulgada",
        "precio": 5990,
        "stock": 40,
        "contenido": "1.000",
        "unidad_contenido": "kg",
        "unidad_venta": "bolsa",
        "descripcion": (
            "Clavo galvanizado de cabeza ancha destinado a la fijacion de tejas "
            "asfalticas sobre una base apta para recibir clavado."
        ),
        "uso_recomendado": (
            "Fijacion mecanica de teja asfaltica siguiendo la cantidad, posicion y "
            "penetracion indicadas por el fabricante de la cubierta."
        ),
        "especificaciones": {
            "familia": "fijacion para teja asfaltica",
            "largo_pulgadas": 1,
            "acabado": "galvanizado",
            "fuente_tecnica": "https://www.sodimac.cl/sodimac-cl/articulo/110071934/Clavo-Terrano-1-Teja-Asfaltica-1-kg/110071935",
        },
    },
)


def crear_productos(apps, schema_editor):
    Producto = apps.get_model("productos", "Producto")
    for registro in PRODUCTOS:
        Producto.objects.update_or_create(
            sku=registro["sku"],
            defaults={
                "nombre": registro["nombre"],
                "descripcion": registro["descripcion"],
                "precio": registro["precio"],
                "imagen": "",
                "stock": registro["stock"],
                "stock_minimo": 5,
                "categoria": "Techumbre",
                "marca": registro["marca"],
                "modelo": registro["modelo"],
                "ambiente_uso": "exterior",
                "superficies_compatibles": ["techumbre"],
                "activo": True,
                "unidad_venta": registro.get("unidad_venta", "rollo"),
                "contenido": Decimal(registro["contenido"]),
                "unidad_contenido": registro.get("unidad_contenido", "m"),
                "tipo_calculo": "longitud" if registro.get("unidad_contenido", "m") == "m" else "ninguno",
                "rendimiento": Decimal(registro["contenido"]) if registro.get("unidad_contenido", "m") == "m" else None,
                "unidad_rendimiento": "m_unidad" if registro.get("unidad_contenido", "m") == "m" else "",
                "porcentaje_desperdicio": Decimal("0.00"),
                "uso_recomendado": registro["uso_recomendado"],
                "especificaciones": {
                    **registro["especificaciones"],
                    "fecha_consulta_fuente": "2026-11-20",
                },
                "informacion_tecnica_verificada": True,
            },
        )


def eliminar_productos(apps, schema_editor):
    Producto = apps.get_model("productos", "Producto")
    Producto.objects.filter(sku__in=[item["sku"] for item in PRODUCTOS]).delete()


class Migration(migrations.Migration):
    dependencies = [("productos", "0064_alternativas_adhesivos_madera")]

    operations = [migrations.RunPython(crear_productos, eliminar_productos)]
