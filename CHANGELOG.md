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
