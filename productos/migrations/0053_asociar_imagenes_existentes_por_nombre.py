import re
import unicodedata
from pathlib import Path

from django.conf import settings
from django.db import migrations


EXTENSIONES_VALIDAS = {'.jpg', '.jpeg', '.png', '.webp'}
PRIORIDAD_EXTENSION = {'.webp': 0, '.jpg': 1, '.jpeg': 2, '.png': 3}


def _clave_nombre(valor):
    texto = unicodedata.normalize('NFKD', str(valor or ''))
    texto = ''.join(caracter for caracter in texto if not unicodedata.combining(caracter))
    return re.sub(r'[^a-z0-9]+', '', texto.casefold())


def asociar_imagenes_existentes(apps, schema_editor):
    """Enlaza archivos versionados sin reemplazar elecciones manuales."""
    Producto = apps.get_model('productos', 'Producto')
    carpeta_productos = Path(settings.MEDIA_ROOT) / 'productos'
    if not carpeta_productos.exists():
        return

    archivos_por_nombre = {}
    for archivo in carpeta_productos.rglob('*'):
        if not archivo.is_file() or archivo.suffix.casefold() not in EXTENSIONES_VALIDAS:
            continue
        archivos_por_nombre.setdefault(_clave_nombre(archivo.stem), []).append(archivo)

    for producto in Producto.objects.filter(imagen='').iterator():
        candidatos = archivos_por_nombre.get(_clave_nombre(producto.nombre), [])
        if not candidatos:
            continue
        elegido = sorted(
            candidatos,
            key=lambda archivo: (
                PRIORIDAD_EXTENSION.get(archivo.suffix.casefold(), 99),
                archivo.as_posix().casefold(),
            ),
        )[0]
        ruta_relativa = elegido.relative_to(settings.MEDIA_ROOT).as_posix()
        Producto.objects.filter(pk=producto.pk, imagen='').update(imagen=ruta_relativa)


class Migration(migrations.Migration):
    dependencies = [('productos', '0052_renombrar_maquina_soldar')]

    operations = [
        migrations.RunPython(asociar_imagenes_existentes, migrations.RunPython.noop),
    ]
