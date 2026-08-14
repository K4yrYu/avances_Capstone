from rest_framework import serializers
from PIL import Image, UnidentifiedImageError
from .models import Producto, HistorialPrecio

class ProductoSerializer(serializers.ModelSerializer):
    imagen = serializers.ImageField(required=False, allow_empty_file=False)

    class Meta:
        model = Producto
        fields = ['id', 'nombre', 'descripcion', 'precio', 'imagen', 'stock', 'categoria', 'activo']
        read_only_fields = ['id']

    def validate_precio(self, value):
        if value <= 0:
            raise serializers.ValidationError('El precio debe ser mayor que cero.')
        return value

    def validate_stock(self, value):
        if value < 0:
            raise serializers.ValidationError('El stock no puede ser negativo.')
        return value

    def validate_imagen(self, value):
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError('La imagen no puede superar los 5 MB.')
        try:
            with Image.open(value) as image:
                image_format = image.format
                width, height = image.size
                image.verify()
            value.seek(0)
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise serializers.ValidationError('El archivo no contiene una imagen válida.') from exc
        if image_format not in {'JPEG', 'PNG', 'WEBP'}:
            raise serializers.ValidationError('Solo se permiten imágenes JPG, PNG o WebP.')
        if width > 5000 or height > 5000:
            raise serializers.ValidationError('La imagen no puede superar 5000 × 5000 píxeles.')
        return value

    def validate(self, attrs):
        if self.instance is None and not attrs.get('imagen'):
            raise serializers.ValidationError({'imagen': 'Debes subir una imagen del producto.'})
        return attrs

class HistorialPrecioSerializer(serializers.ModelSerializer):
    class Meta:
        model = HistorialPrecio
        fields = '__all__'
