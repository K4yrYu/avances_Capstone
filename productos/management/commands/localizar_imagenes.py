from io import BytesIO

import requests
from PIL import Image, ImageOps, UnidentifiedImageError
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from productos.models import Producto


PRODUCTOS_ADICIONALES = [
    {
        'nombre': 'Perno hexagonal métrico',
        'descripcion': 'Perno de acero para trabajos de construcción y montaje.',
        'precio': 5000,
        'imagen': 'https://europer.cl/wp-content/uploads/2020/07/B7-PERNOS-METRICO.jpg',
        'stock': 40,
        'categoria': 'Construcción',
        'activo': True,
    },
    {
        'nombre': 'Cinta métrica profesional 5 m',
        'descripcion': 'Cinta métrica retráctil para mediciones de hasta cinco metros.',
        'precio': 12990,
        'imagen': 'https://cdnx.jumpseller.com/my-toolbox-chile/image/42833863/d_nq_np_2x_820651-mlc40854154766_022020-f-8cff2697-107e-4579-baa7-b830d0424250.jpg?1732308296',
        'stock': 25,
        'categoria': 'Herramientas',
        'activo': True,
    },
    {
        'nombre': 'Madera de pino 2x3 pulgadas',
        'descripcion': 'Pieza de madera de pino dimensionada para construcción y terminaciones.',
        'precio': 5900,
        'imagen': 'https://media.falabella.com/sodimacCL/376256_01/w=800,h=800,fit=pad',
        'stock': 120,
        'categoria': 'Construcción',
        'activo': True,
    },
]


class Command(BaseCommand):
    help = 'Descarga imágenes URL, las normaliza y las guarda en media/productos.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--agregar-productos',
            action='store_true',
            help='Agrega el catálogo adicional antes de localizar las imágenes.',
        )

    def handle(self, *args, **options):
        if options['agregar_productos']:
            self._agregar_productos()

        errores = []
        convertidos = 0
        for producto in Producto.objects.order_by('id'):
            origen = str(producto.imagen or '').strip()
            if not origen.lower().startswith(('http://', 'https://')):
                continue
            try:
                contenido = self._descargar_y_normalizar(origen)
                nombre = f'producto-{producto.id}-{slugify(producto.nombre)[:60]}.jpg'
                producto.imagen.save(nombre, ContentFile(contenido), save=True)
                convertidos += 1
                self.stdout.write(self.style.SUCCESS(f'Imagen local: {producto.nombre}'))
            except Exception as exc:
                errores.append(f'{producto.id} - {producto.nombre}: {exc}')
                self.stderr.write(self.style.ERROR(errores[-1]))

        self.stdout.write(f'Imágenes convertidas: {convertidos}')
        if errores:
            raise CommandError('No fue posible convertir todas las imágenes:\n' + '\n'.join(errores))

    def _agregar_productos(self):
        for datos in PRODUCTOS_ADICIONALES:
            existente = Producto.objects.filter(nombre__iexact=datos['nombre']).first()
            if existente:
                self.stdout.write(f'Ya existe: {existente.nombre}')
                continue
            producto = Producto.objects.create(**datos)
            self.stdout.write(self.style.SUCCESS(f'Producto agregado: {producto.nombre}'))

    @staticmethod
    def _descargar_y_normalizar(url):
        response = requests.get(
            url,
            timeout=(10, 30),
            headers={'User-Agent': 'FERREMAS/1.0 catalog-image-migration'},
        )
        response.raise_for_status()
        if len(response.content) > 10 * 1024 * 1024:
            raise ValueError('el archivo supera los 10 MB')

        try:
            with Image.open(BytesIO(response.content)) as imagen:
                imagen.verify()
            with Image.open(BytesIO(response.content)) as imagen:
                imagen = ImageOps.exif_transpose(imagen)
                imagen.thumbnail((1600, 1600))
                if imagen.mode in {'RGBA', 'LA'}:
                    fondo = Image.new('RGB', imagen.size, 'white')
                    alpha = imagen.getchannel('A')
                    fondo.paste(imagen.convert('RGB'), mask=alpha)
                    imagen = fondo
                else:
                    imagen = imagen.convert('RGB')

                salida = BytesIO()
                imagen.save(salida, format='JPEG', quality=88, optimize=True)
                return salida.getvalue()
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError('la respuesta no contiene una imagen válida') from exc
