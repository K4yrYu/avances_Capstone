from django.contrib import admin

from .models import LoteInventario, MovimientoInventario


@admin.register(MovimientoInventario)
class MovimientoInventarioAdmin(admin.ModelAdmin):
    list_display = ("creado_en", "producto_nombre", "producto_sku", "tipo", "origen", "stock_resultante")
    list_filter = ("tipo", "estado", "origen", "creado_en")
    search_fields = ("producto_nombre", "producto_sku", "referencia")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LoteInventario)
class LoteInventarioAdmin(admin.ModelAdmin):
    list_display = ("producto", "lote", "cantidad_disponible", "fecha_vencimiento")
    list_filter = ("fecha_vencimiento",)
    search_fields = ("producto__nombre", "producto__sku", "lote")
