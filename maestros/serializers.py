from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .chile import COMUNA_REGION, COMUNAS_CHOICES, REGIONES_COMUNAS, comunas_de_region
from .models import (
    MAX_IMAGENES_POR_TRABAJO,
    MAX_TAMANO_IMAGEN,
    DocumentoMaestro,
    Especialidad,
    ImagenTrabajoRealizado,
    LicenciaMaestro,
    PerfilMaestro,
    TrabajoRealizado,
    validar_archivo_documental,
    validar_fecha_trabajo,
)


class ImagenLimitadaField(serializers.ImageField):
    def to_internal_value(self, data):
        if getattr(data, "size", 0) > MAX_TAMANO_IMAGEN:
            raise serializers.ValidationError("La imagen debe pesar como máximo 5 MB.")
        return super().to_internal_value(data)


class ComunasTrabajoField(serializers.ListField):
    child = serializers.ChoiceField(choices=COMUNAS_CHOICES)

    def to_representation(self, value):
        if not value:
            return []
        if isinstance(value, str):
            return [comuna.strip() for comuna in value.split(",") if comuna.strip()]
        return super().to_representation(value)


class EspecialidadPublicaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Especialidad
        fields = ("id", "nombre")


class ImagenTrabajoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImagenTrabajoRealizado
        fields = ("id", "imagen", "creada_en")
        read_only_fields = fields


class ArchivoDocumentalField(serializers.FileField):
    def to_internal_value(self, data):
        archivo = super().to_internal_value(data)
        try:
            validar_archivo_documental(archivo)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from error
        return archivo


class DocumentoMaestroSerializer(serializers.ModelSerializer):
    archivo = ArchivoDocumentalField(write_only=True)
    nombre_archivo = serializers.SerializerMethodField()
    descarga_url = serializers.SerializerMethodField()

    class Meta:
        model = DocumentoMaestro
        fields = (
            "id",
            "tipo",
            "archivo",
            "nombre_archivo",
            "descarga_url",
            "estado_revision",
            "observacion_admin",
            "subido_en",
            "actualizado_en",
            "revisado_en",
        )
        read_only_fields = (
            "id",
            "nombre_archivo",
            "descarga_url",
            "estado_revision",
            "observacion_admin",
            "subido_en",
            "actualizado_en",
            "revisado_en",
        )

    def get_nombre_archivo(self, obj):
        return obj.archivo.name.rsplit("/", 1)[-1] if obj.archivo else ""

    def get_descarga_url(self, obj):
        from django.urls import reverse

        url = reverse("maestros:descargar_documento", args=[obj.pk])
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request else url


class LicenciaMaestroSerializer(serializers.ModelSerializer):
    archivo = ArchivoDocumentalField(write_only=True)
    nombre_archivo = serializers.SerializerMethodField()
    descarga_url = serializers.SerializerMethodField()

    class Meta:
        model = LicenciaMaestro
        fields = (
            "id",
            "tipo_licencia",
            "clase",
            "numero_licencia",
            "archivo",
            "nombre_archivo",
            "descarga_url",
            "estado_revision",
            "observacion_admin",
            "subido_en",
            "actualizado_en",
            "revisado_en",
        )
        read_only_fields = (
            "id",
            "nombre_archivo",
            "descarga_url",
            "estado_revision",
            "observacion_admin",
            "subido_en",
            "actualizado_en",
            "revisado_en",
        )

    def validate_tipo_licencia(self, tipo):
        perfil = self.context.get("perfil")
        if perfil and tipo not in perfil.tipos_licencia_requeridos():
            raise serializers.ValidationError(
                "Tu perfil no requiere este tipo de licencia profesional."
            )
        return tipo

    def validate(self, attrs):
        tipo = attrs.get("tipo_licencia", getattr(self.instance, "tipo_licencia", ""))
        clase = attrs.get("clase", getattr(self.instance, "clase", ""))
        permitidas = {
            Especialidad.TipoLicencia.SEC_ELECTRICA: {"A", "B", "C", "D"},
            Especialidad.TipoLicencia.SEC_GAS: {"1", "2", "3"},
        }
        if clase not in permitidas.get(tipo, set()):
            raise serializers.ValidationError(
                {"clase": "La clase no corresponde al tipo de licencia seleccionado."}
            )
        return attrs

    def get_nombre_archivo(self, obj):
        return obj.archivo.name.rsplit("/", 1)[-1] if obj.archivo else ""

    def get_descarga_url(self, obj):
        from django.urls import reverse

        url = reverse("maestros:descargar_licencia", args=[obj.pk])
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request else url


