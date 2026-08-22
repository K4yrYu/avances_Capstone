from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ImagenTrabajoRealizado, PerfilMaestro, TrabajoRealizado
from .permissions import IsActiveVerifiedUser
from .serializers import (
    CambioEstadoMaestroSerializer,
    CargaImagenesTrabajoSerializer,
    ImagenTrabajoSerializer,
    PerfilMaestroPublicoSerializer,
    PerfilMaestroSerializer,
    TrabajoRealizadoSerializer,
)


class APIPrivadaMaestros(APIView):
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsActiveVerifiedUser,)

    def perfil_propio(self, request):
        return get_object_or_404(
            PerfilMaestro.objects.prefetch_related("especialidades"),
            usuario=request.user,
        )


class MiPerfilAPIView(APIPrivadaMaestros):
    def get(self, request):
        perfil = self.perfil_propio(request)
        return Response(PerfilMaestroSerializer(perfil, context={"request": request}).data)

    def post(self, request):
        if PerfilMaestro.objects.filter(usuario=request.user).exists():
            return Response(
                {"detail": "Ya tienes un perfil profesional."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = PerfilMaestroSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        perfil = serializer.save(usuario=request.user)
        return Response(
            PerfilMaestroSerializer(perfil, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def patch(self, request):
        perfil = self.perfil_propio(request)
        serializer = PerfilMaestroSerializer(
            perfil,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        perfil = serializer.save()
        return Response(PerfilMaestroSerializer(perfil, context={"request": request}).data)


class EnviarRevisionAPIView(APIPrivadaMaestros):
    def post(self, request):
        perfil = self.perfil_propio(request)
        if perfil.estado == PerfilMaestro.Estado.SUSPENDIDO:
            return Response(
                {"detail": "Un perfil suspendido debe ser habilitado por administración."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        perfil.estado = PerfilMaestro.Estado.PENDIENTE
        perfil.observacion_admin = ""
        perfil.fecha_aprobacion = None
        perfil.save(
            update_fields=[
                "estado",
                "observacion_admin",
                "fecha_aprobacion",
                "actualizado_en",
            ]
        )
        return Response(PerfilMaestroSerializer(perfil, context={"request": request}).data)


class TrabajosAPIView(APIPrivadaMaestros):
    def get(self, request):
        perfil = self.perfil_propio(request)
        trabajos = perfil.trabajos.prefetch_related("especialidades", "imagenes")
        return Response(
            TrabajoRealizadoSerializer(
                trabajos,
                many=True,
                context={"request": request, "maestro": perfil},
            ).data
        )

    def post(self, request):
        perfil = self.perfil_propio(request)
        serializer = TrabajoRealizadoSerializer(
            data=request.data,
            context={"request": request, "maestro": perfil},
        )
        serializer.is_valid(raise_exception=True)
        trabajo = serializer.save(maestro=perfil)
        return Response(
            TrabajoRealizadoSerializer(
                trabajo,
                context={"request": request, "maestro": perfil},
            ).data,
            status=status.HTTP_201_CREATED,
        )


class TrabajoDetalleAPIView(APIPrivadaMaestros):
    def trabajo_propio(self, request, pk):
        return get_object_or_404(
            TrabajoRealizado.objects.prefetch_related("especialidades", "imagenes"),
            pk=pk,
            maestro__usuario=request.user,
        )

    def patch(self, request, pk):
        trabajo = self.trabajo_propio(request, pk)
        serializer = TrabajoRealizadoSerializer(
            trabajo,
            data=request.data,
            partial=True,
            context={"request": request, "maestro": trabajo.maestro},
        )
        serializer.is_valid(raise_exception=True)
        trabajo = serializer.save()
        return Response(
            TrabajoRealizadoSerializer(
                trabajo,
                context={"request": request, "maestro": trabajo.maestro},
            ).data
        )

    def delete(self, request, pk):
        trabajo = self.trabajo_propio(request, pk)
        trabajo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ImagenesTrabajoAPIView(APIPrivadaMaestros):
    def post(self, request, pk):
        trabajo = get_object_or_404(
            TrabajoRealizado,
            pk=pk,
            maestro__usuario=request.user,
        )
        imagenes = request.FILES.getlist("imagenes")
        serializer = CargaImagenesTrabajoSerializer(
            data={"imagenes": imagenes},
            context={"request": request, "trabajo": trabajo},
        )
        serializer.is_valid(raise_exception=True)
        creadas = serializer.save()
        return Response(
            ImagenTrabajoSerializer(creadas, many=True, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class ImagenDetalleAPIView(APIPrivadaMaestros):
    def delete(self, request, pk):
        imagen = get_object_or_404(
            ImagenTrabajoRealizado,
            pk=pk,
            trabajo__maestro__usuario=request.user,
        )
        imagen.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class EstadoMaestroAdminAPIView(APIView):
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAdminUser,)

    def patch(self, request, pk):
        perfil = get_object_or_404(PerfilMaestro, pk=pk)
        if perfil.usuario_id == request.user.id:
            return Response(
                {"detail": "No puedes revisar tu propio perfil profesional."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = CambioEstadoMaestroSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        perfil.observacion_admin = serializer.validated_data.get(
            "observacion_admin", perfil.observacion_admin
        ).strip()
        perfil.save(update_fields=["observacion_admin", "actualizado_en"])
        perfil.cambiar_estado(serializer.validated_data["estado"])
        return Response(PerfilMaestroSerializer(perfil, context={"request": request}).data)


class MaestrosPublicosAPIView(ListAPIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    serializer_class = PerfilMaestroPublicoSerializer

    def get_queryset(self):
        return (
            PerfilMaestro.objects.filter(estado=PerfilMaestro.Estado.APROBADO)
            .select_related("usuario")
            .prefetch_related("especialidades")
        )


class MaestroPublicoDetalleAPIView(RetrieveAPIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    serializer_class = PerfilMaestroPublicoSerializer

    def get_queryset(self):
        return (
            PerfilMaestro.objects.filter(estado=PerfilMaestro.Estado.APROBADO)
            .select_related("usuario")
            .prefetch_related("especialidades")
        )
