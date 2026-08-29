# Historial de cambios de SFI

Este documento registra las mejoras incorporadas al proyecto. La guía de trabajo para Codex se mantiene separada en `AGENTS.md`.

## Cómo registrar una versión

Cada nueva entrega debe indicar:

- Número y nombre de la versión.
- Fecha.
- Funciones agregadas.
- Cambios realizados.
- Errores corregidos.
- Cambios de base de datos o configuración necesarios.

No se deben incluir contraseñas, tokens, claves de API ni contenido del archivo `.env`.

---

## [Sin publicar]

### Verificación documental y directorio definitivo de maestros - 29 de agosto de 2026 (UTC-04:00)

#### Documentación y aprobación

- Se incorporó la carga privada de cédula de identidad y certificado de antecedentes para todos los maestros.
- Electricidad exige una licencia SEC eléctrica e Instalaciones de gas exige una licencia SEC gas; si el maestro selecciona ambas especialidades debe presentar ambas licencias.
- Los documentos y licencias admiten los estados pendiente, verificado y rechazado, con revisión exclusiva de administración y observación obligatoria al rechazar.
- El perfil solo puede enviarse a revisión cuando contiene toda la documentación requerida y solo puede quedar aprobado cuando cada documento y licencia obligatoria está verificado.
- Los archivos documentales se almacenan fuera de `media`, se descargan mediante vistas protegidas y nunca se publican en el perfil ni en la API pública.
- Se agregaron paneles ordenados para cargar, reemplazar y revisar documentación, junto con tarjetas administrativas plegables e indicadores de requisitos pendientes.

#### Directorio, contacto y privacidad

- SFI quedó definido como directorio de maestros independientes: no crea solicitudes, contrataciones, cotizaciones, pagos, garantías ni seguimiento de servicios.
- El perfil público muestra únicamente maestros aprobados, sus especialidades, experiencia, región, comunas, disponibilidad y portafolio publicado.
- Se muestran las insignias `Maestro verificado` e `Instalador SEC verificado` cuando corresponde.
- El botón `Contactar maestro` presenta primero un aviso obligatorio sobre el alcance de SFI y solo después abre WhatsApp con un mensaje inicial prellenado.
- Se agregó `Reportar perfil` mediante un correo simple prellenado para identidad o documentación posiblemente falsa, licencia dudosa, información engañosa o contenido inapropiado.
- Se evita exponer públicamente el RUT, documentos, licencias, archivos privados y observaciones administrativas.

#### Formularios y presentación visual

- El maestro puede actualizar su teléfono de contacto desde la edición profesional; el nuevo número actualiza WhatsApp sin devolver un perfil aprobado a revisión.
- Cambiar solamente la fotografía o disponibilidad mantiene la aprobación; modificar descripción, experiencia, especialidades o cobertura requiere una nueva revisión.
- El formulario profesional se reorganizó en secciones para fotografía, contacto, trayectoria, especialidades, cobertura y disponibilidad, con vista previa limpia y diseño adaptable.
- Se mejoró el formulario de trabajos realizados con varias especialidades, previsualización de imágenes y validación de fechas coherentes, sin fechas futuras ni anteriores al rango permitido.
- El directorio utiliza tarjetas de tamaño uniforme y el encabezado público agrupa claramente verificaciones, región, comunas, especialidades, experiencia y disponibilidad con los colores SFI.

#### API, configuración y base de datos

- La API interna de maestros incorpora endpoints protegidos para documentos y licencias propios, además de endpoints administrativos para su revisión.
- Se mantienen autenticación, CSRF, validación de propiedad, permisos administrativos, límites de 5 MB y ausencia de datos documentales en respuestas públicas.
- Se agregó `PRIVATE_DOCUMENTS_ROOT`, un correo de soporte configurable y el directorio privado a `.gitignore`.
- El límite de registro público quedó en 10 solicitudes por IP dentro de una ventana real de 3 minutos.
- Se agregaron las migraciones `0012`, `0013` y `0014` para documentación, tipos de licencia, configuración de especialidades e Instalaciones de gas.

#### Verificación

