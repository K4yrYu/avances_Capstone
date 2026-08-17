from django.urls import path

from . import views


urlpatterns = [
    path('asistente/', views.asistente_sfi, name='asistente_sfi'),
    path('asistente/api/consultar/', views.api_consultar_asistente, name='api_consultar_asistente'),
    path(
        'asistente/api/configurar-foto/',
        views.api_configurar_foto_pintura,
        name='api_configurar_foto_pintura',
    ),
    path(
        'asistente/api/analizar-pintura/',
        views.api_analizar_foto_pintura,
        name='api_analizar_foto_pintura',
    ),
]
