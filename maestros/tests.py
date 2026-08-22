import shutil
import tempfile
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Especialidad, PerfilMaestro, TrabajoRealizado


TEST_MEDIA_ROOT = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class MaestrosFaseUnoTests(TestCase):
    contador_usuarios = 0
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.User = get_user_model()
        self.especialidad, _ = Especialidad.objects.get_or_create(nombre="Carpintería", defaults={"activa": True})

    def crear_usuario(self, username, verificado=True, staff=False):
        type(self).contador_usuarios += 1
        numero = 10000000 + type(self).contador_usuarios
        return self.User.objects.create_user(
            username=username,
            password="ClaveSegura2398!",
            email=f"{username}@example.com",
            rut=f"{numero}-{type(self).contador_usuarios % 9}",
            telefono="+56912345678",
            email_confirmado=verificado,
            is_active=True,
            is_staff=staff,
        )

    def crear_perfil(self, usuario, estado=PerfilMaestro.Estado.BORRADOR):
        perfil = PerfilMaestro.objects.create(
            usuario=usuario,
            descripcion_profesional="Especialista en proyectos residenciales.",
            anos_experiencia=8,
            region="RM",
            comuna="Maipú",
            zonas_trabajo="Maipú",
            estado=estado,
        )
        perfil.especialidades.add(self.especialidad)
        return perfil

    def test_usuario_no_verificado_no_puede_crear_perfil(self):
        usuario = self.crear_usuario("novalido", verificado=False)
        self.client.force_login(usuario)
        respuesta = self.client.post(
            reverse("maestros:crear_perfil"),
            {
                "descripcion_profesional": "Experiencia suficiente para una descripción.",
                "anos_experiencia": 3,
                "especialidades": [self.especialidad.id],
                "region": "RM",
                "comunas_trabajo": ["Maipú"],
                "disponible": "on",
            },
        )
        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(PerfilMaestro.objects.filter(usuario=usuario).exists())

    def test_solo_perfiles_aprobados_son_publicos(self):
        perfiles = {}
        for indice, estado in enumerate(PerfilMaestro.Estado.values, start=1):
            usuario = self.crear_usuario(f"maestro{indice}")
            perfiles[estado] = self.crear_perfil(usuario, estado)

        respuesta = self.client.get(reverse("maestros:lista"))
        self.assertContains(respuesta, perfiles[PerfilMaestro.Estado.APROBADO].usuario.username)
        for estado in (
            PerfilMaestro.Estado.BORRADOR,
            PerfilMaestro.Estado.PENDIENTE,
            PerfilMaestro.Estado.RECHAZADO,
            PerfilMaestro.Estado.SUSPENDIDO,
        ):
            self.assertNotContains(respuesta, perfiles[estado].usuario.username)
            detalle = self.client.get(reverse("maestros:detalle", args=[perfiles[estado].id]))
            self.assertEqual(detalle.status_code, 404)
        aprobado = self.client.get(reverse("maestros:detalle", args=[perfiles[PerfilMaestro.Estado.APROBADO].id]))
        self.assertEqual(aprobado.status_code, 200)

    def test_usuario_no_puede_aprobar_su_perfil(self):
        usuario = self.crear_usuario("postulante", staff=True)
        perfil = self.crear_perfil(usuario, PerfilMaestro.Estado.PENDIENTE)
        self.client.force_login(usuario)
        respuesta = self.client.post(
            reverse("maestros:admin_estado", args=[perfil.id]),
            {"estado": PerfilMaestro.Estado.APROBADO},
        )
        self.assertEqual(respuesta.status_code, 403)
        perfil.refresh_from_db()
        self.assertEqual(perfil.estado, PerfilMaestro.Estado.PENDIENTE)

    def test_admin_puede_aprobar_y_guarda_fecha(self):
        usuario = self.crear_usuario("solicitante")
        perfil = self.crear_perfil(usuario, PerfilMaestro.Estado.PENDIENTE)
        admin = self.crear_usuario("administrador", staff=True)
        self.client.force_login(admin)
        respuesta = self.client.post(
            reverse("maestros:admin_estado", args=[perfil.id]),
            {"estado": PerfilMaestro.Estado.APROBADO, "observacion_admin": "Antecedentes revisados."},
        )
        self.assertRedirects(respuesta, reverse("maestros:admin_revision"))
        perfil.refresh_from_db()
        self.assertEqual(perfil.estado, PerfilMaestro.Estado.APROBADO)
        self.assertIsNotNone(perfil.fecha_aprobacion)

    def test_maestro_solo_edita_su_perfil_y_trabajos(self):
        propietario = self.crear_usuario("propietario")
        intruso = self.crear_usuario("intruso")
        perfil_propietario = self.crear_perfil(propietario)
        perfil_intruso = self.crear_perfil(intruso)
        trabajo = TrabajoRealizado.objects.create(
            maestro=perfil_propietario,
            titulo="Repisa terminada",
            descripcion="Repisa de madera instalada.",
            comuna="Maipú",
        )
        trabajo.especialidades.add(self.especialidad)
        self.client.force_login(intruso)
        respuesta = self.client.post(
            reverse("maestros:editar_trabajo", args=[trabajo.id]),
            {
                "titulo": "Intento de cambio",
                "descripcion": "No debe guardarse.",
                "especialidades": [self.especialidad.id],
                "comuna": "Santiago",
                "publicado": "on",
            },
        )
        self.assertEqual(respuesta.status_code, 404)
        trabajo.refresh_from_db()
        self.assertEqual(trabajo.titulo, "Repisa terminada")

        self.client.post(
            reverse("maestros:editar_perfil"),
            {
                "descripcion_profesional": "Actualización del perfil propio.",
                "anos_experiencia": 5,
                "especialidades": [self.especialidad.id],
                "region": "RM",
                "comunas_trabajo": ["La Florida", "Puente Alto"],
                "disponible": "on",
            },
        )
        perfil_intruso.refresh_from_db()
        perfil_propietario.refresh_from_db()
        self.assertEqual(perfil_intruso.comuna, "La Florida")
        self.assertEqual(perfil_intruso.zonas_trabajo, "La Florida, Puente Alto")
        self.assertEqual(perfil_propietario.comuna, "Maipú")

    def test_perfil_permite_varias_especialidades_y_comunas_de_una_region(self):
        usuario = self.crear_usuario("multioficio")
        electricidad, _ = Especialidad.objects.get_or_create(nombre="Electricidad", defaults={"activa": True})
        self.client.force_login(usuario)
        respuesta = self.client.post(
            reverse("maestros:crear_perfil"),
            {
                "descripcion_profesional": "Experiencia en terminaciones e instalaciones.",
                "anos_experiencia": 7,
                "especialidades": [self.especialidad.id, electricidad.id],
                "region": "RM",
                "comunas_trabajo": ["Maipú", "Cerrillos"],
                "disponible": "on",
            },
        )
        self.assertRedirects(respuesta, reverse("maestros:panel"))
        perfil = PerfilMaestro.objects.get(usuario=usuario)
        self.assertEqual(perfil.especialidades.count(), 2)
        self.assertEqual(perfil.zonas_trabajo, "Maipú, Cerrillos")

    def test_trabajos_no_publicados_no_aparecen(self):
        usuario = self.crear_usuario("publico")
        perfil = self.crear_perfil(usuario, PerfilMaestro.Estado.APROBADO)
        visible = TrabajoRealizado.objects.create(
            maestro=perfil,
            titulo="Trabajo visible",
            descripcion="Resultado publicado.",
            comuna="Maipú",
            publicado=True,
        )
        visible.especialidades.add(self.especialidad)
        privado = TrabajoRealizado.objects.create(
            maestro=perfil,
            titulo="Trabajo privado",
            descripcion="Resultado no publicado.",
            comuna="Maipú",
            publicado=False,
        )
        privado.especialidades.add(self.especialidad)
        respuesta = self.client.get(reverse("maestros:detalle", args=[perfil.id]))
        self.assertContains(respuesta, "Trabajo visible")
        self.assertNotContains(respuesta, "Trabajo privado")

    def test_trabajo_no_acepta_fecha_futura(self):
        usuario = self.crear_usuario("fechafutura")
        perfil = self.crear_perfil(usuario)
        self.client.force_login(usuario)
        respuesta = self.client.post(
            reverse("maestros:crear_trabajo"),
            {
                "titulo": "Trabajo del futuro",
                "descripcion": "Esta fecha no debe aceptarse.",
                "especialidades": [self.especialidad.id],
                "comuna": "Maipú",
                "fecha": (timezone.localdate() + timedelta(days=1)).isoformat(),
                "publicado": "on",
            },
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "no puede estar en el futuro")
        self.assertFalse(TrabajoRealizado.objects.filter(titulo="Trabajo del futuro").exists())

    def test_trabajo_respeta_experiencia_y_permite_varias_especialidades(self):
        usuario = self.crear_usuario("trabajomultiple")
        perfil = self.crear_perfil(usuario)
        electricidad, _ = Especialidad.objects.get_or_create(nombre="Electricidad", defaults={"activa": True})
        perfil.especialidades.add(electricidad)
        self.client.force_login(usuario)

        fecha_antigua = timezone.localdate().replace(year=timezone.localdate().year - 20)
        respuesta_invalida = self.client.post(
            reverse("maestros:crear_trabajo"),
            {
                "titulo": "Trabajo demasiado antiguo",
                "descripcion": "No coincide con la experiencia declarada.",
                "especialidades": [self.especialidad.id],
                "comuna": "Maipú",
                "fecha": fecha_antigua.isoformat(),
                "publicado": "on",
            },
        )
        self.assertContains(respuesta_invalida, "no coincide con los años de experiencia")

        respuesta_valida = self.client.post(
            reverse("maestros:crear_trabajo"),
            {
                "titulo": "Instalación y terminaciones",
                "descripcion": "Proyecto terminado correctamente.",
                "especialidades": [self.especialidad.id, electricidad.id],
                "comuna": "Maipú",
                "fecha": timezone.localdate().isoformat(),
                "publicado": "on",
            },
        )
        self.assertRedirects(respuesta_valida, reverse("maestros:trabajos"))
        trabajo = TrabajoRealizado.objects.get(titulo="Instalación y terminaciones")
        self.assertEqual(trabajo.especialidades.count(), 2)