- `python manage.py check` finalizó sin observaciones.
- Se ejecutaron 72 pruebas del módulo `maestros`; todas finalizaron correctamente.

### Mejora de IA con filtros - 28 de agosto de 2026 (UTC-04:00)

#### Búsqueda semántica ferretera

- Se agregó un diccionario local de sinónimos ferreteros chilenos para interpretar términos como wincha, flexómetro, perforadora, combo, azulejo, inodoro, vanitorio e impermeabilizante sin depender de nuevas APIs externas.
- Se incorporaron conceptos relacionados para búsquedas por proyecto, entre ellos colgar repisas, pintar muros, instalar cerámica, renovar baños y armar muebles.
- Las palabras escritas directamente por el cliente conservan mayor puntuación que las expansiones semánticas y los resultados mantienen un máximo de seis productos reales del catálogo.
- Se reforzó la relevancia de consultas específicas para descartar coincidencias aisladas, como una sierra que solo compartía la expresión `con cable` con la búsqueda de un taladro.
- Se corrigió la ambigüedad entre `metro` y `métrico`, evitando mostrar pernos métricos cuando el cliente solicita una cinta de medir.

#### Consultas y filtros de precio

- El asistente reconoce para cualquier producto o categoría preguntas como `cuánto cuesta`, `qué valor tiene`, `el más caro` y `el más económico`.
- Las palabras conversacionales se eliminan antes de buscar, por lo que expresiones como `sanitario que valor tiene` no reducen la precisión del catálogo.
- Las comparaciones se realizan en Django con los precios registrados en la base de datos; Gemini solamente interpreta la intención y no inventa valores.
- Las respuestas de mayor o menor precio devuelven una única alternativa, mientras que las consultas generales muestran hasta seis opciones con sus precios actuales.
- Cuando un presupuesto no alcanza, la alternativa económica se determina por su precio real y no por la posición previa del resultado.

#### Verificación

- No se agregaron migraciones, credenciales ni servicios externos.
- `python manage.py check` finalizó sin observaciones.
- Se ejecutaron 87 pruebas del módulo `asistente`; todas finalizaron correctamente.

### Consolidación del módulo de maestros - 28 de agosto de 2026 (UTC-04:00)

#### Perfiles, portafolio y contacto

- Se consolidó el flujo completo para crear, editar y enviar perfiles profesionales a revisión, junto con la aprobación, rechazo y suspensión controlados desde administración.
- Los perfiles admiten varias especialidades y comunas de trabajo asociadas a una región de Chile, con validaciones en backend y filtros públicos automáticos.
- Las fotografías del perfil y del portafolio disponen de previsualización, límites de tamaño, imágenes de respaldo y presentación adaptable a dispositivos móviles.
- Los trabajos realizados permiten varias especialidades, múltiples imágenes, publicación controlada y fechas coherentes con la experiencia declarada, sin aceptar fechas futuras.
- El perfil público de un maestro aprobado muestra teléfono, acceso directo a WhatsApp y correo electrónico para facilitar el contacto profesional.
- Todas las barras públicas mantienen los accesos a Maestros, Carrito y Mis compras; quienes poseen perfil profesional también disponen de `Mi panel`.

#### Administración, seguridad y API

- El resumen administrativo incorpora maestros activos, postulaciones pendientes, alertas de revisión y accesos directos a la gestión profesional.
- Se mantiene una API privada protegida por autenticación, CSRF, propiedad de recursos y permisos administrativos, además de una API pública limitada a perfiles aprobados y datos autorizados.
- Las modificaciones sensibles de un perfil aprobado vuelven a dejarlo pendiente de revisión; cambiar únicamente su disponibilidad conserva la aprobación.
- Solo se publican perfiles aprobados y disponibles, junto con los trabajos marcados como publicados.
- Se preservaron las vistas HTML y la identidad visual existente de SFI sin modificar los módulos de carrito, Webpay o suscripciones.

#### Integración con el asistente SFI

