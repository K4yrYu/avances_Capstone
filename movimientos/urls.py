from django.urls import path

from . import views


app_name = "movimientos"

urlpatterns = [
    path("administracion/movimientos/", views.lista_movimientos, name="lista"),
    path("administracion/movimientos/ajuste/", views.registrar_ajuste, name="registrar_ajuste"),
]
