from pathlib import Path
import os
from dotenv import load_dotenv

# Configuración de las rutas dentro del proyecto. BASE_DIR es el directorio raíz.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')


def env_bool(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in {'1', 'true', 'yes', 'on'}

# Configuración local desde variables de entorno.
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    raise RuntimeError('Falta DJANGO_SECRET_KEY en el archivo .env')

DJANGO_ENV = os.getenv('DJANGO_ENV', 'local').strip().lower()
IS_PRODUCTION = DJANGO_ENV == 'production'
DEBUG = False if IS_PRODUCTION else env_bool('DJANGO_DEBUG', True)

# Dominios permitidos para desarrollo local.
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv('ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')
    if host.strip()
]

# Aplicaciones de Django que estarán activas.
INSTALLED_APPS = [
    'django.contrib.admin',  # Panel de administración por defecto
    'django.contrib.auth',  # Autenticación de usuarios
    'django.contrib.contenttypes',  # Para manejar tipos de contenido
    'django.contrib.sessions',  # Para manejar sesiones de usuario
    'django.contrib.messages',  # Para manejar mensajes de usuario
    'django.contrib.staticfiles',  # Archivos estáticos (CSS, JS, imágenes)
    'home',  # Tu aplicación de inicio
    'rest_framework',  # Framework para APIs
    'rest_framework.authtoken',
    'productos',  # Aplicación de productos
    'corsheaders',  # Para evitar el bloqueo de peticiones a la API
    'usuarios',  # Aplicación de usuarios
    'carro_compras', # aplicacion de compras
]

# Middleware necesario para la seguridad, autenticación y manejo de sesiones.
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',  # Middleware de seguridad
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Para servir archivos estáticos en producción
    'django.contrib.sessions.middleware.SessionMiddleware',  # Middleware de sesiones
    'corsheaders.middleware.CorsMiddleware',  # Para que no bloquee peticiones API
    'django.middleware.common.CommonMiddleware',  # Middleware de funcionalidades comunes
    'django.middleware.csrf.CsrfViewMiddleware',  # Middleware de protección CSRF
    'django.contrib.auth.middleware.AuthenticationMiddleware',  # Middleware de autenticación
    'django.contrib.messages.middleware.MessageMiddleware',  # Middleware de mensajes
    'django.middleware.clickjacking.XFrameOptionsMiddleware',  # Middleware de protección contra clickjacking
]

# Configuración CORS (permite solicitudes desde otros dominios)
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv('CORS_ALLOWED_ORIGINS', 'http://127.0.0.1:8000').split(',')
    if origin.strip()
]

# Archivo de configuración para las URLs del proyecto.
ROOT_URLCONF = 'ferremas.urls'

# Configuración para los templates de Django
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',  # Usar DjangoTemplates para procesar HTML
        'DIRS': [os.path.join(BASE_DIR, 'home', 'templates')],  # Ruta de los templates (ajusta según tu estructura)
        'APP_DIRS': True,  # Django buscará automáticamente los templates en cada aplicación
        'OPTIONS': {
            'context_processors': [  # Procesadores de contexto para manejar datos en los templates
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# Configuración para el servidor WSGI (conexión entre Django y el servidor web).
WSGI_APPLICATION = 'ferremas.wsgi.application'

# Base de datos MySQL local.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '3306'),
    }
}

# Validación de contraseñas
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Configuración de internacionalización
LANGUAGE_CODE = 'es'  # Idioma por defecto (puedes cambiarlo a 'es' para español)

TIME_ZONE = 'America/Santiago'

USE_I18N = True  # Habilitar internacionalización

USE_TZ = True  # Habilitar el uso de zonas horarias

# Configuración para los archivos estáticos (CSS, JS, imágenes)
STATIC_URL = '/static/'  # URL para servir los archivos estáticos
STATIC_ROOT = BASE_DIR / 'staticfiles'  # Directorio donde se recopilarán los archivos estáticos en producción

# Directorios donde se encuentran los archivos estáticos
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),  # Ruta donde están tus archivos estáticos
]

# Para la carga de archivos estáticos en producción (cuando usas el servidor WhiteNoise)
WHITENOISE_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Tipo de campo por defecto para los identificadores de las tablas de la base de datos
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Origen local autorizado para formularios CSRF.
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv('CSRF_TRUSTED_ORIGINS', 'http://127.0.0.1:8000').split(',')
    if origin.strip()
]

CORS_ALLOW_CREDENTIALS = True

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'same-origin'
SECURE_SSL_REDIRECT = IS_PRODUCTION
SESSION_COOKIE_SECURE = IS_PRODUCTION
CSRF_COOKIE_SECURE = IS_PRODUCTION
SECURE_HSTS_SECONDS = 31536000 if IS_PRODUCTION else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = IS_PRODUCTION
SECURE_HSTS_PRELOAD = IS_PRODUCTION


# Configuración de los archivos multimedia (si es necesario para manejar archivos de imagen, etc.)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

LOGIN_URL = '/usuarios/iniciosesion/'


AUTH_USER_MODEL = 'usuarios.Usuario'

# Configuración de Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',  # Permite autenticación con sesión (cookies)
        'rest_framework.authentication.TokenAuthentication',    # Opcional, para APIs que usen tokens
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '60/minute',
        'user': '120/minute',
        'login': '5/minute',
        'register': '3/hour',
    },
}

TRANSBANK = {
    'COMMERCE_CODE': os.getenv('TRANSBANK_COMMERCE_CODE'),
    'API_KEY': os.getenv('TRANSBANK_API_KEY'),
    'ENVIRONMENT': os.getenv('TRANSBANK_ENVIRONMENT', 'TEST').upper(),
}
if not TRANSBANK['COMMERCE_CODE'] or not TRANSBANK['API_KEY']:
    raise RuntimeError('Faltan TRANSBANK_COMMERCE_CODE o TRANSBANK_API_KEY en el archivo .env')
if TRANSBANK['ENVIRONMENT'] not in {'TEST', 'LIVE'}:
    raise RuntimeError('TRANSBANK_ENVIRONMENT debe ser TEST o LIVE')
if IS_PRODUCTION and TRANSBANK['ENVIRONMENT'] != 'LIVE':
    raise RuntimeError('Webpay debe usar el ambiente LIVE en producción')

EMAIL_BACKEND = os.getenv(
    'EMAIL_BACKEND',
    'django.core.mail.backends.smtp.EmailBackend'
    if IS_PRODUCTION else 'django.core.mail.backends.console.EmailBackend',
)
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True

EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = os.getenv(
    'DEFAULT_FROM_EMAIL',
    f"SFI <{EMAIL_HOST_USER}>" if EMAIL_HOST_USER else 'SFI <webmaster@localhost>',
)
if IS_PRODUCTION and EMAIL_BACKEND.endswith('smtp.EmailBackend'):
    if not EMAIL_HOST_USER or not EMAIL_HOST_PASSWORD:
        raise RuntimeError('Faltan las credenciales SMTP para enviar correos en producción')




PASSWORD_RESET_TIMEOUT = 7200