- El asistente puede buscar maestros por especialidad y comuna usando únicamente perfiles aprobados y disponibles.
- El flujo conversacional reconoce solicitudes como mostrar todos los profesionales de una especialidad, buscar en cualquier comuna o cambiar de especialidad sin conservar filtros anteriores incorrectos.
- Las respuestas mantienen el contexto de búsqueda y enlazan al perfil público para consultar experiencia, zonas, portafolio y medios de contacto.
- La búsqueda de profesionales se mantiene separada de Gemini y consulta directamente los datos verificados en Django.

#### Datos, limpieza y pruebas

- Se agregó la migración `0010_eliminar_maestros_demo` para retirar exclusivamente los 14 usuarios y perfiles de demostración conocidos, junto con sus portafolios relacionados.
- Se conservó intacto el perfil profesional original y la base quedó sin usuarios `demo_*`.
- Las pruebas del asistente ahora crean sus propios maestros temporales y ya no dependen de datos demostrativos instalados en la base local.
- `python manage.py check` finalizó correctamente.
- Se ejecutaron 42 pruebas de `maestros` y 87 pruebas de `asistente`; todas finalizaron correctamente.
### Expiración de registros públicos sin verificar - 24 de agosto de 2026, 04:38 (UTC-04:00)

#### Agregado

- Las cuentas creadas mediante el registro público disponen de 24 horas para confirmar su correo.
- Se guarda en la base de datos la fecha y hora de envío del correo y la fecha exacta de expiración.
- El correo, la pantalla de registro pendiente y la respuesta de la API informan que una cuenta no activada será eliminada al vencer el plazo.
- Se agregó el comando `python manage.py limpiar_cuentas_no_verificadas` para ejecutar la limpieza manualmente o durante el arranque.
- `iniciar_ferremas.bat` comprueba y elimina cuentas vencidas antes de iniciar Django.
- Mientras el sistema está funcionando, la limpieza diaria se activa con el primer acceso desde las 04:00 en la zona horaria `America/Santiago`.
- Antes de un nuevo registro se libera cualquier correo, RUT o nombre de usuario perteneciente a una cuenta pública ya vencida.

#### Seguridad y compatibilidad

- La limpieza exige simultáneamente que la cuenta siga inactiva, no tenga el correo confirmado y posea una expiración vencida.
- Al confirmar el correo se elimina la fecha de expiración, impidiendo que una cuenta activada pueda ser borrada por este proceso.
- Las cuentas creadas por administración, administradores y cuentas verificadas quedan fuera de la limpieza.
- Las cuentas pendientes anteriores reciben una expiración compatible basada en su fecha original de registro.
- La activación y la limpieza utilizan comprobaciones persistentes para continuar funcionando después de apagar y volver a iniciar el sistema.

#### Verificación

- Se comprobó la configuración de 24 horas y las 04:00 bajo la hora oficial de Chile.
- Las 9 pruebas específicas de seguridad de usuarios finalizaron correctamente.
- La batería completa alcanzó 119 pruebas aprobadas sin errores.
### Módulo Movimientos y Reposición 2.0 - 24 de agosto de 2026, 04:07 (UTC-04:00)

#### Reposición y recepción

- Se incorporó una recepción detallada por producto con resultados completo, parcial, no recibido, dañado, equivocado u otra incidencia.
- Las cantidades recibidas correctamente actualizan el stock; las unidades con incidencias no ingresan al inventario.
- Las solicitudes pendientes y el historial de recepciones se presentan en secciones independientes y cada confirmación conserva su trazabilidad.
- Toda confirmación cierra la solicitud pendiente: las recepciones correctas muestran un aviso verde y las que contienen incidencias muestran un aviso rojo.
- Las incidencias se notifican al correo del proveedor e incluyen productos, cantidades, resultado y observaciones registradas.
- Los pedidos enviados, las entradas confirmadas y las incidencias quedaron integrados con el Registro de movimientos.

#### Control de duplicados y compras pendientes

