from rest_framework.permissions import BasePermission


class IsActiveVerifiedUser(BasePermission):
    """Restringe la gestión profesional a cuentas activas y verificadas."""

    message = "Debes tener una cuenta activa y un correo confirmado."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and getattr(user, "email_confirmado", False)
        )
