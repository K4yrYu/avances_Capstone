from functools import wraps

from django.shortcuts import render

from .models import Usuario


def _pagina_restringida_404(comprobar_permiso):
    """Oculta una página interna cuando el visitante no tiene acceso."""

    def decorador(vista):
        @wraps(vista)
        def protegida(request, *args, **kwargs):
            usuario = request.user
            if not usuario.is_authenticated or not usuario.is_active:
                return render(request, '404.html', status=404)
            if not comprobar_permiso(usuario):
                return render(request, '404.html', status=404)
            return vista(request, *args, **kwargs)

        return protegida

    return decorador


def _es_admin(usuario):
    return usuario.is_staff or usuario.rol == Usuario.Rol.ADMINISTRADOR


def _es_repartidor_o_admin(usuario):
    return (
        _es_admin(usuario)
        or usuario.rol == Usuario.Rol.REPARTIDOR
        or usuario.groups.filter(name='Repartidores').exists()
    )


def _es_retiros_o_admin(usuario):
    return _es_admin(usuario) or usuario.rol == Usuario.Rol.RETIROS


solo_admin_404 = _pagina_restringida_404(_es_admin)
solo_repartidor_o_admin_404 = _pagina_restringida_404(_es_repartidor_o_admin)
solo_retiros_o_admin_404 = _pagina_restringida_404(_es_retiros_o_admin)
