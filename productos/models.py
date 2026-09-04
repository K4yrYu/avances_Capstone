from decimal import Decimal

from django.conf import settings
from django.core.validators import RegexValidator
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class Proveedor(models.Model):
    nombre = models.CharField(max_length=160, unique=True)
    nombre_contacto = models.CharField(max_length=160, blank=True)
    email = models.EmailField()
    telefono = models.CharField(max_length=40, blank=True)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nombre

    class Meta:
        ordering = ['nombre']


class Producto(models.Model):
    CATEGORIA_CHOICES = [
        ('General', 'General'),
        ('Herramientas', 'Herramientas'),
        ('Construcción', 'Construcción'),
        ('Electricidad', 'Electricidad'),
        ('Pinturas', 'Pinturas'),
        ('Gasfitería', 'Gasfitería'),
        ('Adhesivos', 'Adhesivos'),
        ('Iluminación', 'Iluminación'),
        ('Ferretería', 'Ferretería'),
        ('Seguridad', 'Seguridad'),
        ('Otra', 'Otra'),
    ]
    UNIDAD_VENTA_CHOICES = [
        ('unidad', 'Unidad'),
        ('envase', 'Envase'),
        ('paquete', 'Paquete'),
        ('caja', 'Caja'),
        ('saco', 'Saco'),
        ('rollo', 'Rollo'),
        ('juego', 'Juego'),
    ]
    UNIDAD_CONTENIDO_CHOICES = [
        ('unidad', 'unidad(es)'),
        ('ml', 'mL'),
        ('l', 'L'),
        ('g', 'g'),
        ('kg', 'kg'),
        ('m', 'm'),
        ('m2', 'm²'),
        ('m3', 'm³'),
    ]
    TIPO_CALCULO_CHOICES = [
        ('ninguno', 'Sin cálculo automático'),
        ('pintura', 'Pintura por superficie'),
        ('superficie', 'Cobertura por superficie'),
        ('longitud', 'Material por longitud'),
        ('peso', 'Material por peso'),
        ('unidad', 'Material por unidades'),
    ]
    UNIDAD_RENDIMIENTO_CHOICES = [
        ('', 'No aplica'),
        ('m2_l', 'm² por litro'),
        ('m2_kg', 'm² por kilogramo'),
        ('m2_unidad', 'm² por unidad'),
        ('m_unidad', 'metros por unidad'),
        ('unidad_m2', 'unidades por m²'),
    ]

    AMBIENTE_USO_CHOICES = [
        ('no_aplica', 'No aplica'),
        ('interior', 'Interior'),
        ('exterior', 'Exterior'),
        ('interior_exterior', 'Interior y exterior'),
        ('especial', 'Uso especial o t\u00e9cnico'),
    ]
    SUPERFICIE_CHOICES = [
        ('yeso_carton', 'Yeso y yeso-cart\u00f3n'),
        ('yeso', 'Yeso'),
        ('pasta_muro', 'Pasta muro o superficie empastada'),
        ('estuco', 'Estuco'),
        ('hormigon', 'Hormig\u00f3n o concreto'),
        ('ladrillo', 'Ladrillo'),
        ('fibrocemento', 'Fibrocemento'),
        ('madera', 'Madera preparada'),
        ('metal_galvanizado', 'Metal galvanizado'),
        ('piscina_estanque', 'Piscina o estanque'),
    ]
    TIPO_PINTURA_CHOICES = [
        ('no_aplica', 'No aplica'),
        ('latex', 'L\u00e1tex al agua'),
        ('esmalte_agua', 'Esmalte al agua'),
        ('caucho_clorado', 'Caucho clorado'),
    ]
    TERMINACION_CHOICES = [
        ('no_aplica', 'No aplica'),
        ('mate', 'Mate'),
        ('satinado', 'Satinado'),
        ('semibrillo', 'Semibrillo'),
        ('cascara_huevo', 'C\u00e1scara de huevo'),
        ('lisa_mate', 'Lisa y mate'),
    ]
    PROPIEDAD_PINTURA_CHOICES = [
        ('base_agua', 'Base agua'),
        ('bajo_olor', 'Bajo olor'),
        ('lavable', 'Lavable'),
        ('super_lavable', 'S\u00faper lavable'),
        ('antihongos', 'Antihongos'),
        ('hidrorrepelente', 'Hidrorrepelente'),
        ('proteccion_uv', 'Protecci\u00f3n UV'),
        ('alto_cubrimiento', 'Alto poder cubridor'),
        ('secado_rapido', 'Secado r\u00e1pido'),
        ('resistente_sanitizantes', 'Resistente a sanitizantes'),
    ]
    PREPARACION_CHOICES = [
        ('limpieza', 'Limpiar y secar'),
        ('lijado', 'Lijar'),
        ('reparacion', 'Reparar grietas o imperfecciones'),
        ('sellador', 'Aplicar sellador'),
        ('imprimante', 'Aplicar imprimante'),
        ('impermeabilizacion', 'Impermeabilizar previamente'),
    ]
    ESTADO_SUPERFICIE_CHOICES = [
        ('nueva', 'Nueva o sin pintar'),
        ('pintada_buen_estado', 'Pintada y en buen estado'),
        ('deteriorada', 'Deteriorada o con grietas'),
        ('humedad', 'Con humedad o manchas'),
    ]

    nombre = models.CharField(max_length=200)
    descripcion = models.TextField()
    precio = models.IntegerField(validators=[MinValueValidator(1)])
    imagen = models.ImageField(upload_to='productos/', max_length=255)
    stock = models.PositiveIntegerField(default=0)
    controla_vencimiento = models.BooleanField(
        default=False,
        help_text='Controla las existencias de este producto por lote y fecha de vencimiento.',
    )
    categoria = models.CharField(
        max_length=100,
        choices=CATEGORIA_CHOICES,
        default='Otra',
    )
    activo = models.BooleanField(default=True)

    # Ficha comercial y técnica. Estos datos alimentarán al asistente SFI.
    marca = models.CharField(max_length=100, blank=True)
    modelo = models.CharField(max_length=120, blank=True)
    sku = models.CharField(max_length=50, unique=True, null=True, blank=True)
    color = models.CharField(max_length=80, blank=True)
    color_hex = models.CharField(
        max_length=7,
        blank=True,
        validators=[RegexValidator(r'^#[0-9A-Fa-f]{6}$', 'Usa un color hexadecimal como #FFFFFF.')],
    )
    ambiente_uso = models.CharField(
        max_length=20,
        choices=AMBIENTE_USO_CHOICES,
        default='no_aplica',
    )
    superficies_compatibles = models.JSONField(default=list, blank=True)
    tipo_pintura = models.CharField(
        max_length=20,
        choices=TIPO_PINTURA_CHOICES,
        default='no_aplica',
    )
    terminacion = models.CharField(
        max_length=20,
        choices=TERMINACION_CHOICES,
        default='no_aplica',
    )
    propiedades_pintura = models.JSONField(default=list, blank=True)
    preparaciones_recomendadas = models.JSONField(default=list, blank=True)
    secado_tacto_horas = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01')), MaxValueValidator(Decimal('168'))],
    )
    repintado_min_horas = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01')), MaxValueValidator(Decimal('720'))],
    )
    repintado_max_horas = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01')), MaxValueValidator(Decimal('720'))],
    )
    proveedor = models.ForeignKey(
        Proveedor,
        on_delete=models.SET_NULL,
        related_name='productos',
        null=True,
        blank=True,
    )
    stock_minimo = models.PositiveIntegerField(default=5)
    unidad_venta = models.CharField(
        max_length=20,
        choices=UNIDAD_VENTA_CHOICES,
        default='unidad',
    )
    contenido = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.001'))],
    )
    unidad_contenido = models.CharField(
        max_length=20,
        choices=UNIDAD_CONTENIDO_CHOICES,
        blank=True,
    )
    tipo_calculo = models.CharField(
        max_length=20,
        choices=TIPO_CALCULO_CHOICES,
        default='ninguno',
    )
    rendimiento = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.001'))],
    )
    unidad_rendimiento = models.CharField(
        max_length=30,
        choices=UNIDAD_RENDIMIENTO_CHOICES,
        blank=True,
    )
    capas_recomendadas = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
    )
    porcentaje_desperdicio = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('10.00'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('50'))],
    )
    uso_recomendado = models.TextField(blank=True)
    especificaciones = models.JSONField(default=dict, blank=True)
    informacion_tecnica_verificada = models.BooleanField(default=False)

    def __str__(self):
        return self.nombre

    @staticmethod
    def _numero_legible(value):
        if value is None:
            return ''
        return format(value.normalize(), 'f')

    @property
    def presentacion(self):
        if self.contenido and self.unidad_contenido:
            return f'{self._numero_legible(self.contenido)} {self.get_unidad_contenido_display()}'
        return self.get_unidad_venta_display()

    @property
    def rendimiento_legible(self):
        if not self.rendimiento or not self.unidad_rendimiento:
            return ''
        return f'{self._numero_legible(self.rendimiento)} {self.get_unidad_rendimiento_display()}'

    @property
    def superficies_compatibles_display(self):
        etiquetas = dict(self.SUPERFICIE_CHOICES)
        return [etiquetas[valor] for valor in self.superficies_compatibles if valor in etiquetas]

    @property
    def propiedades_pintura_display(self):
        etiquetas = dict(self.PROPIEDAD_PINTURA_CHOICES)
        return [etiquetas[valor] for valor in self.propiedades_pintura if valor in etiquetas]

    @property
    def preparaciones_recomendadas_display(self):
        etiquetas = dict(self.PREPARACION_CHOICES)
        return [etiquetas[valor] for valor in self.preparaciones_recomendadas if valor in etiquetas]

    @property
    def tiempo_repintado_legible(self):
        if self.repintado_min_horas is None:
            return ''
        minimo = self._numero_legible(self.repintado_min_horas)
        if self.repintado_max_horas and self.repintado_max_horas != self.repintado_min_horas:
            return f'{minimo} a {self._numero_legible(self.repintado_max_horas)} horas'
        return f'{minimo} horas'

    @property
    def apto_para_calculo(self):
        if not self.informacion_tecnica_verificada or self.tipo_calculo == 'ninguno':
            return False
        if self.tipo_calculo == 'pintura' and (
            self.ambiente_uso == 'no_aplica'
            or not self.superficies_compatibles
            or self.tipo_pintura == 'no_aplica'
            or self.terminacion == 'no_aplica'
            or not self.propiedades_pintura
            or not self.preparaciones_recomendadas
            or self.repintado_min_horas is None
        ):
            return False
        datos_base = bool(self.contenido and self.unidad_contenido)
        if self.tipo_calculo in {'pintura', 'superficie'}:
            return bool(
                datos_base
                and self.rendimiento
                and self.unidad_rendimiento
                and (self.tipo_calculo != 'pintura' or self.capas_recomendadas)
            )
        return datos_base

    @property
    def necesita_reposicion(self):
        return self.activo and self.stock <= self.stock_minimo

    @property
    def cantidad_reposicion_sugerida(self):
        if not self.necesita_reposicion:
            return 0
        return max((self.stock_minimo * 2) - self.stock, 1)

    class Meta:
        ordering = ['nombre', 'id']
        constraints = [
            models.CheckConstraint(condition=Q(precio__gt=0), name='producto_precio_positivo'),
            models.CheckConstraint(condition=Q(stock__gte=0), name='producto_stock_no_negativo'),
            models.CheckConstraint(
                condition=Q(contenido__isnull=True) | Q(contenido__gt=0),
                name='producto_contenido_positivo',
            ),
            models.CheckConstraint(
                condition=Q(rendimiento__isnull=True) | Q(rendimiento__gt=0),
                name='producto_rendimiento_positivo',
            ),
            models.CheckConstraint(
                condition=Q(porcentaje_desperdicio__gte=0) & Q(porcentaje_desperdicio__lte=50),
                name='producto_desperdicio_valido',
            ),
        ]