- Los productos que ya tienen una solicitud pendiente, con error o enviada se ocultan temporalmente de `Productos que requieren compra` y el backend rechaza solicitudes duplicadas.
- La confirmación de recepción bloquea el botón mientras se procesa y utiliza una clave de idempotencia única para impedir recepciones, correos o movimientos repetidos por múltiples clics.
- Los productos faltantes en una recepción parcial vuelven a la lista de compra aunque el stock resultante supere el mínimo.
- La cantidad sugerida para esos productos corresponde exactamente a las unidades no recibidas.
- Solo se considera la solicitud más reciente, por lo que una reposición posterior completada resuelve la alerta anterior y evita que reaparezca indefinidamente.

#### Registro de movimientos

- La interfaz se estandarizó bajo el nombre `Registro de movimientos` y diferencia visualmente solicitudes en proceso, entradas e incidencias de reposición.
- Los movimientos conservan los datos históricos del producto, proveedor, orden, responsable, cantidades y resultado aun cuando cambie la ficha del producto.
- Se reorganizaron las columnas de fecha, operación y observaciones extensas para mejorar su lectura.

#### Base de datos y verificación

- Se agregaron modelos y migraciones para recepciones, detalles por producto, datos históricos del proveedor e idempotencia de cada confirmación.
- La conexión MySQL configurada en `.env`, las migraciones y `python manage.py check` fueron verificados correctamente.
- Se ejecutaron 115 pruebas automatizadas en una base aislada: todas finalizaron correctamente.
- Se corrigió una prueba y la lógica asociada que omitían productos parcialmente recibidos cuando su stock superaba el mínimo.

### Movimientos de inventario y ajustes administrativos - 23 de agosto de 2026, 04:07 (UTC-04:00)

#### Agregado

- Se incorporó el módulo administrativo `Movimientos`, accesible directamente debajo de Productos en la barra lateral.
- Se creó un historial de inventario inalterable que conserva una copia del nombre, SKU, categoría, marca, modelo, precio y stock del producto al momento de cada operación, aunque su ficha cambie posteriormente.
- El historial distingue stock inicial, entradas, salidas, ajustes, modificaciones e inactivaciones, junto con su fecha, operación, referencia y responsable.
- Se agregaron filtros por producto o SKU, fechas, tipo, estado, origen y categoría, además de paginación y un formulario administrativo para ajustes manuales con observación obligatoria.
- El dashboard de Movimientos incorpora totales, flujo de entradas y salidas, productos más y menos vendidos, stock bajo y lotes próximos a vencer.
- Se agregó al resumen administrativo una tarjeta responsive con entradas, salidas por ventas, unidades de reposición pendientes y ajustes de los últimos 30 días, junto con un acceso en `Áreas administrativas`.
- Se incorporó un comando de administración para respaldar y reiniciar de forma controlada los movimientos cuando sea necesario durante el desarrollo.

#### Integración de inventario

- Las ventas descuentan stock y registran su salida solamente después de que Webpay confirma el pago; los pagos rechazados o incompletos no generan movimientos.
- La recepción de una reposición registra entradas de inventario con referencia a la orden y protección contra registros duplicados.
- Las creaciones, ediciones, cambios de precio y cambios de estado de productos conservan movimientos históricos con el administrador responsable.
- El responsable se presenta según el origen de la operación: administrador, cliente autenticado o proceso automático del sistema.
- Las variaciones de precio muestran indicadores diferenciados cuando el valor sube o baja.
- Los productos se desactivan sin eliminar sus referencias históricas ni afectar ventas o boletas existentes.

#### Panel administrativo e interfaz

- `Volver a la tienda` y `Cerrar sesión` se trasladaron desde el pie de la barra lateral al encabezado compartido de todas las secciones administrativas.
- El regreso a la tienda usa la combinación azul, amarilla y blanca de SFI; el cierre de sesión se diferencia en rojo y continúa enviándose mediante `POST` con CSRF.
- Ambos controles mantienen una ubicación y ancho uniformes en escritorio y se reducen a iconos accesibles en pantallas pequeñas.
- Se actualizó la versión del recurso CSS compartido para evitar que la caché conserve estilos anteriores.
- Se personalizó la pantalla 404 con la identidad visual de SFI, imagen central y regreso al inicio.
- La barra de la Calculadora de Pintura se ajustó al formato visual de la navegación principal.

