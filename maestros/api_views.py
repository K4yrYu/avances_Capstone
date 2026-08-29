from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    DocumentoMaestro,
    ImagenTrabajoRealizado,
    LicenciaMaestro,
    ObservacionMaestro,
    PerfilMaestro,
    TrabajoRealizado,
)
from .permissions import IsActiveVerifiedUser
from .serializers import (
    CambioEstadoMaestroSerializer,
    CargaImagenesTrabajoSerializer,
    DocumentoMaestroSerializer,
    ImagenTrabajoSerializer,
    LicenciaMaestroSerializer,
    PerfilMaestroPublicoSerializer,
    PerfilMaestroSerializer,
    RevisionDocumentalSerializer,
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
        try:
            perfil.enviar_a_revision()
        except DjangoValidationError as error:
            return Response(
                {"detail": " ".join(error.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(PerfilMaestroSerializer(perfil, context={"request": request}).data)


class DocumentosPropiosAPIView(APIPrivadaMaestros):
    def get(self, request):
        perfil = self.perfil_propio(request)
        return Response(
            DocumentoMaestroSerializer(
                perfil.documentos.all(),
                many=True,
                context={"request": request},
            ).data
        )

    @transaction.atomic
    def post(self, request):
        perfil = self.perfil_propio(request)
        serializer = DocumentoMaestroSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        tipo = serializer.validated_data["tipo"]
        archivo = serializer.validated_data["archivo"]
        documento, creado = DocumentoMaestro.objects.get_or_create(
            perfil=perfil,
            tipo=tipo,
            defaults={"archivo": archivo},
        )
        if creado:
            documento.full_clean()
            documento.save()
            perfil.volver_a_revision_por_edicion()
        else:
            documento.preparar_reemplazo(archivo)
        return Response(
            DocumentoMaestroSerializer(
                documento,
                context={"request": request},
            ).data,
            status=status.HTTP_201_CREATED if creado else status.HTTP_200_OK,
        )


class LicenciasPropiasAPIView(APIPrivadaMaestros):
    def get(self, request):
        perfil = self.perfil_propio(request)
        return Response(
            LicenciaMaestroSerializer(
                perfil.licencias.all(),
                many=True,
                context={"request": request, "perfil": perfil},
            ).data
        )

    @transaction.atomic
    def post(self, request):
        perfil = self.perfil_propio(request)
        serializer = LicenciaMaestroSerializer(
            data=request.data,
            context={"request": request, "perfil": perfil},
        )
        serializer.is_valid(raise_exception=True)
        datos = serializer.validated_data
        tipo = datos["tipo_licencia"]
        licencia, creado = LicenciaMaestro.objects.get_or_create(
            perfil=perfil,
            tipo_licencia=tipo,
            defaults={
                "clase": datos["clase"],
                "numero_licencia": datos["numero_licencia"],
                "archivo": datos["archivo"],
            },
        )
        if creado:
            licencia.full_clean()
            licencia.save()
            perfil.volver_a_revision_por_edicion()
        else:
            licencia.preparar_reemplazo(
                datos["archivo"],
                datos["clase"],
                datos["numero_licencia"],
            )
        return Response(
            LicenciaMaestroSerializer(
                licencia,
                context={"request": request, "perfil": perfil},
            ).data,
            status=status.HTTP_201_CREATED if creado else status.HTTP_200_OK,
        )


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
        serializer = CambioEstadoMaestroSerializer(
            data=request.data,
            context={"perfil": perfil},
        )
        serializer.is_valid(raise_exception=True)
        perfil.observacion_admin = serializer.validated_data.get(
            "observacion_admin", perfil.observacion_admin
        ).strip()
        perfil.save(update_fields=["observacion_admin", "actualizado_en"])
        nuevo_estado = serializer.validated_data["estado"]
        try:
            perfil.cambiar_estado(nuevo_estado)
        except DjangoValidationError as error:
            return Response(
                {"detail": " ".join(error.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if perfil.observacion_admin:
            tipos = {
                PerfilMaestro.Estado.APROBADO: ObservacionMaestro.Tipo.APROBACION,
                PerfilMaestro.Estado.RECHAZADO: ObservacionMaestro.Tipo.RECHAZO,
                PerfilMaestro.Estado.SUSPENDIDO: ObservacionMaestro.Tipo.SUSPENSION,
            }
            ObservacionMaestro.objects.create(
                perfil=perfil,
                tipo=tipos[nuevo_estado],
                texto=perfil.observacion_admin,
                registrada_por=request.user,
            )
        return Response(PerfilMaestroSerializer(perfil, context={"request": request}).data)


class RevisionDocumentoAdminAPIView(APIView):
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAdminUser,)

    def patch(self, request, pk):
        documento = get_object_or_404(DocumentoMaestro, pk=pk)
        serializer = RevisionDocumentalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        documento.revisar(
            serializer.validated_data["estado_revision"],
            request.user,
            serializer.validated_data.get("observacion_admin", ""),
        )
        return Response(
            DocumentoMaestroSerializer(
                documento,
                context={"request": request},
            ).data
        )


class RevisionLicenciaAdminAPIView(APIView):
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAdminUser,)

    def patch(self, request, pk):
        licencia = get_object_or_404(LicenciaMaestro, pk=pk)
        serializer = RevisionDocumentalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        licencia.revisar(
            serializer.validated_data["estado_revision"],
            request.user,
            serializer.validated_data.get("observacion_admin", ""),
        )
        return Response(
            LicenciaMaestroSerializer(
                licencia,
                context={"request": request, "perfil": licencia.perfil},
            ).data
        )


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
