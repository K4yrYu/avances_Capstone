from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinLengthValidator
from django.db import models
from django.utils import timezone

from .chile import REGIONES_CHOICES
from .presentacion import avatar_maestro_url, imagen_proyecto_url
from .storage import documentos_privados_storage


MAX_IMAGENES_POR_TRABAJO = 10
MAX_TAMANO_IMAGEN = 5 * 1024 * 1024
MAX_TAMANO_DOCUMENTO = 5 * 1024 * 1024


def validar_archivo_documental(archivo):
    """Valida tamaño, extensión, MIME declarado y firma básica del archivo."""
    nombre = str(getattr(archivo, "name", "") or "").lower()
    extensiones = {
        ".pdf": ("application/pdf", (b"%PDF",)),
        ".jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
        ".jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
        ".png": ("image/png", (b"\x89PNG\r\n\x1a\n",)),
    }
    extension = next((item for item in extensiones if nombre.endswith(item)), "")
    if not extension:
        raise ValidationError("Solo se permiten archivos PDF, JPG, JPEG o PNG.")
    if getattr(archivo, "size", 0) > MAX_TAMANO_DOCUMENTO:
        raise ValidationError("El archivo debe pesar como máximo 5 MB.")

    mime_esperado, firmas = extensiones[extension]
    content_type = getattr(archivo, "content_type", "")
    if content_type and content_type != mime_esperado:
        raise ValidationError("El tipo de archivo no coincide con su extensión.")

    flujo = getattr(archivo, "file", archivo)
    posicion = None
    try:
        posicion = flujo.tell()
        cabecera = flujo.read(12)
        flujo.seek(posicion)
    except (AttributeError, OSError, ValueError):
        return
    if cabecera and not any(cabecera.startswith(firma) for firma in firmas):
        raise ValidationError("El contenido del archivo no corresponde a un formato permitido.")


def validar_fecha_trabajo(value):
    hoy = timezone.localdate()
    if value > hoy:
        raise ValidationError("La fecha del trabajo no puede estar en el futuro.")
    if value.year < hoy.year - 60:
        raise ValidationError("La fecha del trabajo es demasiado antigua para un portafolio profesional.")


