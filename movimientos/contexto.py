from contextlib import contextmanager
from contextvars import ContextVar


_responsable_actual = ContextVar("responsable_movimiento", default=None)


def obtener_responsable_actual():
    return _responsable_actual.get()


@contextmanager
def contexto_responsable(usuario):
    token = _responsable_actual.set(usuario if getattr(usuario, "is_authenticated", False) else None)
    try:
        yield
    finally:
        _responsable_actual.reset(token)
