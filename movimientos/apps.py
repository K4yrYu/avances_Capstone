from django.apps import AppConfig


class MovimientosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "movimientos"
    verbose_name = "Movimientos de inventario"

    def ready(self):
        from . import signals  # noqa: F401