#### Maestros profesionales

- La carga de fotografía del perfil dispone de una vista previa más grande junto al selector de archivo y mantiene una disposición adaptable en móviles.
- Los mensajes de creación y actualización indican que el perfil debe enviarse mediante `Enviar a revisión` para verificar los cambios.
- Se resaltaron las acciones para actualizar la información y agregar trabajos, y se ampliaron las tarjetas del portafolio privado y el botón para volver al panel.
- Se descartó el envío decorativo de correos de aprobación o rechazo; los cambios de estado se procesan directamente en el sistema.
- Solo los perfiles pendientes pueden aprobarse o rechazarse y solo los perfiles aprobados pueden suspenderse.
- Rechazar o suspender exige una observación administrativa de al menos 10 caracteres, tanto en la interfaz HTML como en la API.

#### Webpay y correcciones

- El entorno de pruebas de Webpay utiliza las credenciales oficiales de integración proporcionadas por el SDK de Transbank, manteniendo las credenciales configuradas para el entorno productivo.
- Se corrigió la edición administrativa de productos y se agregó cobertura para comprobar que registra los cambios históricos y al usuario responsable.
- Se agregaron pruebas para pagos aprobados y rechazados, movimientos de ventas, edición de productos, transiciones de maestros, observaciones obligatorias y la pantalla 404.

#### Base de datos y configuración

- Se registró la aplicación `movimientos` y sus rutas administrativas en Django.
- Se agregaron las migraciones `0001_initial` y `0002_registrar_stock_inicial` para crear el historial y registrar el punto de partida del inventario.
- La configuración de ejemplo mantiene separados los valores locales, el correo y las integraciones externas sin documentar secretos reales.
- `python manage.py check` y el renderizado del panel administrativo finalizaron correctamente; la batería completa de pruebas permanece pendiente porque el usuario local de MySQL no puede crear la base `test_ferremas`.

### Mejoras de interfaz en Maestros y visualizador de pintura - 22 de agosto de 2026

#### Modificado

- Se rediseñó el listado de maestros con tarjetas horizontales más amplias, fotografía destacada, información profesional ordenada y adaptación responsive para escritorio y dispositivos móviles.
- La disponibilidad del profesional ahora tiene mayor presencia visual y las especialidades se presentan de forma resumida cuando existen varias.
- Se trasladó el acceso `Trabaja con nosotros` al hero del listado y se convirtió en una llamada a la acción amarilla acorde con la identidad visual de SFI.
- Se amplió la fotografía del perfil individual y se reorganizaron sus datos profesionales para mejorar la lectura.
- Cada trabajo del portafolio dispone ahora de un carrusel independiente, controles condicionales cuando hay varias fotografías, contador, navegación mediante teclado y gestos táctiles, y una relación visual 4:3 en móviles.
- Se rediseñó `Trabaja con nosotros` manteniendo su información, proceso y colores, con una llamada a la acción inferior grande que se adapta al estado del usuario y de su perfil.
- Se eliminaron del hero las acciones duplicadas para crear el perfil y consultar maestros, además del enlace redundante `Ver maestros disponibles` del bloque final.
- En el visualizador de pintura, `Ver antes` funciona como interruptor: blanco en estado normal y amarillo cuando muestra la fotografía original, permitiendo volver al resultado pintado sin mantener presionado.

#### Pruebas y configuración

- Se verificó la configuración de Django y se ejecutaron correctamente las 17 pruebas del módulo `maestros`.
- No se requieren migraciones ni variables de entorno adicionales.

### API segura de maestros - 21 de agosto de 2026

#### Agregado

- Se incorporó una API interna con Django REST Framework para administrar el perfil profesional, enviar postulaciones a revisión y gestionar trabajos e imágenes del portafolio.
- Se agregó un endpoint administrativo exclusivo para aprobar, rechazar o suspender perfiles profesionales.
- Se agregó una API pública de solo lectura que entrega únicamente maestros aprobados, trabajos publicados y datos profesionales públicos.
- Se crearon serializers, permisos y vistas API independientes para mantener sin cambios las vistas HTML existentes.

