from django.urls import path

from . import views
from productos import views as producto_views


app_name = "movimientos"

urlpatterns = [
    path("administracion/movimientos/", views.lista_movimientos, name="lista"),
    path("administracion/movimientos/merma/", views.registrar_merma, name="registrar_merma"),
    path("administracion/movimientos/reajuste/", views.iniciar_reajuste, name="iniciar_reajuste"),
    path(
        "administracion/movimientos/reajuste/<int:id>/",
        producto_views.editar_producto,
        name="reajustar_producto",
    ),
]
