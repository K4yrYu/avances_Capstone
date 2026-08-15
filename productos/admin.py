from django.contrib import admin

from .models import (
    DetalleSolicitudReposicion,
    HistorialPrecio,
    Producto,
    Proveedor,
    SolicitudReposicion,
)


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'nombre_contacto', 'email', 'telefono', 'activo')
    list_filter = ('activo',)
    search_fields = ('nombre', 'nombre_contacto', 'email')


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = (
        'nombre', 'marca', 'categoria', 'ambiente_uso', 'tipo_pintura', 'terminacion',
        'precio', 'stock', 'stock_minimo',
        'proveedor', 'activo',
        'informacion_tecnica_verificada', 'estado_calculo',
    )
    list_filter = (
        'activo', 'categoria', 'ambiente_uso', 'tipo_pintura', 'terminacion',
        'proveedor', 'tipo_calculo', 'informacion_tecnica_verificada',
    )
    search_fields = ('nombre', 'marca', 'modelo', 'descripcion', 'uso_recomendado')
    ordering = ('nombre',)
    readonly_fields = ('presentacion', 'rendimiento_legible', 'estado_calculo')
    fieldsets = (
        ('Información comercial', {
            'fields': (
                'nombre', 'marca', 'modelo', ('color', 'color_hex'), 'ambiente_uso',
                'descripcion', 'categoria', 'precio', 'imagen',
            ),
        }),
        ('Inventario', {
            'fields': (('stock', 'stock_minimo'), 'proveedor', 'activo', 'unidad_venta'),
        }),
        ('Ficha técnica para el asistente SFI', {
            'fields': (
                ('contenido', 'unidad_contenido'),
                'tipo_calculo',
                ('rendimiento', 'unidad_rendimiento'),
                ('capas_recomendadas', 'porcentaje_desperdicio'),
                ('tipo_pintura', 'terminacion'),
                'superficies_compatibles', 'propiedades_pintura',
                'preparaciones_recomendadas',
                ('secado_tacto_horas', 'repintado_min_horas', 'repintado_max_horas'),
                'uso_recomendado', 'especificaciones',
                'informacion_tecnica_verificada',
                ('presentacion', 'rendimiento_legible', 'estado_calculo'),
            ),
        }),
    )

    @admin.display(boolean=True, description='Apto para cálculo')
    def estado_calculo(self, obj):
        return obj.apto_para_calculo


@admin.register(HistorialPrecio)
class HistorialPrecioAdmin(admin.ModelAdmin):
    list_display = ('producto', 'precio_anterior', 'precio_nuevo', 'fecha')
    search_fields = ('producto__nombre',)
    ordering = ('-fecha',)
    readonly_fields = ('producto', 'precio_anterior', 'precio_nuevo', 'fecha')


class DetalleSolicitudReposicionInline(admin.TabularInline):
    model = DetalleSolicitudReposicion
    extra = 0
    readonly_fields = ('producto', 'cantidad_solicitada', 'stock_al_solicitar')


@admin.register(SolicitudReposicion)
class SolicitudReposicionAdmin(admin.ModelAdmin):
    list_display = ('numero', 'proveedor', 'estado', 'email_destino', 'creada_por', 'creada_en')
    list_filter = ('estado', 'proveedor')
    search_fields = ('asunto', 'email_destino', 'proveedor__nombre')
    readonly_fields = (
        'proveedor', 'creada_por', 'estado', 'email_destino', 'asunto',
        'observaciones', 'error_envio', 'creada_en', 'enviada_en', 'recibida_en',
    )
    inlines = (DetalleSolicitudReposicionInline,)
