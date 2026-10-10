from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator

class Usuario(AbstractUser):
    class Rol(models.TextChoices):
        CLIENTE = 'cliente', 'Cliente'
        REPARTIDOR = 'repartidor', 'Repartidor'
        RETIROS = 'retiros', 'Encargado de retiros'
        ADMINISTRADOR = 'administrador', 'Administrador'
    # Heredamos de AbstractUser que ya tiene campos como username, first_name, last_name, email, password, etc.
    
    email = models.EmailField(unique=True)
    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.CLIENTE)

    # Añadimos campos adicionales
    rut = models.CharField(
        max_length=12,
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^\d{7,8}-[\dkK]$',
                message='El RUT debe tener el formato 12345678-9'
            )
        ],
        verbose_name='RUT'
    )
    telefono = models.CharField(
        max_length=15,
        validators=[
            RegexValidator(
                regex=r'^\+?\d{9,15}$',
                message='El teléfono debe tener entre 9 y 15 dígitos'
            )
        ],
        verbose_name='Teléfono'
    )

    email_confirmado = models.BooleanField(default=False)  # 👈 Campo nuevo para verificación de correo
    correo_activacion_enviado_en = models.DateTimeField(null=True, blank=True)
    activacion_expira_en = models.DateTimeField(null=True, blank=True)
    
    # Campos requeridos
    REQUIRED_FIELDS = ['rut', 'email', 'telefono']

    def save(self, *args, **kwargs):
        if self._state.adding and (self.is_staff or self.is_superuser):
            self.rol = self.Rol.ADMINISTRADOR
        if self.rol == self.Rol.ADMINISTRADOR:
            self.is_staff = True
        elif not self.is_superuser:
            self.is_staff = False
        if kwargs.get('update_fields') and 'rol' in kwargs['update_fields']:
            kwargs['update_fields'] = set(kwargs['update_fields']) | {'is_staff'}
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.rut})"

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
