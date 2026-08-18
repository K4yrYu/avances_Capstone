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