#### Seguridad y validación

- Las APIs privadas usan autenticación de sesión con protección CSRF y determinan siempre el propietario mediante `request.user`.
- Los serializers privados no aceptan usuario, estado, observación administrativa ni fecha de aprobación enviados por el maestro.
- Se impidió consultar, modificar o eliminar perfiles, trabajos e imágenes pertenecientes a otros usuarios.
- Solo administradores pueden cambiar estados profesionales y ningún administrador puede aprobar su propio perfil.
- Se validan en backend las especialidades activas, comunas chilenas, regiones, fechas e imágenes.
- Cada imagen se limita a 5 MB y cada trabajo a un máximo de 10 imágenes.
- Un perfil aprobado vuelve automáticamente a pendiente cuando cambia información profesional sensible; modificar solo la disponibilidad mantiene la aprobación.
- La API pública no expone RUT, teléfono, correo, observaciones administrativas ni perfiles sin aprobar.

#### Pruebas y configuración

- El módulo cuenta ahora con 17 pruebas para autenticación, propiedad, manipulación de identificadores, permisos administrativos, visibilidad pública, revalidación y límites de imágenes.
- No se requieren migraciones nuevas ni variables de entorno adicionales.

### Módulo de maestros profesionales - 21 de agosto de 2026

#### Agregado

- Se creó la Fase 1 del módulo `maestros` con perfiles profesionales asociados a usuarios SFI verificados.
- Se incorporaron los estados borrador, pendiente, aprobado, rechazado y suspendido, junto con revisión administrativa y fecha de aprobación.
- Se agregó un directorio público que muestra únicamente maestros aprobados, con filtros automáticos por especialidad, región y comuna.
- Se incorporaron las 16 regiones y 346 comunas de Chile, con validación de correspondencia entre región y comunas seleccionadas.
- Se agregaron 13 especialidades iniciales y una opción para que administración registre nuevas especialidades.
- Los maestros pueden seleccionar varias especialidades y varias comunas de trabajo.
- Se agregó un portafolio profesional con trabajos publicados, múltiples especialidades y varias imágenes por trabajo.
- Se incorporó previsualización de la foto profesional y de las imágenes nuevas del portafolio antes de guardar.

#### Modificado

- Todas las barras públicas ahora incluyen acceso a Maestros, Carrito y Mis compras.
- Los usuarios con perfil de maestro disponen del acceso Mi panel en todas las barras públicas.
- El panel administrativo muestra maestros activos y pendientes, alertas de revisión y accesos directos a su gestión.
- Las especialidades seleccionadas se muestran con resaltado y un ticket visible.
- Las fechas de trabajos realizados se limitan según la experiencia declarada y no permiten fechas futuras o excesivamente antiguas.

#### Seguridad y validación

- Solo usuarios activos con correo confirmado pueden crear un perfil profesional.
- Cada usuario administra únicamente su propio perfil, trabajos e imágenes.
- Solo administradores pueden aprobar, rechazar o suspender perfiles y no pueden revisar su propio perfil.
- Los clientes solo pueden ver perfiles aprobados y trabajos marcados como publicados.
- Se agregaron 9 pruebas para permisos, estados, visibilidad, múltiples especialidades, comunas y validación de fechas.

#### Base de datos y configuración

- Se registró la aplicación `maestros` en Django y se conectaron sus rutas públicas y administrativas.
- Se agregaron las migraciones `0001` a `0007` del módulo, incluyendo datos territoriales, especialidades iniciales y preservación de especialidades en trabajos existentes.
- No se requieren nuevas variables de entorno.

### Agregado de productos al carrito sin navegación - 17 de agosto de 2026

#### Agregado
- Componente de alerta emergente (Toast) al agregar productos o recomendaciones al carrito en la vista del Asistente IA y en la Calculadora de Pintura, informando al usuario con la confirmación del producto añadido y un acceso rápido "Ver mi carrito".