class RevisionDocumentalSerializer(serializers.Serializer):
    estado_revision = serializers.ChoiceField(
        choices=DocumentoMaestro.EstadoRevision.choices
    )
    observacion_admin = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=2000,
    )

    def validate(self, attrs):
        observacion = attrs.get("observacion_admin", "").strip()
        if (
            attrs["estado_revision"] == DocumentoMaestro.EstadoRevision.RECHAZADO
            and len(observacion) < 10
        ):
            raise serializers.ValidationError(
                {
                    "observacion_admin": (
                        "Debes indicar un motivo de rechazo de al menos 10 caracteres."
                    )
                }
            )
        attrs["observacion_admin"] = observacion
        return attrs


class PerfilMaestroSerializer(serializers.ModelSerializer):
    foto = ImagenLimitadaField(required=False, allow_null=True)
    especialidades = serializers.PrimaryKeyRelatedField(
        many=True,
        allow_empty=False,
        queryset=Especialidad.objects.filter(activa=True),
    )
    comunas_trabajo = ComunasTrabajoField(
        source="zonas_trabajo",
        allow_empty=False,
    )
    region_nombre = serializers.SerializerMethodField()

    class Meta:
        model = PerfilMaestro
        fields = (
            "id",
            "foto",
            "descripcion_profesional",
            "anos_experiencia",
            "especialidades",
            "region",
            "region_nombre",
            "comunas_trabajo",
            "disponible",
            "estado",
            "observacion_admin",
            "fecha_aprobacion",
            "creado_en",
            "actualizado_en",
        )
        read_only_fields = (
            "id",
            "estado",
            "observacion_admin",
            "fecha_aprobacion",
            "creado_en",
            "actualizado_en",
        )

    def get_region_nombre(self, obj):
        return REGIONES_COMUNAS.get(obj.region, (obj.region, ()))[0]

    def validate(self, attrs):
        region = attrs.get("region", getattr(self.instance, "region", None))
        comunas = attrs.get("zonas_trabajo")
        if comunas is None and self.instance:
            comunas = [
                comuna.strip()
                for comuna in self.instance.zonas_trabajo.split(",")
                if comuna.strip()
            ]
        permitidas = set(comunas_de_region(region))
        if not region or not comunas or any(comuna not in permitidas for comuna in comunas):
            raise serializers.ValidationError(
                {
                    "comunas_trabajo": (
                        "Selecciona una o más comunas pertenecientes a la región indicada."
                    )
                }
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        especialidades = validated_data.pop("especialidades")
        comunas = validated_data.pop("zonas_trabajo")
        validated_data["comuna"] = comunas[0]
        validated_data["zonas_trabajo"] = ", ".join(comunas)
        validated_data["estado"] = PerfilMaestro.Estado.BORRADOR
        perfil = PerfilMaestro.objects.create(**validated_data)
        perfil.especialidades.set(especialidades)
        return perfil

    @transaction.atomic
    def update(self, instance, validated_data):
        especialidades = validated_data.pop("especialidades", None)
        comunas = validated_data.pop("zonas_trabajo", None)

        sensibles_cambiados = any(
            campo in validated_data and getattr(instance, campo) != validated_data[campo]
            for campo in (
                "descripcion_profesional",
                "anos_experiencia",
                "region",
            )
        )
        if especialidades is not None:
            actuales = set(instance.especialidades.values_list("id", flat=True))
            sensibles_cambiados = sensibles_cambiados or actuales != {
                especialidad.id for especialidad in especialidades
            }
        if comunas is not None:
            actuales = [
                comuna.strip()
                for comuna in instance.zonas_trabajo.split(",")
                if comuna.strip()
            ]
            sensibles_cambiados = sensibles_cambiados or actuales != list(comunas)
            validated_data["comuna"] = comunas[0]
            validated_data["zonas_trabajo"] = ", ".join(comunas)

        for campo, valor in validated_data.items():
            setattr(instance, campo, valor)
        instance.save()
        if especialidades is not None:
            instance.especialidades.set(especialidades)
        if sensibles_cambiados:
            instance.volver_a_revision_por_edicion()
        return instance


class TrabajoRealizadoSerializer(serializers.ModelSerializer):
    especialidades = serializers.PrimaryKeyRelatedField(
        many=True,
        allow_empty=False,
        queryset=Especialidad.objects.filter(activa=True),
    )
    imagenes = ImagenTrabajoSerializer(many=True, read_only=True)

    class Meta:
        model = TrabajoRealizado
        fields = (
            "id",
            "titulo",
            "descripcion",
            "especialidades",
            "comuna",
            "fecha",
            "publicado",
            "imagenes",
            "creado_en",
            "actualizado_en",
        )
        read_only_fields = ("id", "imagenes", "creado_en", "actualizado_en")

    def validate_especialidades(self, especialidades):
        maestro = self.context.get("maestro")
        if maestro:
            permitidas = set(maestro.especialidades.filter(activa=True).values_list("id", flat=True))
            if any(especialidad.id not in permitidas for especialidad in especialidades):
                raise serializers.ValidationError(
                    "Solo puedes seleccionar especialidades activas de tu perfil."
                )
        return especialidades

    def validate_comuna(self, comuna):
        if comuna not in COMUNA_REGION:
            raise serializers.ValidationError("Selecciona una comuna válida de Chile.")
        return comuna

    def validate_fecha(self, fecha):
        if not fecha:
            return fecha
        try:
            validar_fecha_trabajo(fecha)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages) from error

        maestro = self.context.get("maestro")
        if maestro:
            hoy = timezone.localdate()
            anos = max(1, maestro.anos_experiencia)
            fecha_minima = hoy.replace(year=hoy.year - min(anos, 60), month=1, day=1)
            if fecha < fecha_minima:
                raise serializers.ValidationError(
                    "La fecha no coincide con los años de experiencia indicados en tu perfil."
                )
        return fecha


