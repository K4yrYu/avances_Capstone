# SFI - Instrucciones para Codex / Agentes

## Proyecto

SFI es un ecommerce ferretero desarrollado con:

- Python
- Django
- MySQL
- Bootstrap
- JavaScript
- Webpay Plus
- Gemini para el asistente IA

El proyecto se ejecuta localmente en Windows.

No agregar Docker ni configuraciones de hosting salvo que se solicite.

---

## REGLA PRINCIPAL: AHORRAR CONTEXTO

No analices todo el repositorio para cada tarea.

Trabaja solamente con los archivos y módulos necesarios para resolver la solicitud actual.

Antes de leer archivos:

1. Identifica el módulo afectado.
2. Busca la función, clase, template o URL relacionada.
3. Lee únicamente esos archivos.
4. Amplía a otros archivos solo si existe una dependencia real.

No recorras carpetas completas sin necesidad.

No vuelvas a leer archivos que ya fueron revisados en la conversación actual salvo que hayan cambiado.

---

## Archivos que NO debes leer salvo necesidad

No inspeccionar automáticamente:

- media/
- media/productos/
- productos.json
- CHANGELOG.md
- migraciones antiguas
- archivos estáticos no relacionados
- .env
- backups/
- db.sqlite3
- staticfiles/
- __pycache__/
- .git/

Nunca mostrar ni modificar secretos de `.env`.

---

## Ideas futuras

- Las propuestas aprobadas para evaluación futura se documentan en `IDEAS.md`.
- Consultar ese archivo solamente cuando el usuario solicite planificar, priorizar o implementar una función futura.
- Una idea registrada no autoriza su implementación. No modificar código, modelos ni base de datos hasta recibir una solicitud explícita.

---

## Módulos principales

- `productos/`: catálogo, productos, categorías, proveedores y stock.
- `carro_compras/`: carrito, ventas, Webpay, compras y boletas.
- `usuarios/`: usuarios, autenticación y permisos.
- `asistente/`: asistente SFI y Gemini.
- `home/`: páginas generales.
- `ferremas/`: configuración principal de Django.
- `static/`: estilos y JavaScript compartido.

Usa esta información para dirigirte primero al módulo correcto.

---

## Forma de trabajar

Cuando recibas una tarea:

1. Localiza los archivos relacionados.
2. Lee el mínimo contexto necesario.
3. Explica brevemente qué encontraste.
4. Implementa únicamente lo solicitado.
5. Evita refactorizaciones no relacionadas.
6. Mantén las funciones existentes que ya funcionan.
7. Verifica el cambio.

No hagas una auditoría general del proyecto salvo que se solicite explícitamente.

---

## Búsqueda

Antes de abrir muchos archivos, utiliza búsquedas por nombre de:

- función
- clase
- modelo
- URL
- template
- texto mostrado en pantalla

Prefiere localizar primero y leer después.

---

## Django

Mantener la lógica importante en el backend.

Nunca confiar en:

- precios enviados por JavaScript
- stock enviado por el navegador
- permisos comprobados solo en frontend

Si cambia un modelo:

- crear una migración nueva
- no modificar migraciones antiguas ya aplicadas

No borrar información de la base de datos.

---

## Seguridad

Mantener:

- CSRF
- autenticación
- autorización
- validaciones backend
- variables sensibles en `.env`

Nunca exponer:

- claves API
- contraseñas
- tokens
- credenciales
- trazas internas al usuario

---

## SFI

Mantener la identidad visual existente:

- azul oscuro
- amarillo
- blanco
- verde

No rediseñar páginas que no estén relacionadas con la tarea.

---

## Asistente SFI

El asistente debe usar información real del catálogo.

Nunca inventar:

- productos
- precios
- stock
- características técnicas

Los cálculos importantes deben realizarse con Python/Django.

Gemini debe interpretar la consulta y explicar los resultados, no inventar los cálculos.

Para tareas del asistente, revisar primero `asistente/`.

No analizar todo `productos/` salvo que una función del asistente dependa de él.

---

## Pruebas

Después de un cambio ejecutar primero:

python manage.py check

Después ejecutar solamente las pruebas del módulo modificado.

No ejecutar toda la batería de pruebas salvo que:

- el cambio sea transversal
- falle una dependencia
- el usuario lo solicite

---

## Respuesta final

Al terminar responde de forma breve con:

- archivos modificados
- qué cambió
- pruebas realizadas
- posibles problemas pendientes

No generar explicaciones extensas salvo que se soliciten.
