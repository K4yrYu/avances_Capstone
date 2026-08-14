from django.db import models
from django.core.validators import MinValueValidator
from django.db.models import Q

class Producto(models.Model):
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField()
    precio = models.IntegerField(validators=[MinValueValidator(1)])
    imagen = models.ImageField(upload_to='productos/', max_length=255)
    stock = models.PositiveIntegerField(default=0)
    categoria = models.CharField(max_length=100, default="General")
    activo = models.BooleanField(default=True)  # 🔹 nuevo campo

    def __str__(self):
        return self.nombre

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(precio__gt=0), name='producto_precio_positivo'),
            models.CheckConstraint(condition=Q(stock__gte=0), name='producto_stock_no_negativo'),
        ]

    
class HistorialPrecio(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='historial_precios')
    precio_anterior = models.IntegerField(validators=[MinValueValidator(1)])
    precio_nuevo = models.IntegerField(validators=[MinValueValidator(1)])
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.producto.nombre} | {self.precio_anterior} → {self.precio_nuevo}"
