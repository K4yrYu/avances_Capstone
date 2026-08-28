from datetime import date

from django.contrib.auth.hashers import make_password
from django.db import migrations
from django.utils import timezone


MAESTROS_DEMO = (
    {
        "username": "demo_pedro_gonzalez",
        "nombre": "Pedro",
        "apellido": "González",
        "especialidad": "Carpintería",
        "experiencia": 8,
        "comunas": ("Maipú", "Cerrillos"),
        "descripcion": "Carpintero especializado en muebles a medida, repisas e instalaciones residenciales.",
        "trabajos": (
            ("Instalación de repisa mural", "Instalación de repisa de madera con soportes metálicos y fijaciones adecuadas para muro domiciliario.", "Maipú", date(2025, 11, 18)),
            ("Mueble organizador a medida", "Fabricación e instalación de mueble organizador de madera para espacio interior.", "Cerrillos", date(2025, 8, 7)),
        ),
    },
    {
        "username": "demo_carlos_munoz",
        "nombre": "Carlos",
        "apellido": "Muñoz",
        "especialidad": "Carpintería",
        "experiencia": 10,
        "comunas": ("Santiago", "Estación Central"),
        "descripcion": "Carpintero con experiencia en renovación, ajuste e instalación de mobiliario de cocina.",
        "trabajos": (("Renovación de mueble de cocina", "Restauración de puertas, cubiertas y módulos para extender la vida útil del mobiliario de cocina.", "Santiago", date(2025, 9, 12)),),
    },
    {
        "username": "demo_maria_soto",
        "nombre": "María",
        "apellido": "Soto",
        "especialidad": "Pintura",
        "experiencia": 7,
        "comunas": ("Maipú", "Cerrillos"),
        "descripcion": "Pintora dedicada a interiores residenciales, preparación de superficies y terminaciones limpias.",
        "trabajos": (
            ("Pintura interior de dormitorio", "Preparación y aplicación de pintura interior en dormitorio residencial.", "Maipú", date(2025, 10, 21)),
            ("Renovación de living y comedor", "Pintura de muros interiores con preparación previa de superficies y terminaciones.", "Cerrillos", date(2025, 7, 15)),
        ),
    },
    {
        "username": "demo_jorge_rojas",
        "nombre": "Jorge",
        "apellido": "Rojas",
        "especialidad": "Pintura",
        "experiencia": 12,
        "comunas": ("Providencia", "Ñuñoa"),
        "descripcion": "Especialista en pintura de fachadas, departamentos y protección de superficies exteriores.",
        "trabajos": (
            ("Pintura exterior de fachada", "Lavado, reparación menor y aplicación de revestimiento protector para fachada residencial.", "Providencia", date(2025, 12, 3)),
            ("Renovación de departamento", "Preparación y pintura completa de muros y cielos en departamento habitado.", "Ñuñoa", date(2025, 6, 26)),
        ),
    },
    {
        "username": "demo_daniela_silva",
        "nombre": "Daniela",
        "apellido": "Silva",
        "especialidad": "Pintura",
        "experiencia": 5,
        "comunas": ("San Miguel", "La Cisterna"),
        "descripcion": "Pintora residencial enfocada en ambientes interiores y terminaciones uniformes.",
        "trabajos": (("Pintura interior de departamento", "Preparación, sellado y pintura de espacios interiores de un departamento residencial.", "San Miguel", date(2025, 11, 4)),),
    },
    {
        "username": "demo_luis_perez",
        "nombre": "Luis",
        "apellido": "Pérez",
        "especialidad": "Gasfitería",
        "experiencia": 9,
        "comunas": ("Maipú", "Pudahuel"),
        "descripcion": "Gasfíter para reparaciones domiciliarias, filtraciones, grifería y mantención sanitaria.",
        "trabajos": (
            ("Reparación de filtración domiciliaria", "Detección de fuga, reemplazo de conexión y prueba de funcionamiento en red domiciliaria.", "Maipú", date(2025, 10, 8)),
            ("Cambio de grifería de cocina", "Retiro de grifería antigua e instalación sellada de una nueva combinación de cocina.", "Pudahuel", date(2025, 8, 19)),
        ),
    },
    {
        "username": "demo_andrea_torres",
        "nombre": "Andrea",
        "apellido": "Torres",
        "especialidad": "Electricidad",
        "experiencia": 8,
        "comunas": ("Ñuñoa", "Santiago"),
        "descripcion": "Electricista para instalaciones domiciliarias, circuitos, tableros y luminarias.",
        "trabajos": (
            ("Renovación de instalación eléctrica", "Revisión de circuitos y renovación de canalización, conductores y protecciones domiciliarias.", "Ñuñoa", date(2025, 9, 30)),
            ("Instalación de luminarias", "Montaje y conexión segura de luminarias interiores con verificación de funcionamiento.", "Santiago", date(2025, 7, 9)),
        ),
    },
    {
        "username": "demo_miguel_castro",
        "nombre": "Miguel",
        "apellido": "Castro",
        "especialidad": "Cerámica y revestimientos",
        "experiencia": 11,
        "comunas": ("La Florida", "Puente Alto"),
        "descripcion": "Instalador de cerámicas y revestimientos para cocinas, baños y pisos residenciales.",
        "trabajos": (
            ("Instalación de cerámica en cocina", "Nivelación de superficie e instalación de cerámica con fragüe y terminaciones perimetrales.", "La Florida", date(2025, 10, 2)),
            ("Renovación de revestimiento de baño", "Retiro controlado e instalación de nuevo revestimiento cerámico para baño.", "Puente Alto", date(2025, 5, 22)),
        ),
    },
    {
        "username": "demo_roberto_vidal",
        "nombre": "Roberto",
        "apellido": "Vidal",
        "especialidad": "Albañilería",
        "experiencia": 15,
        "comunas": ("Puente Alto", "La Florida"),
        "descripcion": "Maestro albañil especializado en reparación de muros, nivelación y terminaciones residenciales.",
        "trabajos": (("Reparación y terminación de muro", "Reconstrucción de sección dañada, nivelación y terminación lista para pintar.", "Puente Alto", date(2025, 9, 5)),),
    },
    {
        "username": "demo_carolina_reyes",
        "nombre": "Carolina",
        "apellido": "Reyes",
        "especialidad": "Yesería y tabiquería",
        "experiencia": 6,
        "comunas": ("San Miguel", "Santiago"),
        "descripcion": "Especialista en tabiques interiores, cielos y terminaciones en yeso-cartón.",
        "trabajos": (("Construcción de tabique interior", "Estructura, aislación y revestimiento de tabique interior con terminación de juntas.", "San Miguel", date(2025, 8, 28)),),
    },
    {
        "username": "demo_pablo_herrera",
        "nombre": "Pablo",
        "apellido": "Herrera",
        "especialidad": "Jardinería",
        "experiencia": 10,
        "comunas": ("Maipú", "Peñaflor"),
        "descripcion": "Jardinero dedicado a recuperación, orden y mantención de áreas verdes residenciales.",
        "trabajos": (("Recuperación de jardín residencial", "Limpieza, preparación del terreno, poda y recuperación de áreas verdes domiciliarias.", "Maipú", date(2025, 11, 12)),),
    },
    {
        "username": "demo_ricardo_fuentes",
        "nombre": "Ricardo",
        "apellido": "Fuentes",
        "especialidad": "Techumbre",
        "experiencia": 14,
        "comunas": ("La Florida", "Puente Alto"),
        "descripcion": "Maestro de techumbre para inspecciones preventivas, sellos y reparación de cubiertas.",
        "trabajos": (("Reparación preventiva de techumbre", "Inspección, reemplazo de elementos dañados y sellado preventivo de encuentros de cubierta.", "La Florida", date(2025, 10, 16)),),
    },
)


