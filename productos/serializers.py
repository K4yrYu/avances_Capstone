import json
from decimal import Decimal

from PIL import Image, UnidentifiedImageError
from rest_framework import serializers

from .models import HistorialPrecio, Producto, Proveedor


class ProductoSerializer(serializers.ModelSerializer):
    imagen = serializers.ImageField(required=False, allow_empty_file=False)
    proveedor = serializers.PrimaryKeyRelatedField(
        queryset=Proveedor.objects.filter(activo=True),
        required=False,
        allow_null=True,
        write_only=True,
    )
    proveedor_nombre = serializers.CharField(source='proveedor.nombre', read_only=True)
    presentacion = serializers.CharField(read_only=True)
    rendimiento_legible = serializers.CharField(read_only=True)
    apto_para_calculo = serializers.BooleanField(read_only=True)
    tipo_calculo_display = serializers.CharField(source='get_tipo_calculo_display', read_only=True)
    ambiente_uso_display = serializers.CharField(source='get_ambiente_uso_display', read_only=True)
    superficies_compatibles_display = serializers.ListField(read_only=True)
    tipo_pintura_display = serializers.CharField(source='get_tipo_pintura_display', read_only=True)
    terminacion_display = serializers.CharField(source='get_terminacion_display', read_only=True)
    propiedades_pintura_display = serializers.ListField(read_only=True)
    preparaciones_recomendadas_display = serializers.ListField(read_only=True)
    tiempo_repintado_legible = serializers.CharField(read_only=True)
    necesita_reposicion = serializers.BooleanField(read_only=True)
    cantidad_reposicion_sugerida = serializers.IntegerField(read_only=True)

    class Meta:
        model = Producto
        fields = [
            'id', 'nombre', 'descripcion', 'precio', 'imagen', 'stock', 'categoria', 'activo',
            'marca', 'modelo', 'sku', 'color', 'color_hex', 'ambiente_uso', 'ambiente_uso_display',
            'superficies_compatibles', 'superficies_compatibles_display',
            'tipo_pintura', 'tipo_pintura_display', 'terminacion', 'terminacion_display',
            'propiedades_pintura', 'propiedades_pintura_display',
            'preparaciones_recomendadas', 'preparaciones_recomendadas_display',
            'secado_tacto_horas', 'repintado_min_horas', 'repintado_max_horas',
            'tiempo_repintado_legible',
            'proveedor', 'proveedor_nombre',
            'stock_minimo', 'controla_vencimiento', 'necesita_reposicion', 'cantidad_reposicion_sugerida',
            'unidad_venta', 'contenido', 'unidad_contenido',
            'tipo_calculo', 'tipo_calculo_display', 'rendimiento', 'unidad_rendimiento',
            'capas_recomendadas', 'porcentaje_desperdicio', 'uso_recomendado',
            'especificaciones', 'informacion_tecnica_verificada', 'presentacion',
            'rendimiento_legible', 'apto_para_calculo',
        ]
        read_only_fields = ['id']

    def _validate_stock_y_lotes(self, attrs):
        attrs = super().validate(attrs)
        if self.instance is not None and 'stock' in attrs and attrs['stock'] != self.instance.stock:
            raise serializers.ValidationError({
                'stock': 'El stock no se edita desde Productos. Registra una recepción, venta o ajuste en Movimientos.'
            })
        controla_vencimiento = attrs.get(
            'controla_vencimiento',
            self.instance.controla_vencimiento if self.instance else False,
        )
        stock = self.instance.stock if self.instance else attrs.get('stock', 0)
        if controla_vencimiento and stock:
            unidades_lote = 0
            if self.instance:
                unidades_lote = sum(
                    self.instance.lotes_inventario.values_list('cantidad_disponible', flat=True)
                )
            if unidades_lote != stock:
                raise serializers.ValidationError({
                    'controla_vencimiento': (
                        'Para activar el control por lotes, el stock debe estar en cero o ya estar respaldado por lotes. '
                        'Usa Movimientos y Reposición para regularizarlo.'
                    )
                })
        return attrs

    def validate_precio(self, value):
        if value <= 0:
            raise serializers.ValidationError('El precio debe ser mayor que cero.')
        return value

    def validate_stock(self, value):
        if value < 0:
            raise serializers.ValidationError('El stock no puede ser negativo.')
        return value

    def validate_stock_minimo(self, value):
        if value < 0 or value > 1_000_000:
            raise serializers.ValidationError('El stock mínimo debe estar entre 0 y 1.000.000.')
        return value

    def validate_marca(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('La marca es obligatoria para identificar el producto.')
        return value

    def validate_sku(self, value):
        value = str(value or '').strip().upper()
        return value or None

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

    def validate_especificaciones(self, value):
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as exc:
                raise serializers.ValidationError('Las especificaciones no tienen un formato válido.') from exc
        if not isinstance(value, dict):
            raise serializers.ValidationError('Las especificaciones deben ser un objeto de clave y valor.')
        if len(value) > 20:
            raise serializers.ValidationError('Puedes registrar como máximo 20 especificaciones.')
        normalizadas = {}
        for clave, contenido in value.items():
            clave_limpia = str(clave).strip()
            valor_limpio = str(contenido).strip()
            if not clave_limpia or not valor_limpio:
                continue
            if len(clave_limpia) > 60 or len(valor_limpio) > 200:
                raise serializers.ValidationError('Cada especificación debe ser breve y clara.')
            normalizadas[clave_limpia] = valor_limpio
        return normalizadas

    def validate_superficies_compatibles(self, value):
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as exc:
                raise serializers.ValidationError('Selecciona superficies validas.') from exc
        if not isinstance(value, list):
            raise serializers.ValidationError('Las superficies deben enviarse como una lista.')
        permitidas = dict(Producto.SUPERFICIE_CHOICES)
        normalizadas = []
        for superficie in value:
            superficie = str(superficie).strip()
            if superficie not in permitidas:
                raise serializers.ValidationError('La lista contiene una superficie no permitida.')
            if superficie not in normalizadas:
                normalizadas.append(superficie)
        return normalizadas

    @staticmethod
    def _normalizar_opciones(value, choices, mensaje):
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as exc:
                raise serializers.ValidationError(mensaje) from exc
        if not isinstance(value, list):
            raise serializers.ValidationError(mensaje)
        permitidas = dict(choices)
        normalizadas = []
        for opcion in value:
            opcion = str(opcion).strip()
            if opcion not in permitidas:
                raise serializers.ValidationError(mensaje)
            if opcion not in normalizadas:
                normalizadas.append(opcion)
        return normalizadas

    def validate_propiedades_pintura(self, value):
        return self._normalizar_opciones(
            value,
            Producto.PROPIEDAD_PINTURA_CHOICES,
            'La lista contiene una propiedad de pintura no permitida.',
        )

    def validate_preparaciones_recomendadas(self, value):
        return self._normalizar_opciones(
            value,
            Producto.PREPARACION_CHOICES,
            'La lista contiene una preparacion no permitida.',
        )

    def validate(self, attrs):
        attrs = self._validate_stock_y_lotes(attrs)
        if self.instance is None and not attrs.get('imagen'):
            raise serializers.ValidationError({'imagen': 'Debes subir una imagen del producto.'})

        def valor(nombre, defecto=None):
            if nombre in attrs:
                return attrs[nombre]
            return getattr(self.instance, nombre, defecto) if self.instance else defecto

        contenido = valor('contenido')
        unidad_contenido = valor('unidad_contenido', '')
        rendimiento = valor('rendimiento')
        unidad_rendimiento = valor('unidad_rendimiento', '')
        tipo_calculo = valor('tipo_calculo', 'ninguno')
        categoria = valor('categoria', 'Otra')
        ambiente_uso = valor('ambiente_uso', 'no_aplica')
        superficies = valor('superficies_compatibles', [])
        tipo_pintura = valor('tipo_pintura', 'no_aplica')
        terminacion = valor('terminacion', 'no_aplica')
        propiedades = valor('propiedades_pintura', [])
        preparaciones = valor('preparaciones_recomendadas', [])
        repintado_min = valor('repintado_min_horas')
        repintado_max = valor('repintado_max_horas')
        capas = valor('capas_recomendadas')
        verificada = valor('informacion_tecnica_verificada', False)

        # El color solo corresponde a pinturas o recubrimientos configurados
        # con calculo de pintura. Evita guardar este dato en herramientas u
        # otros productos donde no aporta informacion comercial.
        es_pintura = categoria == 'Pinturas' or tipo_calculo == 'pintura'
        errores = {}
        if not es_pintura:
            attrs['color'] = ''
            attrs['color_hex'] = ''
            attrs['ambiente_uso'] = 'no_aplica'
            attrs['superficies_compatibles'] = []
            attrs['tipo_pintura'] = 'no_aplica'
            attrs['terminacion'] = 'no_aplica'
            attrs['propiedades_pintura'] = []
            attrs['preparaciones_recomendadas'] = []
            attrs['secado_tacto_horas'] = None
            attrs['repintado_min_horas'] = None
            attrs['repintado_max_horas'] = None
        elif ambiente_uso == 'no_aplica':
            errores['ambiente_uso'] = 'Indica si la pintura es interior, exterior o de uso especial.'
        if es_pintura and not superficies:
            errores['superficies_compatibles'] = 'Selecciona al menos una superficie compatible.'
        if es_pintura and tipo_pintura == 'no_aplica':
            errores['tipo_pintura'] = 'Selecciona el tipo de pintura.'
        if es_pintura and terminacion == 'no_aplica':
            errores['terminacion'] = 'Selecciona la terminacion de la pintura.'
        if repintado_min is not None and repintado_max is not None and repintado_max < repintado_min:
            errores['repintado_max_horas'] = 'El tiempo maximo no puede ser menor que el minimo.'

        if bool(contenido) != bool(unidad_contenido):
            raise serializers.ValidationError({
                'contenido': 'Indica el contenido y su unidad de medida.',
                'unidad_contenido': 'Selecciona la unidad correspondiente al contenido.',
            })
        if bool(rendimiento) != bool(unidad_rendimiento):
            raise serializers.ValidationError({
                'rendimiento': 'Indica el rendimiento y su unidad.',
                'unidad_rendimiento': 'Selecciona la unidad correspondiente al rendimiento.',
            })
        if tipo_calculo == 'pintura' and unidad_contenido and unidad_contenido != 'l':
            raise serializers.ValidationError({'unidad_contenido': 'La pintura debe registrar su contenido en litros.'})
        if tipo_calculo == 'pintura' and unidad_rendimiento and unidad_rendimiento != 'm2_l':
            raise serializers.ValidationError({'unidad_rendimiento': 'La pintura debe usar m² por litro.'})

        if verificada and tipo_calculo != 'ninguno':
            if not contenido or not unidad_contenido:
                errores['contenido'] = 'Una ficha verificada necesita contenido y unidad.'
            if tipo_calculo in {'pintura', 'superficie'} and (not rendimiento or not unidad_rendimiento):
                errores['rendimiento'] = 'Este tipo de cálculo necesita un rendimiento comprobado.'
            if tipo_calculo == 'pintura' and not capas:
                errores['capas_recomendadas'] = 'Indica las capas recomendadas por el fabricante.'
            if tipo_calculo == 'pintura' and not propiedades:
                errores['propiedades_pintura'] = 'Registra al menos una propiedad verificada.'
            if tipo_calculo == 'pintura' and not preparaciones:
                errores['preparaciones_recomendadas'] = 'Registra al menos una preparacion recomendada.'
            if tipo_calculo == 'pintura' and repintado_min is None:
                errores['repintado_min_horas'] = 'Indica el tiempo minimo de repintado.'
        if errores:
            raise serializers.ValidationError(errores)

        desperdicio = valor('porcentaje_desperdicio', Decimal('10'))
        if desperdicio is not None and not Decimal('0') <= desperdicio <= Decimal('50'):
            raise serializers.ValidationError({'porcentaje_desperdicio': 'El margen debe estar entre 0% y 50%.'})
        return attrs


class HistorialPrecioSerializer(serializers.ModelSerializer):
    class Meta:
        model = HistorialPrecio
        fields = '__all__'


class CalculoPinturaEntradaSerializer(serializers.Serializer):
    superficie = serializers.IntegerField(min_value=1, max_value=100000)
    ambiente = serializers.ChoiceField(choices=[
        valor for valor, _ in Producto.AMBIENTE_USO_CHOICES if valor != 'no_aplica'
    ])
    tipo_superficie = serializers.ChoiceField(choices=Producto.SUPERFICIE_CHOICES)
    estado_superficie = serializers.ChoiceField(choices=Producto.ESTADO_SUPERFICIE_CHOICES)
    terminacion = serializers.ChoiceField(choices=[
        ('cualquiera', 'Sin preferencia'),
        *[opcion for opcion in Producto.TERMINACION_CHOICES if opcion[0] != 'no_aplica'],
    ])
    capas = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=10)
    desperdicio = serializers.DecimalField(
        required=False,
        allow_null=True,
        max_digits=5,
        decimal_places=2,
        min_value=Decimal('0'),
        max_value=Decimal('50'),
    )
    color = serializers.CharField(required=False, allow_blank=True, max_length=80, default='')