class CargaImagenesTrabajoSerializer(serializers.Serializer):
    imagenes = serializers.ListField(
        child=ImagenLimitadaField(),
        allow_empty=False,
        max_length=MAX_IMAGENES_POR_TRABAJO,
    )

    def validate_imagenes(self, imagenes):
        trabajo = self.context["trabajo"]
        if trabajo.imagenes.count() + len(imagenes) > MAX_IMAGENES_POR_TRABAJO:
            raise serializers.ValidationError(
                f"Cada trabajo puede tener como máximo {MAX_IMAGENES_POR_TRABAJO} imágenes."
            )
        return imagenes

    def create(self, validated_data):
        trabajo = self.context["trabajo"]
        return ImagenTrabajoRealizado.objects.bulk_create(
            [
                ImagenTrabajoRealizado(trabajo=trabajo, imagen=imagen)
                for imagen in validated_data["imagenes"]
            ]
        )


class CambioEstadoMaestroSerializer(serializers.Serializer):
    estado = serializers.ChoiceField(
        choices=(
            PerfilMaestro.Estado.APROBADO,
            PerfilMaestro.Estado.RECHAZADO,
            PerfilMaestro.Estado.SUSPENDIDO,
        )
    )
    observacion_admin = serializers.CharField(required=False, allow_blank=True, max_length=2000)

    def validate(self, attrs):
        observacion = attrs.get("observacion_admin", "").strip()
        perfil = self.context.get("perfil")
        if (
            attrs["estado"]
            in {PerfilMaestro.Estado.APROBADO, PerfilMaestro.Estado.RECHAZADO}
            and perfil is not None
            and perfil.estado != PerfilMaestro.Estado.PENDIENTE
        ):
            raise serializers.ValidationError(
                {
                    "estado": (
                        "Solo puedes aprobar o rechazar perfiles pendientes de revisión. "
                        "El maestro debe actualizar y volver a enviar su perfil."
                    )
                }
            )
        if (
            attrs["estado"] == PerfilMaestro.Estado.APROBADO
            and perfil is not None
            and not perfil.puede_ser_aprobado()
        ):
            raise serializers.ValidationError(
                {
                    "estado": [
                        "No se puede aprobar este maestro.",
                        *perfil.motivos_documentacion_pendiente(),
                    ]
                }
            )
        if (
            attrs["estado"] == PerfilMaestro.Estado.SUSPENDIDO
            and perfil is not None
            and perfil.estado != PerfilMaestro.Estado.APROBADO
        ):
            raise serializers.ValidationError(
                {"estado": "Solo puedes suspender un perfil que se encuentre aprobado."}
            )
        if (
            attrs["estado"]
            in {
                PerfilMaestro.Estado.RECHAZADO,
                PerfilMaestro.Estado.SUSPENDIDO,
            }
            and len(observacion) < 10
        ):
            raise serializers.ValidationError(
                {
                    "observacion_admin": (
                        "Debes escribir una observación de al menos 10 caracteres "
                        "para rechazar o suspender el perfil."
                    )
                }
            )
        attrs["observacion_admin"] = observacion
        return attrs


