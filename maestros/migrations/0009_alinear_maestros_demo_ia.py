from django.contrib.auth.hashers import make_password
from django.db import migrations


MAESTROS = (
    (
        "demo_pedro_gonzalez", "demo_pedro_carpintero", "Pedro", "González",
        8, "Maipú", "Maipú, Cerrillos",
        "Carpintero con experiencia en instalación de repisas, muebles, soportes y trabajos de madera para el hogar.",
    ),
    (
        "demo_carlos_munoz", "demo_carlos_carpintero", "Carlos", "Muñoz",
        5, "Santiago", "Santiago, Estación Central",
        "Especialista en muebles, reparaciones de madera e instalaciones domiciliarias.",
    ),
    (
        "demo_maria_soto", "demo_maria_pintora", "María", "Soto",
        7, "Maipú", "Maipú, Cerrillos",
        "Pintora especializada en interiores, dormitorios, living, cocinas y terminaciones residenciales.",
    ),
    (
        "demo_jorge_rojas", "demo_jorge_pintor", "Jorge", "Rojas",
        10, "Ñuñoa", "Ñuñoa, Providencia",
        "Especialista en pintura interior y exterior, preparación de superficies y fachadas.",
    ),
    (
        "demo_daniela_silva", "demo_daniela_pintora", "Daniela", "Silva",
        6, "Santiago", "Santiago, San Miguel",
        "Pintora residencial enfocada en ambientes interiores y terminaciones uniformes.",
    ),
    (
        "demo_luis_perez", "demo_luis_gasfiter", "Luis", "Pérez",
        9, "Maipú", "Maipú, Pudahuel",
        "Gasfíter para reparaciones domiciliarias, filtraciones, grifería y mantención sanitaria.",
    ),
    (
        "demo_andrea_torres", "demo_andrea_electricista", "Andrea", "Torres",
        8, "Santiago", "Santiago, Ñuñoa",
        "Electricista para instalaciones domiciliarias, circuitos, tableros y luminarias.",
    ),
    (
        "demo_miguel_castro", "demo_miguel_ceramista", "Miguel", "Castro",
        6, "La Florida", "La Florida, Puente Alto",
        "Instalador de cerámicas y revestimientos para cocinas, baños y pisos residenciales.",
    ),
    (
        "demo_roberto_vidal", "demo_roberto_albanil", "Roberto", "Vidal",
        12, "Puente Alto", "Puente Alto, La Florida",
        "Maestro albañil especializado en reparación de muros, nivelación y terminaciones residenciales.",
    ),
    (
        "demo_carolina_reyes", "demo_carolina_yeseria", "Carolina", "Reyes",
        7, "Santiago", "Santiago, San Miguel",
        "Especialista en tabiques interiores, cielos y terminaciones en yeso-cartón.",
    ),
    (
        "demo_pablo_herrera", "demo_pablo_jardinero", "Pablo", "Herrera",
        6, "Maipú", "Maipú, Padre Hurtado",
        "Jardinero dedicado a recuperación, orden y mantención de áreas verdes residenciales.",
    ),
    (
        "demo_ricardo_fuentes", "demo_ricardo_techumbre", "Ricardo", "Fuentes",
        11, "Puente Alto", "Puente Alto, La Florida",
        "Maestro de techumbre para inspecciones preventivas, sellos y reparación de cubiertas.",
    ),
)


def alinear_maestros_demo(apps, schema_editor):
    Usuario = apps.get_model("usuarios", "Usuario")
    PerfilMaestro = apps.get_model("maestros", "PerfilMaestro")

    for anterior, username, nombre, apellido, experiencia, comuna, zonas, descripcion in MAESTROS:
        usuario = Usuario.objects.filter(username=anterior).first()
        if usuario is None:
            usuario = Usuario.objects.filter(username=username).first()
        if usuario is None:
            continue
        usuario.username = username
        usuario.first_name = nombre
        usuario.last_name = apellido
        usuario.email = f"{username}@demo.sfi.local"
        usuario.password = make_password(None)
        usuario.email_confirmado = True
        usuario.is_active = True
        usuario.is_staff = False
        usuario.is_superuser = False
        usuario.save(update_fields=[
            "username", "first_name", "last_name", "email", "password",
            "email_confirmado", "is_active", "is_staff", "is_superuser",
        ])
        PerfilMaestro.objects.filter(usuario=usuario).update(
            descripcion_profesional=descripcion,
            anos_experiencia=experiencia,
            region="RM",
            comuna=comuna,
            zonas_trabajo=zonas,
            disponible=True,
            estado="APROBADO",
            observacion_admin="",
        )

    negativos = (
        ("demo_pintor_pendiente", "Fernando", "Demo", "PENDIENTE", True),
        ("demo_carpintero_no_disponible", "Mario", "Demo", "APROBADO", False),
    )
    for username, nombre, apellido, estado, disponible in negativos:
        usuario = Usuario.objects.filter(username=username).first()
        if usuario is None:
            continue
        usuario.first_name = nombre
        usuario.last_name = apellido
        usuario.email = f"{username}@demo.sfi.local"
        usuario.password = make_password(None)
        usuario.email_confirmado = True
        usuario.is_active = True
        usuario.is_staff = False
        usuario.is_superuser = False
        usuario.save(update_fields=[
            "first_name", "last_name", "email", "password", "email_confirmado",
            "is_active", "is_staff", "is_superuser",
        ])
        PerfilMaestro.objects.filter(usuario=usuario).update(
            anos_experiencia=4,
            region="RM",
            comuna="Maipú",
            zonas_trabajo="Maipú",
            disponible=disponible,
            estado=estado,
            observacion_admin="",
        )


class Migration(migrations.Migration):
    dependencies = [
        ("maestros", "0008_maestros_y_portafolios_demo"),
    ]

    operations = [
        migrations.RunPython(alinear_maestros_demo, migrations.RunPython.noop),
    ]
