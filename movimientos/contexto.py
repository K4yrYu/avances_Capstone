from contextlib import contextmanager
from contextvars import ContextVar


_responsable_actual = ContextVar("responsable_movimiento", default=None)
_motivo_actual = ContextVar("motivo_movimiento", default="")


def obtener_responsable_actual():
    return _responsable_actual.get()


def obtener_motivo_actual():
    return _motivo_actual.get()


@contextmanager
def contexto_responsable(usuario):
    token = _responsable_actual.set(usuario if getattr(usuario, "is_authenticated", False) else None)
    try:
        yield
    finally:
        _responsable_actual.reset(token)


@contextmanager
def contexto_reajuste(usuario, motivo):
    token_usuario = _responsable_actual.set(
        usuario if getattr(usuario, "is_authenticated", False) else None
    )
    token_motivo = _motivo_actual.set(str(motivo or "").strip())
    try:
        yield
    finally:
        _motivo_actual.reset(token_motivo)
        _responsable_actual.reset(token_usuario)
