# Ideas posibles para SFI

Este documento conserva propuestas teóricas que podrían incorporarse al proyecto en el futuro. No forman parte del alcance actual y no deben implementarse sin una solicitud explícita.

## Estado de las ideas

- **Posible:** propuesta aceptada para análisis futuro.
- **Priorizada:** seleccionada para diseñar su alcance.
- **En desarrollo:** implementación autorizada y comenzada.
- **Implementada:** incorporada al proyecto y verificada.
- **Descartada:** propuesta que no continuará.

---

## SFI Lista Express

**Estado:** Posible  
**Tipo:** Inteligencia artificial multimodal y ecommerce  
**Nombre alternativo:** Escanea y compra / Lista inteligente de obra

### Problema que resuelve

En construcción es habitual recibir listas de materiales escritas a mano, fotografiadas o enviadas mediante mensajería. El cliente debe buscar cada elemento manualmente y puede confundir nombres, medidas, unidades o cantidades.

### Propuesta

Permitir que el cliente suba una fotografía de una lista de materiales. La IA extraería descripciones, cantidades, unidades y medidas; posteriormente, Django buscaría coincidencias reales en el catálogo SFI.

El usuario debería revisar y confirmar cada coincidencia antes de agregar productos al carrito.

### Flujo esperado

1. El cliente adjunta una fotografía JPG, PNG o WebP.
2. El sistema valida el archivo, tamaño y resolución.
3. Gemini extrae únicamente descripciones, cantidades, unidades y medidas.
4. Django normaliza los datos y busca productos activos del catálogo.
5. SFI clasifica cada resultado como coincidencia alta, coincidencia media, requiere revisión o no encontrado.
6. El cliente corrige o confirma los resultados.
7. El backend valida precio, estado y stock.
8. Los productos confirmados pueden agregarse al carrito.

### Ejemplo

Texto fotografiado:

```text
5 sacos de cemento
2 tablas de pino 2x3
1 kg de clavos de 4 pulgadas
1 galón de pintura blanca exterior
2 rodillos
```

Resultado esperado:

| Texto detectado | Coincidencia del catálogo | Cantidad | Estado |
|---|---|---:|---|
| 5 sacos de cemento | Cemento uso general 25 kg | 5 | Coincidencia alta |
| Tabla de pino 2x3 | Pino dimensionado 2x3 x 3,2 m | 2 | Coincidencia alta |
| Clavos de 4 pulgadas | Clavo corriente 4 pulgadas, 1 kg | 1 | Coincidencia alta |
| Pintura blanca exterior | Pintura de fachada blanca, 1 galón | 1 | Coincidencia media |
| Rodillos | Sin tamaño especificado | 2 | Requiere revisión |

### Reglas obligatorias

- Gemini no puede asignar identificadores, precios ni stock.
- Django debe obtener todos los datos comerciales desde la base de datos.
- Las coincidencias ambiguas requieren confirmación humana.
- Un producto no encontrado no debe sustituirse automáticamente por otro diferente.
- El stock y el precio deben validarse nuevamente al agregar al carrito.
- La fotografía no debe guardarse permanentemente sin consentimiento.
- No deben enviarse al modelo secretos, datos administrativos ni información privada del catálogo.
- Deben mantenerse los límites de archivo y de solicitudes.

### Primera versión viable

- Imágenes JPG, PNG o WebP de hasta 4 MB.
- Máximo 20 líneas detectadas por análisis.
- Una fotografía por consulta.
- Edición manual de nombre, cantidad y unidad.
- Confirmación obligatoria antes de agregar productos.
- Indicador del nivel de coincidencia.
- Mensajes claros para elementos ambiguos o no encontrados.
- Sin almacenamiento permanente de la fotografía.

### Valor para el Capstone

- Conecta una necesidad cotidiana del mundo físico con el catálogo digital.
- Demuestra IA multimodal, normalización, búsqueda, validación y ecommerce.
- Reutiliza el cliente seguro de Gemini, las validaciones de imágenes, el catálogo y el carrito existentes.
- Permite una demostración breve, visible y fácil de comprender.

### Criterios para considerarla terminada

