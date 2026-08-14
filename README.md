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