PERFILES_NEGATIVOS = (
    ("demo_pintor_pendiente", "Tomás", "Vega", "Pintura", "PENDIENTE", True),
    ("demo_carpintero_no_disponible", "Felipe", "Navarro", "Carpintería", "APROBADO", False),
)


def _crear_usuario(Usuario, indice, username, nombre, apellido):
    usuario, _ = Usuario.objects.get_or_create(
        username=username,
        defaults={
            "first_name": nombre,
            "last_name": apellido,
            "email": f"{username}@example.invalid",
            "rut": f"2600{indice:04d}-{indice % 9}",
            "telefono": f"+5697000{indice:04d}",
            "password": make_password(None),
            "is_active": True,
            "email_confirmado": True,
        },
    )
    return usuario


def crear_maestros_demo(apps, schema_editor):
    Usuario = apps.get_model("usuarios", "Usuario")
    Especialidad = apps.get_model("maestros", "Especialidad")
    PerfilMaestro = apps.get_model("maestros", "PerfilMaestro")
    TrabajoRealizado = apps.get_model("maestros", "TrabajoRealizado")

    for indice, datos in enumerate(MAESTROS_DEMO, start=1):
        usuario = _crear_usuario(
            Usuario, indice, datos["username"], datos["nombre"], datos["apellido"]
        )
        especialidad = Especialidad.objects.get(nombre=datos["especialidad"])
        perfil, _ = PerfilMaestro.objects.update_or_create(
            usuario=usuario,
            defaults={
                "descripcion_profesional": datos["descripcion"],
                "anos_experiencia": datos["experiencia"],
                "region": "RM",
                "comuna": datos["comunas"][0],
                "zonas_trabajo": ", ".join(datos["comunas"]),
                "disponible": True,
                "estado": "APROBADO",
                "observacion_admin": "",
                "fecha_aprobacion": timezone.now(),
            },
        )
        perfil.especialidades.set([especialidad])
        for titulo, descripcion, comuna, fecha in datos["trabajos"]:
            trabajo, _ = TrabajoRealizado.objects.update_or_create(
                maestro=perfil,
                titulo=titulo,
                defaults={
                    "descripcion": descripcion,
                    "comuna": comuna,
                    "fecha": fecha,
                    "publicado": True,
                },
            )
            trabajo.especialidades.set([especialidad])

    inicio = len(MAESTROS_DEMO) + 1
    for indice, (username, nombre, apellido, oficio, estado, disponible) in enumerate(
        PERFILES_NEGATIVOS, start=inicio
    ):
        usuario = _crear_usuario(Usuario, indice, username, nombre, apellido)
        especialidad = Especialidad.objects.get(nombre=oficio)
        perfil, _ = PerfilMaestro.objects.update_or_create(
            usuario=usuario,
            defaults={
                "descripcion_profesional": "Perfil técnico creado para validar filtros y recomendaciones.",
                "anos_experiencia": 4,
                "region": "RM",
                "comuna": "Maipú",
                "zonas_trabajo": "Maipú",
                "disponible": disponible,
                "estado": estado,
                "observacion_admin": "",
                "fecha_aprobacion": timezone.now() if estado == "APROBADO" else None,
            },
        )
        perfil.especialidades.set([especialidad])


class Migration(migrations.Migration):
    dependencies = [
        ("maestros", "0007_alter_trabajorealizado_fecha"),
        ("usuarios", "0003_alter_usuario_email"),
    ]

    operations = [
        migrations.RunPython(crear_maestros_demo, migrations.RunPython.noop),
    ]