#### Modificado
- La acción de los botones "Agregar" en las tarjetas de productos recomendados del Asistente IA y de la Calculadora de Pintura procesa la adición mediante AJAX en segundo plano sin redirigir ni sacar al usuario de la página actual.
- Estado visual dinámico en el botón al presionar "Agregar", mostrando una animación de carga y la confirmación "✓ Agregado".

### Asistente SFI y análisis fotográfico


#### Agregado

- Se integró un chat contextual dentro del módulo fotográfico para consultar colores, pinturas, cantidades y costos sin separar la conversación de la imagen analizada.
- Se incorporaron 24 variantes tintométricas Sipa distribuidas entre látex, esmalte satinado, fachada hidrorrepelente y esmalte semibrillo.
- Los productos ahora pueden registrar un SKU comercial único, visible y administrable desde la ficha de producto.
- Los colores solicitados en el chat se incorporan a la lista de pinturas recomendadas cuando existen productos reales, compatibles, activos y con stock.
- Se añadieron accesos para probar una pintura sobre la fotografía y consultar su ficha de producto.
- Se incorporaron selección automática con detección de bordes, pincel, borrador y vista de máscara para corregir manualmente las superficies que se pintarán.
- Se añadió **Autopintura TEST**, una detección experimental de superficies que presenta primero una máscara amarilla revisable.
- Se agregó una acción separada para aplicar la pintura seleccionada únicamente sobre las zonas marcadas.
- La pintura seleccionada queda destacada en amarillo para mantener visible la opción activa.
- El estado de la conversación, la fotografía, el análisis, los colores y las marcas realizadas se conserva por usuario mientras la pestaña permanezca abierta.

#### Modificado

- Al adjuntar una fotografía se oculta el chat general y se utiliza un único flujo contextual asociado a esa imagen.
- El análisis ofrece automáticamente pinturas compatibles con el ambiente detectado: interior, exterior o piscina.
- Las consultas destinadas únicamente a visualizar un color muestran opciones disponibles sin exigir medidas innecesarias.
- Las preguntas sobre cantidades, litros, envases, presupuesto o costos solicitan primero los datos técnicos faltantes, como superficie, material y estado actual.
- Las respuestas que solicitan información adicional utilizan un lenguaje más claro y amable.
- Las preguntas de cálculo ahora reconocen explícitamente la pintura o el color seleccionado antes de solicitar medidas y condiciones faltantes.
- La distribución del módulo fotográfico se reorganizó con la imagen y las herramientas de análisis en la parte superior y el chat contextual debajo.
- Se restauraron dimensiones visuales más compactas después de revisar la ampliación del área fotográfica y del panel de análisis.
- El botón **Nueva consulta** reinicia el flujo completo y se resaltó con los colores de SFI.
- La barra de navegación del asistente ahora replica dimensiones, acciones y comportamiento adaptable de la página de Inicio.

#### Seguridad y validación

- Los cálculos de pintura continúan realizándose con funciones deterministas de Python; Gemini interpreta la intención y redacta la respuesta.
- El asistente evita inventar productos, precios o existencias y no recomienda pinturas incompatibles con el uso detectado.
- Las fotografías permanecen en el navegador durante la sesión y no se guardan permanentemente en SFI.
- Se ampliaron las pruebas del flujo fotográfico, la selección de colores y el cálculo posterior de cantidades.

#### Mejoras de catálogo y base de datos

- Se añadieron las migraciones `0015_producto_sku`, `0016_variantes_pintura_sipa` y `0017_familia_cromatica_variantes`.
- El asistente y la calculadora reconocen la familia cromática en español aunque el tono tenga un nombre comercial en inglés.
- Se incorporó un catálogo inicial de 24 productos de quincallería con SKU, ficha técnica, stock demostrativo y precios referenciales de mercado: tornillos, anclajes, seguridad y herrajes para muebles.
- Cada producto nuevo de quincallería dispone de una imagen individual de catálogo, evitando repetir una sola fotografía por familia.
- La búsqueda del asistente ahora pondera la consulta completa, ignora conectores genéricos y mantiene el orden por relevancia antes de comparar precios.
- Se añadió `docs/revertir_catalogo_quincalleria.sql` como procedimiento de contingencia limitado a los 24 SKU `SFI-QUI-*`.
- Se añadieron las migraciones `0018_catalogo_quincalleria` y `0019_imagenes_individuales_quincalleria`.
- No se requieren variables de entorno adicionales.

