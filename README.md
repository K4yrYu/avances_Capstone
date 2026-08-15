# FERREMAS

E-commerce desarrollado con Django y MySQL para la gestión de productos, carrito, usuarios y pagos mediante Webpay Plus.

## Ejecución local en Windows

1. Copia `.env.example` como `.env` y completa las credenciales locales.
2. Instala las dependencias de `requirements.txt` en el entorno virtual.
3. Aplica las migraciones con `python manage.py migrate`.
4. Ejecuta `iniciar_ferremas.bat` para iniciar MySQL, Django y abrir el navegador.

Las imágenes del catálogo están almacenadas localmente en `media/productos/`. Para agregar o editar productos, el panel acepta archivos JPG, PNG o WebP de hasta 5 MB.

## Pruebas

Ejecuta `probar_seguridad.bat` para revisar la configuración, migraciones, pruebas automatizadas, análisis estático y dependencias.

## Configuración sensible

Los archivos `.env`, `backups/`, `db.sqlite3` y `staticfiles/` están excluidos del repositorio. Nunca publiques credenciales reales, respaldos ni bases de datos locales.
# Asistente SFI con Gemini

El asistente usa Gemini en la nube y consulta los productos y calculadoras de Django. La
clave nunca se envía al navegador.

1. Crea una clave en Google AI Studio: https://aistudio.google.com/app/apikey
2. Agrega en `.env`: `GEMINI_API_KEY=tu-clave`
3. Mantén `GEMINI_MODEL=gemini-3.5-flash-lite` y reinicia `iniciar_ferremas.bat`.
4. Abre `http://127.0.0.1:8000/asistente/`.

El nivel gratuito puede tener límites de solicitudes y sus datos pueden utilizarse para
mejorar los productos de Google. No ingreses contraseñas ni información sensible en el chat.