class HistorialPrecio(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='historial_precios')
    precio_anterior = models.IntegerField(validators=[MinValueValidator(1)])
    precio_nuevo = models.IntegerField(validators=[MinValueValidator(1)])
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.producto.nombre} | {self.precio_anterior} → {self.precio_nuevo}'


class SolicitudReposicion(models.Model):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente de envío'),
        ('enviada', 'Envío aprobado'),
        ('parcial', 'Recepción parcial'),
        ('error', 'Error de envío'),
        ('recibida', 'Mercadería recibida'),
        ('cancelada', 'Cancelada'),
    ]

    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, related_name='solicitudes')
    creada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='solicitudes_reposicion',
    )
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente')
    email_destino = models.EmailField()
    asunto = models.CharField(max_length=200)
    observaciones = models.TextField(blank=True)
    error_envio = models.TextField(blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)
    enviada_en = models.DateTimeField(null=True, blank=True)
    recibida_en = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'{self.numero} | {self.proveedor.nombre}'

    @property
    def numero(self):
        return f'OC-{self.pk:04d}' if self.pk else 'OC-pendiente'

    @property
    def total_unidades(self):
        return sum(item.cantidad_solicitada for item in self.items.all())

    @property
    def total_unidades_pendientes(self):
        return sum(item.cantidad_pendiente for item in self.items.all())

    class Meta:
        ordering = ['-creada_en', '-id']