### Documentación

- Se creó `IDEAS.md` para mantener propuestas futuras separadas de las reglas de trabajo.
- Se registró **SFI Lista Express** como idea posible, sin autorizar todavía su implementación.
- `AGENTS.md` ahora indica cuándo consultar las ideas futuras y evita que se implementen automáticamente.

---

## [0.2.1-beta] - 2026-08-15

### Arreglo carrito TBK y asistente

#### Corregido

- Conexión TLS del asistente con Gemini mediante un cliente limitado al endpoint oficial.
- Manejo controlado de errores del análisis fotográfico, evitando respuestas internas 500.
- Conexión TLS de Webpay Plus mediante un cliente dedicado a los endpoints oficiales de Transbank.

#### Seguridad y verificación

- Se mantiene obligatoria la validación TLS y se rechazan dominios externos.
- Se agregaron pruebas de regresión para Gemini, análisis de fotografías y Webpay.
- No se requieren migraciones ni nuevas variables de entorno.

## [0.2.0-beta] - 2026-08-15

### IA integrada beta

#### Agregado

- Asistente SFI conectado con el catálogo de productos.
- Búsqueda de productos mediante lenguaje natural.
- Recomendaciones según tipo de proyecto y presupuesto disponible.
- Cálculo de pintura basado en superficie, rendimiento, capas y margen adicional.
- Alternativas cuando el presupuesto del cliente no es suficiente.
- Cálculos para proyectos básicos de construcción.
- Opción de agregar al carrito las cantidades calculadas.
- Análisis de fotografías para recomendar pinturas.
- Recomendaciones diferenciadas para interiores, exteriores y piscinas.
- Simulación visual referencial de colores sobre fotografías.
- Persistencia local de la conversación y del análisis al volver desde otra pantalla.
- Límites de solicitudes y validación de imágenes para el asistente.

#### Catálogo e inventario

- Fichas técnicas ampliadas para productos y pinturas.
- Marca, SKU, proveedor, stock mínimo y unidades de medida.
- Datos de rendimiento, capas, terminación, ambiente de uso y superficies compatibles.
- Nuevas pinturas y materiales para proyectos de construcción.
- Gestión de proveedores.
- Gestión de reposición de inventario y solicitudes por correo.
- Imágenes de productos almacenadas como archivos locales en lugar de URLs externas.

#### Diseño y experiencia

- Nueva identidad visual SFI en las páginas públicas y administrativas.
- Panel administrativo unificado y profesional.
- Menú lateral estandarizado.
- Mejoras en productos, ofertas, contacto, carrito y detalle de producto.
- Mejoras en usuarios, inicio de sesión, registro y recuperación de cuenta.
- Mejoras en historial de ventas, retiros, despachos, compras y boletas.
- Footer estandarizado en las páginas públicas.

#### Seguridad y correcciones

- Restricción del panel administrativo a usuarios autorizados.
- Validaciones de carrito, stock, compras y acceso a boletas.
- Corrección al eliminar el último producto del carrito.
- Corrección del retorno desde Webpay hacia el carrito.
- Corrección de textos con problemas de codificación.
- Verificación de cuentas mediante correo electrónico con identidad SFI.

#### Base de datos y configuración

- Nuevas migraciones para fichas técnicas, proveedores, reposición y datos avanzados de pinturas.
- Variables sensibles administradas mediante `.env`.
- Configuración de pruebas separada mediante `ferremas.settings_test`.

---

## Plantilla para la siguiente versión

```md
## [0.3.0-beta] - AAAA-MM-DD

### Nombre de la versión

#### Agregado

- Nueva funcionalidad.

#### Modificado

- Funcionalidad mejorada.

#### Corregido

- Error solucionado.

#### Base de datos o configuración

- Migraciones o variables nuevas necesarias.
```