class TrabajoPublicoSerializer(serializers.ModelSerializer):
    especialidades = EspecialidadPublicaSerializer(many=True, read_only=True)
    imagenes = ImagenTrabajoSerializer(many=True, read_only=True)
    portada_url = serializers.SerializerMethodField()

    class Meta:
        model = TrabajoRealizado
        fields = (
            "id",
            "titulo",
            "descripcion",
            "especialidades",
            "comuna",
            "fecha",
            "imagenes",
            "portada_url",
        )

    def get_portada_url(self, obj):
        url = obj.portada_publica_url
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request else url


class PerfilMaestroPublicoSerializer(serializers.ModelSerializer):
    foto = serializers.SerializerMethodField()
    foto_fallback_url = serializers.SerializerMethodField()
    nombre = serializers.SerializerMethodField()
    especialidades = EspecialidadPublicaSerializer(many=True, read_only=True)
    comunas_trabajo = ComunasTrabajoField(source="zonas_trabajo", read_only=True)
    region_nombre = serializers.SerializerMethodField()
    trabajos = serializers.SerializerMethodField()

    class Meta:
        model = PerfilMaestro
        fields = (
            "id",
            "nombre",
            "foto",
            "foto_fallback_url",
            "descripcion_profesional",
            "anos_experiencia",
            "especialidades",
            "region",
            "region_nombre",
            "comunas_trabajo",
            "disponible",
            "trabajos",
        )

    def get_nombre(self, obj):
        return obj.usuario.get_full_name() or obj.usuario.username

    def _url_absoluta(self, url):
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request else url

    def get_foto(self, obj):
        return self._url_absoluta(obj.foto_publica_url)

    def get_foto_fallback_url(self, obj):
        return self._url_absoluta(obj.foto_fallback_url)

    def get_region_nombre(self, obj):
        return REGIONES_COMUNAS.get(obj.region, (obj.region, ()))[0]

    def get_trabajos(self, obj):
        trabajos = obj.trabajos.filter(publicado=True).prefetch_related(
            "especialidades", "imagenes"
        )
        return TrabajoPublicoSerializer(trabajos, many=True, context=self.context).data
