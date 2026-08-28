from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinLengthValidator
from django.db import models
from django.utils import timezone

from .chile import REGIONES_CHOICES
from .presentacion import avatar_maestro_url, imagen_proyecto_url


MAX_IMAGENES_POR_TRABAJO = 10
MAX_TAMANO_IMAGEN = 5 * 1024 * 1024


def validar_fecha_trabajo(value):
    hoy = timezone.localdate()
    if value > hoy:
        raise ValidationError("La fecha del trabajo no puede estar en el futuro.")
    if value.year < hoy.year - 60:
        raise ValidationError("La fecha del trabajo es demasiado antigua para un portafolio profesional.")


class Especialidad(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ("nombre",)
        verbose_name = "Especialidad"
        verbose_name_plural = "Especialidades"

    def __str__(self):
        return self.nombre


class PerfilMaestro(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = "BORRADOR", "Borrador"
        PENDIENTE = "PENDIENTE", "Pendiente"
        APROBADO = "APROBADO", "Aprobado"
        RECHAZADO = "RECHAZADO", "Rechazado"
        SUSPENDIDO = "SUSPENDIDO", "Suspendido"

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="perfil_maestro",
    )
    foto = models.ImageField(upload_to="maestros/perfiles/", blank=True, null=True)
    descripcion_profesional = models.TextField()
    anos_experiencia = models.PositiveSmallIntegerField(
        default=0,
        validators=[MaxValueValidator(80)],
        verbose_name="años de experiencia",
    )
    especialidades = models.ManyToManyField(Especialidad, related_name="maestros")
    region = models.CharField(max_length=2, choices=REGIONES_CHOICES, default="RM")
    comuna = models.CharField(max_length=100)
    zonas_trabajo = models.TextField(blank=True, verbose_name="comunas o zonas de trabajo")
    disponible = models.BooleanField(default=True)
    estado = models.CharField(
        max_length=12,
        choices=Estado.choices,
        default=Estado.BORRADOR,
        db_index=True,
    )
    observacion_admin = models.TextField(blank=True)
    fecha_aprobacion = models.DateTimeField(blank=True, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-fecha_aprobacion", "usuario__first_name", "usuario__username")
        verbose_name = "Perfil de maestro"
        verbose_name_plural = "Perfiles de maestros"

    def __str__(self):
        return f"{self.usuario.get_full_name() or self.usuario.username} - {self.get_estado_display()}"

    @property
    def es_publico(self):
        return self.estado == self.Estado.APROBADO

    @property
    def foto_fallback_url(self):
        return avatar_maestro_url()

    @property
    def foto_publica_url(self):
        if self.foto and self.foto.name:
            try:
                return self.foto.url
            except ValueError:
                pass
        return self.foto_fallback_url

    def cambiar_estado(self, nuevo_estado):
        estados_admin = {
            self.Estado.APROBADO,
            self.Estado.RECHAZADO,
            self.Estado.SUSPENDIDO,
        }
        if nuevo_estado not in estados_admin:
            raise ValueError("Estado administrativo no válido.")
        self.estado = nuevo_estado
        self.fecha_aprobacion = timezone.now() if nuevo_estado == self.Estado.APROBADO else None
        self.save(update_fields=["estado", "fecha_aprobacion", "actualizado_en"])

    def volver_a_revision_por_edicion(self):
        """Un cambio profesional invalida la aprobación anterior."""
        if self.estado != self.Estado.APROBADO:
            return False
        self.estado = self.Estado.PENDIENTE
        self.observacion_admin = ""
        self.fecha_aprobacion = None
        self.save(
            update_fields=[
                "estado",
                "observacion_admin",
                "fecha_aprobacion",
                "actualizado_en",
            ]
        )
        return True


class ApelacionMaestro(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        ACEPTADA = "ACEPTADA", "Aceptada"
        RECHAZADA = "RECHAZADA", "Rechazada"

    perfil = models.OneToOneField(
        PerfilMaestro,
        on_delete=models.CASCADE,
        related_name="apelacion",
    )
    mensaje = models.TextField(
        max_length=2000,
        validators=[MinLengthValidator(30)],
    )
    estado = models.CharField(
        max_length=10,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
        db_index=True,
    )
    enviada_en = models.DateTimeField(auto_now_add=True)
    resuelta_en = models.DateTimeField(blank=True, null=True)
    revisada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="apelaciones_maestro_revisadas",
    )
    observacion_admin = models.TextField(blank=True, max_length=2000)

    class Meta:
        ordering = ("-enviada_en",)
        verbose_name = "Apelación de maestro"
        verbose_name_plural = "Apelaciones de maestros"

    def __str__(self):
        return f"Apelación de {self.perfil.usuario.username} - {self.get_estado_display()}"

    def resolver(self, estado, administrador, observacion):
        if self.estado != self.Estado.PENDIENTE:
            raise ValueError("La apelación ya fue resuelta.")
        if estado not in {self.Estado.ACEPTADA, self.Estado.RECHAZADA}:
            raise ValueError("La resolución de la apelación no es válida.")
        self.estado = estado
        self.revisada_por = administrador
        self.observacion_admin = observacion
        self.resuelta_en = timezone.now()
        self.save(
            update_fields=[
                "estado",
                "revisada_por",
                "observacion_admin",
                "resuelta_en",
            ]
        )


class ObservacionMaestro(models.Model):
    class Tipo(models.TextChoices):
        HISTORICA = "HISTORICA", "Observación anterior"
        APROBACION = "APROBACION", "Aprobación"
        RECHAZO = "RECHAZO", "Rechazo"
        SUSPENSION = "SUSPENSION", "Suspensión"
        REACTIVACION = "REACTIVACION", "Reactivación"
        APELACION_RECHAZADA = "APELACION_RECHAZADA", "Apelación rechazada"

    perfil = models.ForeignKey(
        PerfilMaestro,
        on_delete=models.CASCADE,
        related_name="observaciones",
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    texto = models.TextField(max_length=2000, validators=[MinLengthValidator(10)])
    registrada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="observaciones_maestro_registradas",
    )
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-creada_en", "-id")
        verbose_name = "Observación de maestro"
        verbose_name_plural = "Observaciones de maestros"

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.perfil.usuario.username}"


class TrabajoRealizado(models.Model):
    maestro = models.ForeignKey(
        PerfilMaestro,
        on_delete=models.CASCADE,
        related_name="trabajos",
    )
    titulo = models.CharField(max_length=150)
    descripcion = models.TextField()
    especialidades = models.ManyToManyField(
        Especialidad,
        related_name="trabajos_realizados",
    )
    comuna = models.CharField(max_length=100)
    fecha = models.DateField(blank=True, null=True, validators=[validar_fecha_trabajo])
    publicado = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-fecha", "-creado_en")
        verbose_name = "Trabajo realizado"
        verbose_name_plural = "Trabajos realizados"

    def __str__(self):
        return self.titulo

    @property
    def imagen_fallback_url(self):
        nombres = self.especialidades.values_list("nombre", flat=True)
        return imagen_proyecto_url(nombres, self.titulo)

    @property
    def portada_publica_url(self):
        portada = self.imagenes.first()
        if portada and portada.imagen and portada.imagen.name:
            try:
                return portada.imagen.url
            except ValueError:
                pass
        return self.imagen_fallback_url


class ImagenTrabajoRealizado(models.Model):
    trabajo = models.ForeignKey(
        TrabajoRealizado,
        on_delete=models.CASCADE,
        related_name="imagenes",
    )
    imagen = models.ImageField(upload_to="maestros/trabajos/")
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("creada_en",)
        verbose_name = "Imagen de trabajo realizado"
        verbose_name_plural = "Imágenes de trabajos realizados"

    def __str__(self):
        return f"Imagen de {self.trabajo.titulo}"
