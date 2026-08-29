import logging
from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authtoken.models import Token
from .serializers import RegistroUsuarioSerializer, AdminUsuarioSerializer, LoginSerializer, UsuarioListaSerializer
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.throttling import ScopedRateThrottle
from .throttles import RegistroRateThrottle
from .models import Usuario
from django.contrib.auth.decorators import user_passes_test
from carro_compras.models import Venta
from django.utils import timezone
from django.contrib.auth.views import PasswordResetView
from django.core.cache import cache
from django.views.decorators.http import require_POST
from django.urls import reverse_lazy, reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.db import transaction
from .services import limpiar_cuentas_no_verificadas

signer = TimestampSigner()
logger = logging.getLogger(__name__)

# ===================== VISTAS HTML =======================

def iniciosesion(request):
    return render(request, 'usuarios/iniciosesion.html')

def registro(request):
    return render(request, 'usuarios/registro.html')

@require_POST
def cerrar_sesion(request):
    if request.user.is_authenticated:
        Token.objects.filter(user=request.user).delete()
    logout(request)
    return redirect('/')

def vista_registro_pendiente(request):
    return render(request, 'usuarios/registro_pendiente.html')

def activar_cuenta(request, token):
    try:
        max_age = settings.ACCOUNT_ACTIVATION_HOURS * 60 * 60
        email = signer.unsign(token, max_age=max_age)
        with transaction.atomic():
            user = Usuario.objects.select_for_update().get(email=email)
            if user.email_confirmado or not user.activacion_expira_en:
                return render(request, 'usuarios/activacion_fallida.html')
            if user.activacion_expira_en <= timezone.now():
                if not user.is_active and not user.email_confirmado:
                    user.delete()
                return render(request, 'usuarios/activacion_fallida.html')
            user.is_active = True
            user.email_confirmado = True
            user.activacion_expira_en = None
            user.save(update_fields=[
                'is_active', 'email_confirmado', 'activacion_expira_en',
            ])
        return render(request, 'usuarios/activacion_exitosa.html')
    except (BadSignature, SignatureExpired, Usuario.DoesNotExist):
        return render(request, 'usuarios/activacion_fallida.html')

@user_passes_test(lambda u: u.is_staff)
def vista_lista_usuarios(request):
    return render(request, 'usuarios/lista_usuarios.html')

@user_passes_test(lambda u: u.is_staff, login_url='/usuarios/iniciosesion/')
def vista_agregar_usuario(request):
    return render(request, 'usuarios/agregar_usuario.html')

@user_passes_test(lambda u: u.is_staff)
def vista_editar_usuario(request, id):
    usuario = get_object_or_404(Usuario, id=id)
    return render(request, 'usuarios/editar_usuario.html', {'usuario': usuario})


# ===================== API REST ==========================

class RegistroAPIView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [RegistroRateThrottle]
    throttle_scope = 'register'

    def post(self, request):
        limpiar_cuentas_no_verificadas(
            email=str(request.data.get('email', '')).strip(),
            rut=str(request.data.get('rut', '')).strip(),
            username=str(request.data.get('username', '')).strip(),
        )
        serializer = RegistroUsuarioSerializer(data=request.data)
        if serializer.is_valid():
            try:
                with transaction.atomic():
                    user = serializer.save()
                    token = signer.sign(user.email)
                    activation_url = request.build_absolute_uri(
                        reverse('activar_cuenta', args=[token])
                    )
                    activation_html = render_to_string(
                        'usuarios/emails/activacion_cuenta.html',
                        {
                            'nombre': user.first_name,
                            'activation_url': activation_url,
                        },
                    )
                    enviados = send_mail(
                        subject='Confirma tu correo y activa tu cuenta | SFI',
                        message=(
                            f'Hola {user.first_name},\n\n'
                            'Confirma tu correo para activar tu cuenta SFI usando este enlace:\n'
                            f'{activation_url}\n\n'
                            'El enlace vence en 24 horas. Si no activas la cuenta dentro de ese plazo, '
                            'el registro pendiente será eliminado. Si no creaste esta cuenta, ignora el mensaje.'
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[user.email],
                        html_message=activation_html,
                    )
                    if enviados != 1:
                        raise RuntimeError('El servidor de correo no confirmó el envío de activación.')
                    enviado_en = timezone.now()
                    user.correo_activacion_enviado_en = enviado_en
                    user.activacion_expira_en = enviado_en + timedelta(
                        hours=settings.ACCOUNT_ACTIVATION_HOURS
                    )
                    user.save(update_fields=[
                        'correo_activacion_enviado_en', 'activacion_expira_en',
                    ])
            except Exception:
                logger.exception('No se pudo enviar el correo de activación')
                return Response(
                    {'detail': 'No fue posible completar el registro. Intenta nuevamente.'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            return Response({
                'status': 'success',
                'message': 'Usuario registrado. Tienes 24 horas para activar la cuenta antes de que sea eliminada.',
                'redirect_url': '/usuarios/registro/pendiente/'
            }, status=201)

        return Response(serializer.errors, status=400)

class LoginAPIView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            login(request, user)
            Token.objects.filter(user=user).delete()
            token = Token.objects.create(user=user)
            next_url = str(request.data.get('next') or '').strip()
            if not url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                next_url = '/'
            return Response({
                'status': 'success',
                'message': 'Inicio de sesión exitoso',
                'token': token.key,
                'redirect_url': next_url,
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def api_lista_usuarios(request):
    usuarios = Usuario.objects.all()
    serializer = UsuarioListaSerializer(usuarios, many=True)
    return Response(serializer.data)

@api_view(['POST'])
@permission_classes([IsAdminUser])
def api_agregar_usuario(request):
    serializer = AdminUsuarioSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=201)
    return Response(serializer.errors, status=400)

@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def api_toggle_activo_usuario(request, id):
    usuario = get_object_or_404(Usuario, id=id)
    if usuario == request.user:
        return Response({"error": "No puedes suspender tu propia cuenta."}, status=403)
    usuario.is_active = not usuario.is_active
    usuario.save(update_fields=['is_active'])
    return Response({"message": "Estado actualizado", "is_active": usuario.is_active})

@api_view(['PUT'])
@permission_classes([IsAdminUser])
def api_editar_usuario(request, id):
    usuario = get_object_or_404(Usuario, id=id)
    if not usuario.is_active:
        return Response({"error": "No puedes editar un usuario suspendido."}, status=403)
    if request.user == usuario:
        return Response({"error": "No puedes editar tu propia cuenta desde el panel."}, status=403)
    serializer = AdminUsuarioSerializer(usuario, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=200)
    return Response(serializer.errors, status=400)


# ===================== RECUPERAR CONTRASEÑA ==========================

class VistaRecuperarConValidacion(PasswordResetView):
    template_name = 'usuarios/recuperar.html'
    email_template_name = 'usuarios/password_reset_email.html'
    subject_template_name = 'usuarios/password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['email'].widget.attrs.update({
            'placeholder': 'tu@correo.cl',
            'autocomplete': 'email',
        })
        return form

    def post(self, request, *args, **kwargs):
        client_ip = request.META.get('REMOTE_ADDR', 'unknown')
        cache_key = f'password-reset:{client_ip}'
        attempts = cache.get(cache_key, 0)
        if attempts >= 5:
            return render(
                request,
                self.template_name,
                {'form': self.get_form(), 'rate_limited': True},
                status=429,
            )
        cache.set(cache_key, attempts + 1, timeout=60 * 60)
        return super().post(request, *args, **kwargs)