class DetalleSolicitudReposicion(models.Model):
    solicitud = models.ForeignKey(SolicitudReposicion, on_delete=models.CASCADE, related_name='items')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='detalles_reposicion')
    cantidad_solicitada = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    stock_al_solicitar = models.PositiveIntegerField()

    def __str__(self):
        return f'{self.producto.nombre}: {self.cantidad_solicitada}'

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['solicitud', 'producto'],
                name='reposicion_producto_unico_por_solicitud',
            ),
        ]

    @property
    def cantidad_recibida_total(self):
        return sum(
            detalle.cantidad_recibida
            for recepcion in self.solicitud.recepciones.all()
            for detalle in recepcion.detalles.all()
            if detalle.detalle_solicitud_id == self.pk
        )

    @property
    def cantidad_pendiente(self):
        return max(self.cantidad_solicitada - self.cantidad_recibida_total, 0)


class RecepcionReposicion(models.Model):
    class Estado(models.TextChoices):
        COMPLETA = 'completa', 'Recepción completa'
        PARCIAL = 'parcial', 'Recepción parcial'
        INCIDENCIA = 'incidencia', 'Recepción con incidencias'

    solicitud = models.ForeignKey(
        SolicitudReposicion,
        on_delete=models.PROTECT,
        related_name='recepciones',
    )
    recibida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='recepciones_reposicion',
    )
    estado = models.CharField(max_length=20, choices=Estado.choices)
    clave_idempotencia = models.CharField(max_length=100, unique=True)
    observaciones = models.TextField(blank=True)
    recibida_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recibida_en', '-id']

    def __str__(self):
        return f'{self.solicitud.numero} | {self.get_estado_display()}'

    @property
    def total_unidades_recibidas(self):
        return sum(detalle.cantidad_recibida for detalle in self.detalles.all())


class DetalleRecepcionReposicion(models.Model):
    class Resultado(models.TextChoices):
        COMPLETO = 'completo', 'Recibido completo'
        PARCIAL = 'parcial', 'Recibido parcialmente'
        NO_LLEGO = 'no_llego', 'No llegó'
        DANADO = 'danado', 'Llegó dañado'
        EQUIVOCADO = 'equivocado', 'Producto equivocado'
        OTRO = 'otro', 'Otro problema'

    recepcion = models.ForeignKey(
        RecepcionReposicion,
        on_delete=models.PROTECT,
        related_name='detalles',
    )
    detalle_solicitud = models.ForeignKey(
        DetalleSolicitudReposicion,
        on_delete=models.PROTECT,
        related_name='detalles_recepcion',
    )
    cantidad_recibida = models.PositiveIntegerField(default=0)
    resultado = models.CharField(max_length=20, choices=Resultado.choices)
    motivo = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['recepcion', 'detalle_solicitud'],
                name='recepcion_detalle_solicitud_unico',
            ),
        ]

    def __str__(self):
        return f'{self.detalle_solicitud.producto.nombre}: {self.get_resultado_display()}'