- Extrae una lista de prueba sin inventar información comercial.
- Distingue coincidencias seguras, ambiguas y no encontradas.
- Permite corregir todos los resultados antes de confirmar.
- Agrega únicamente productos reales y disponibles.
- Mantiene la privacidad de la imagen.
- Cuenta con pruebas para permisos, archivos inválidos, límites, ambigüedad y validación de stock.

---

## Recepción controlada de reposiciones

**Estado:** Implementada

**Tipo:** Inventario, proveedores y trazabilidad

**Implementada el:** 24/08/2026

### Problema que resuelve

Actualmente una solicitud enviada se recibe como una operación completa: todos sus productos aumentan el stock por la cantidad solicitada y la orden cambia inmediatamente a recibida. Este flujo no permite representar entregas parciales, productos ausentes, unidades dañadas o mercadería incorrecta.

### Propuesta

Agregar una etapa de recepción controlada entre la aprobación del envío y la recepción definitiva. La orden mostrará el estado `Envío aprobado` y habilitará `Confirmar recepción` cuando llegue la mercadería.

Al confirmar, se abrirá un modal con todos los productos solicitados. Cada fila permitirá:

- Marcar o desmarcar si el producto fue recibido correctamente.
- Indicar la cantidad realmente recibida.
- Seleccionar un resultado: recibido completo, recibido parcial, no recibido, dañado, producto equivocado u otro.
- Escribir una observación obligatoria cuando exista una incidencia.
- Comparar claramente cantidad solicitada, cantidad recibida y cantidad pendiente.

### Flujo esperado

1. SFI crea y envía la solicitud al proveedor.
2. La aprobación comercial se registra manualmente como `Envío aprobado`, ya que actualmente no existe un portal o API del proveedor que pueda confirmarla automáticamente.
3. Cuando llega la mercadería, administración abre `Confirmar recepción`.
4. El modal carga todos los detalles de la orden con sus cantidades originales.
5. El administrador confirma las unidades correctas y clasifica las incidencias.
6. Django valida nuevamente cada cantidad y actualiza el stock solamente con unidades efectivamente recibidas en buen estado.
7. Cada entrada queda registrada en Movimientos con la orden, el producto, el administrador responsable y la cantidad pendiente.
8. La solicitud queda `Recibida` si no hay pendientes, o `Recepción parcial` si faltan unidades por resolver.
9. Una recepción parcial puede volver a abrirse para registrar entregas posteriores sin duplicar las entradas anteriores.

### Datos que deben conservarse

- Cantidad solicitada por producto.
- Cantidad recibida acumulada.
- Cantidad aceptada en cada recepción.
- Cantidad rechazada o pendiente.
- Resultado y motivo de cada incidencia.
- Observación administrativa.
- Usuario que confirmó la recepción.
- Fecha y hora de cada entrega.
- Referencia a la solicitud y al movimiento de inventario generado.

### Reglas obligatorias

- No confiar en cantidades ni estados enviados solamente por JavaScript.
- Bloquear cantidades negativas o superiores al saldo pendiente.
- No aumentar stock por productos dañados, equivocados o no recibidos.
- Exigir un motivo y una observación para cualquier incidencia.
- Procesar cada confirmación dentro de una transacción de base de datos.
- Usar claves de idempotencia para impedir entradas duplicadas por doble clic o reenvío.
- Mantener el historial de recepciones; una corrección posterior debe generar otro registro, no editar el anterior.
- No considerar la orden totalmente recibida mientras quede alguna unidad pendiente.

### Alcance sugerido para la primera versión

- Nuevo estado `Envío aprobado` y estado `Recepción parcial`.
- Confirmación manual de aprobación del proveedor.
- Modal responsive con una fila por producto.
- Cantidad recibida y motivo de incidencia por fila.
- Actualización parcial de stock y registro en Movimientos.
- Reapertura de órdenes parciales para entregas posteriores.
- Pruebas de recepción completa, parcial, dañada, duplicada y con cantidades manipuladas.

### Decisiones aplicadas

- `Envío aprobado` representa la solicitud enviada correctamente al proveedor.
- Las unidades no recibidas, dañadas o equivocadas no ingresan al stock y permanecen pendientes.
- Las diferencias generan una incidencia trazable en Movimientos y no crean otra solicitud automáticamente.