class Especialidad(models.Model):
    class TipoLicencia(models.TextChoices):
        NINGUNA = "NINGUNA", "No requiere licencia"
        SEC_ELECTRICA = "SEC_ELECTRICA", "SEC eléctrica"
        SEC_GAS = "SEC_GAS", "SEC gas"

    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)
    activa = models.BooleanField(default=True)
    tipo_licencia = models.CharField(
        max_length=20,
        choices=TipoLicencia.choices,
        default=TipoLicencia.NINGUNA,
    )

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
        if nuevo_estado == self.Estado.APROBADO and not self.puede_ser_aprobado():
            detalle = " ".join(self.motivos_documentacion_pendiente())
            raise ValidationError(f"No se puede aprobar este maestro: {detalle}")
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

    def tipos_licencia_requeridos(self):
        return set(
            self.especialidades.exclude(
                tipo_licencia=Especialidad.TipoLicencia.NINGUNA
            ).values_list("tipo_licencia", flat=True)
        )

    def faltantes_para_envio(self):
        documentos = {documento.tipo: documento for documento in self.documentos.all()}
        faltantes = []
        for tipo, etiqueta in DocumentoMaestro.Tipo.choices:
            documento = documentos.get(tipo)
            if documento is None or not documento.archivo:
                faltantes.append(etiqueta)

        licencias = {licencia.tipo_licencia: licencia for licencia in self.licencias.all()}
        etiquetas = dict(Especialidad.TipoLicencia.choices)
        for tipo in sorted(self.tipos_licencia_requeridos()):
            licencia = licencias.get(tipo)
            if licencia is None or not licencia.archivo:
                faltantes.append(f"Licencia {etiquetas[tipo]}")
        return faltantes

    def documentos_obligatorios_completos(self):
        documentos = {documento.tipo: documento for documento in self.documentos.all()}
        return all(
            documentos.get(tipo)
            and documentos[tipo].estado_revision == DocumentoMaestro.EstadoRevision.VERIFICADO
            for tipo, _ in DocumentoMaestro.Tipo.choices
        )

    def licencias_obligatorias_completas(self):
        licencias = {licencia.tipo_licencia: licencia for licencia in self.licencias.all()}
        return all(
            licencias.get(tipo)
            and licencias[tipo].estado_revision == LicenciaMaestro.EstadoRevision.VERIFICADO
            for tipo in self.tipos_licencia_requeridos()
        )

    def documentacion_completa(self):
        return (
            self.documentos_obligatorios_completos()
            and self.licencias_obligatorias_completas()
        )

    def puede_ser_aprobado(self):
        return self.documentacion_completa()

    def motivos_documentacion_pendiente(self):
        motivos = []
        documentos = {documento.tipo: documento for documento in self.documentos.all()}
        for tipo, etiqueta in DocumentoMaestro.Tipo.choices:
            documento = documentos.get(tipo)
            if documento is None or not documento.archivo:
                motivos.append(f"Falta subir {etiqueta.lower()}.")
            elif documento.estado_revision == DocumentoMaestro.EstadoRevision.PENDIENTE:
                motivos.append(f"{etiqueta} pendiente de verificación.")
            elif documento.estado_revision == DocumentoMaestro.EstadoRevision.RECHAZADO:
                motivos.append(f"{etiqueta} rechazado.")

        licencias = {licencia.tipo_licencia: licencia for licencia in self.licencias.all()}
        etiquetas = dict(Especialidad.TipoLicencia.choices)
        for tipo in sorted(self.tipos_licencia_requeridos()):
            etiqueta = f"Licencia {etiquetas[tipo]}"
            licencia = licencias.get(tipo)
            if licencia is None or not licencia.archivo:
                motivos.append(f"Falta subir {etiqueta.lower()}.")
            elif licencia.estado_revision == LicenciaMaestro.EstadoRevision.PENDIENTE:
                motivos.append(f"{etiqueta} pendiente de verificación.")
            elif licencia.estado_revision == LicenciaMaestro.EstadoRevision.RECHAZADO:
                motivos.append(f"{etiqueta} rechazada.")
        return motivos

    def enviar_a_revision(self):
        if self.estado == self.Estado.SUSPENDIDO:
            raise ValidationError(
                "Un perfil suspendido debe ser habilitado por administración."
            )
        if self.estado not in {self.Estado.BORRADOR, self.Estado.RECHAZADO}:
            raise ValidationError(
                "Este perfil no necesita ser enviado nuevamente a revisión."
            )
        faltantes = self.faltantes_para_envio()
        if faltantes:
            raise ValidationError(
                "No puedes enviar tu perfil a revisión. Falta subir: "
                + "; ".join(faltantes)
                + "."
            )
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

    @property
    def tiene_licencia_sec_verificada(self):
        requeridas = self.tipos_licencia_requeridos()
        if not requeridas:
            return False
        verificadas = set(
            self.licencias.filter(
                tipo_licencia__in=requeridas,
                estado_revision=LicenciaMaestro.EstadoRevision.VERIFICADO,
            ).values_list("tipo_licencia", flat=True)
        )
        return requeridas.issubset(verificadas)


class EstadoRevisionDocumento(models.TextChoices):
    PENDIENTE = "PENDIENTE", "Pendiente"
    VERIFICADO = "VERIFICADO", "Verificado"
    RECHAZADO = "RECHAZADO", "Rechazado"


class DocumentoMaestro(models.Model):
    class Tipo(models.TextChoices):
        CEDULA = "CEDULA", "Cédula de identidad"
        ANTECEDENTES = "ANTECEDENTES", "Certificado de antecedentes"

    EstadoRevision = EstadoRevisionDocumento

    perfil = models.ForeignKey(
        PerfilMaestro,
        on_delete=models.CASCADE,
        related_name="documentos",
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    archivo = models.FileField(
        storage=documentos_privados_storage,
        upload_to="maestros/documentos/%Y/%m/",
        validators=[validar_archivo_documental],
    )
    estado_revision = models.CharField(
        max_length=12,
        choices=EstadoRevisionDocumento.choices,
        default=EstadoRevisionDocumento.PENDIENTE,
        db_index=True,
    )
    observacion_admin = models.TextField(blank=True, max_length=2000)
    subido_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    revisado_en = models.DateTimeField(blank=True, null=True)
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="documentos_maestro_revisados",
    )

    class Meta:
        ordering = ("tipo",)
        constraints = [
            models.UniqueConstraint(
                fields=("perfil", "tipo"),
                name="maestro_documento_tipo_unico",
            )
        ]
        verbose_name = "Documento de maestro"
        verbose_name_plural = "Documentos de maestros"

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.perfil.usuario.username}"

    def preparar_reemplazo(self, archivo):
        anterior = self.archivo.name if self.archivo else ""
        self.archivo = archivo
        self.estado_revision = self.EstadoRevision.PENDIENTE
        self.observacion_admin = ""
        self.revisado_en = None
        self.revisado_por = None
        self.full_clean()
        self.save()
        if anterior and anterior != self.archivo.name:
            self.archivo.storage.delete(anterior)
        self.perfil.volver_a_revision_por_edicion()
        return self

    def revisar(self, estado, administrador, observacion=""):
        if estado not in self.EstadoRevision.values:
            raise ValidationError("El estado documental no es válido.")
        observacion = observacion.strip()
        if estado == self.EstadoRevision.RECHAZADO and len(observacion) < 10:
            raise ValidationError(
                "Debes indicar un motivo de rechazo de al menos 10 caracteres."
            )
        self.estado_revision = estado
        self.observacion_admin = observacion
        self.revisado_en = timezone.now() if estado != self.EstadoRevision.PENDIENTE else None
        self.revisado_por = administrador if estado != self.EstadoRevision.PENDIENTE else None
        self.save(
            update_fields=[
                "estado_revision",
                "observacion_admin",
                "revisado_en",
                "revisado_por",
                "actualizado_en",
            ]
        )


class LicenciaMaestro(models.Model):
    EstadoRevision = EstadoRevisionDocumento
    CLASES_ELECTRICAS = (("A", "Clase A"), ("B", "Clase B"), ("C", "Clase C"), ("D", "Clase D"))
    CLASES_GAS = (("1", "Clase 1"), ("2", "Clase 2"), ("3", "Clase 3"))
    CLASES = CLASES_ELECTRICAS + CLASES_GAS

    perfil = models.ForeignKey(
        PerfilMaestro,
        on_delete=models.CASCADE,
        related_name="licencias",
    )
    tipo_licencia = models.CharField(
        max_length=20,
        choices=(
            (Especialidad.TipoLicencia.SEC_ELECTRICA, "SEC eléctrica"),
            (Especialidad.TipoLicencia.SEC_GAS, "SEC gas"),
        ),
    )
    clase = models.CharField(max_length=1, choices=CLASES)
    numero_licencia = models.CharField(max_length=100)
    archivo = models.FileField(
        storage=documentos_privados_storage,
        upload_to="maestros/licencias/%Y/%m/",
        validators=[validar_archivo_documental],
    )
    estado_revision = models.CharField(
        max_length=12,
        choices=EstadoRevisionDocumento.choices,
        default=EstadoRevisionDocumento.PENDIENTE,
        db_index=True,
    )
    observacion_admin = models.TextField(blank=True, max_length=2000)
    subido_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    revisado_en = models.DateTimeField(blank=True, null=True)
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="licencias_maestro_revisadas",
    )

    class Meta:
        ordering = ("tipo_licencia",)
        constraints = [
            models.UniqueConstraint(
                fields=("perfil", "tipo_licencia"),
                name="maestro_licencia_tipo_unico",
            )
        ]
        verbose_name = "Licencia de maestro"
        verbose_name_plural = "Licencias de maestros"

    def __str__(self):
        return f"{self.get_tipo_licencia_display()} - {self.perfil.usuario.username}"

    def clean(self):
        super().clean()
        permitidas = {
            Especialidad.TipoLicencia.SEC_ELECTRICA: {"A", "B", "C", "D"},
            Especialidad.TipoLicencia.SEC_GAS: {"1", "2", "3"},
        }
        if self.clase not in permitidas.get(self.tipo_licencia, set()):
            raise ValidationError(
                {"clase": "La clase no corresponde al tipo de licencia seleccionado."}
            )

    def preparar_reemplazo(self, archivo, clase, numero_licencia):
        anterior = self.archivo.name if self.archivo else ""
        self.archivo = archivo
        self.clase = clase
        self.numero_licencia = numero_licencia.strip()
        self.estado_revision = self.EstadoRevision.PENDIENTE
        self.observacion_admin = ""
        self.revisado_en = None
        self.revisado_por = None
        self.full_clean()
        self.save()
        if anterior and anterior != self.archivo.name:
            self.archivo.storage.delete(anterior)
        self.perfil.volver_a_revision_por_edicion()
        return self

    def revisar(self, estado, administrador, observacion=""):
        if estado not in self.EstadoRevision.values:
            raise ValidationError("El estado documental no es válido.")
        observacion = observacion.strip()
        if estado == self.EstadoRevision.RECHAZADO and len(observacion) < 10:
            raise ValidationError(
                "Debes indicar un motivo de rechazo de al menos 10 caracteres."
            )
        self.estado_revision = estado
        self.observacion_admin = observacion
        self.revisado_en = timezone.now() if estado != self.EstadoRevision.PENDIENTE else None
        self.revisado_por = administrador if estado != self.EstadoRevision.PENDIENTE else None
        self.save(
            update_fields=[
                "estado_revision",
                "observacion_admin",
                "revisado_en",
                "revisado_por",
                "actualizado_en",
            ]
        )


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
