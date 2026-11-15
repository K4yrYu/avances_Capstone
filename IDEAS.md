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

---

## Ampliación de productos básicos y variedades de iluminación

**Estado:** Propuesta para evaluación

**Tipo:** Catálogo y asistente IA

**Registrada el:** 14/11/2026

### Productos básicos sugeridos

#### Techumbres

- Tapagoteras para techo.
- Clavos galvanizados para teja asfáltica.
- Adhesivo o cemento asfáltico para techumbre.
- Cortagoteras metálico.
- Limahoya galvanizada.
- Forro o *flashing* para encuentros con muros.
- Remate lateral para techumbre.
- Sombrerete o ventilación de techo.
- Sellador asfáltico en cartucho.
- Grapas o fijaciones para membrana.
- Coplas, tapas y soportes para canaletas y bajadas.

#### Gasfitería

- Empaquetaduras para sifón y flexibles.
- Llave ajustable.
- Alicate bomba de agua.
- Cortatubo PVC.
- Abrazaderas para tuberías.
- Pasta selladora para roscas.
- Kit de reparación para llave de lavaplatos.

#### Electricidad

- Coplas para conduit PVC de 20 y 25 mm.
- Curvas para conduit PVC de 20 y 25 mm.
- Abrazaderas para conduit.
- Caja eléctrica estanca.
- Huincha aisladora.
- Probador de voltaje.
- Conectores eléctricos.
- Cable a tierra y barra de puesta a tierra.

#### Pintura y terminaciones

- Bandeja para rodillo.
- Espátulas de diferentes tamaños.
- Extensión telescópica para rodillo.
- Sellador acrílico pintable.
- Paños y plástico protector.
- Raspador de pintura.
- Mezclador para pintura.

### Variedades de ampolletas sugeridas

- Ampolleta LED E27 9 W, luz cálida.
- Ampolleta LED E27 9 W, luz fría.
- Ampolleta LED E27 12 W, luz neutra.
- Ampolleta LED E27 12 W, luz fría.
- Ampolleta LED E27 15 W, luz cálida.
- Ampolleta LED E27 15 W, luz fría.
- Ampolleta LED E27 20 W, alta luminosidad.
- Ampolleta LED E14 6 W tipo vela, luz cálida.
- Ampolleta LED GU10 7 W, luz cálida.
- Ampolleta LED GU10 7 W, luz fría.
- Ampolleta LED dicroica MR16 7 W, 12 V.
- Ampolleta LED E27 con sensor de movimiento.
- Ampolleta LED E27 con sensor día/noche.
- Ampolleta LED E27 regulable.
- Ampolleta LED inteligente RGB Wi-Fi.
- Ampolleta LED de emergencia con batería.
- Ampolleta LED exterior resistente a humedad.
- Ampolleta LED industrial E27 o E40 de 30 a 50 W.

### Datos necesarios en cada ficha de iluminación

- Potencia en watts.
- Flujo luminoso en lúmenes.
- Temperatura de color.
- Tipo de soquete.
- Voltaje.
- Vida útil estimada.
- Compatibilidad con regulación.
- Ambiente de uso.
- Eficiencia energética.
- Gama económica, intermedia o premium para comparar precios.

Esta propuesta no autoriza todavía la creación de productos ni cambios en la base de datos.

---

## Mejoras asistente técnico 14-11

**Estado:** Posible

**Fecha de registro:** 14/11/2026

**Tipo:** Asistente IA, orientación técnica y catálogo

**Decisión actual:** Mantener la lógica existente hasta autorizar expresamente esta implementación.

### Objetivo

Permitir que el asistente ayude tanto a clientes que buscan un producto concreto como a personas que describen un problema cotidiano o un proyecto completo, utilizando siempre productos reales del catálogo y sin ocultar materiales necesarios que SFI no tenga disponibles.

### Selector inicial de consulta

El cambio se aplicaría a las opciones de prerespuesta que actualmente aparecen bajo la conversación. No reemplazaría los módulos especializados ni las sugerencias contextuales generadas después de cada respuesta.

Al comenzar una nueva conversación, el asistente podría mostrar:

> ¿Con qué necesitas ayuda hoy?

- **Probar color en mi foto:** conserva el acceso directo al visualizador de pintura existente.
- **Buscar un producto:** inicia una búsqueda por nombre, uso, marca, característica o presupuesto.
- **Elegir una herramienta:** pregunta qué trabajo se realizará, sobre qué material y con qué frecuencia.
- **Ayuda con un proyecto o reparación:** orienta proyectos completos, calcula materiales y solicita medidas progresivamente.
- **Tengo un problema y no sé qué necesito:** permite describir una situación cotidiana y completar especificaciones guiadas antes de recomendar.

La selección orientaría la interpretación y los filtros iniciales, pero no debería bloquear el cambio de intención durante la conversación. Si el usuario escribe directamente su consulta, Gemini podría clasificarla sin obligarlo a seleccionar una opción.

Los accesos actuales `Pintar 50 m²`, `Renovar mi baño`, `Buscar un taladro` y `Preparar un muro` se reemplazarían por estas rutas generales. Sus capacidades no se eliminarían: pasarían a ser ejemplos o continuaciones dentro de la ruta correspondiente.

### Interpretación de las rutas

Cada botón debería enviar al backend un modo estructurado y permitido, además del texto visible:

- `producto`
- `herramienta`
- `proyecto_reparacion`
- `problema_cotidiano`
- `auto`, cuando el usuario escribe sin seleccionar una ruta

El modo funcionaría como contexto inicial, no como bloqueo permanente. La prioridad recomendada sería:

1. Intención explícita del mensaje actual.
2. Ruta seleccionada por el cliente.
3. Contexto reciente de la conversación.
4. Clasificación automática cuando no exista información suficiente.

De esta forma, alguien que comience buscando un producto podría después pedir ayuda para instalarlo sin iniciar otra conversación.

### Preguntas iniciales por ruta

- **Producto:** qué busca, para qué lo usará y si tiene alguna preferencia o presupuesto.
- **Herramienta:** trabajo que realizará, material sobre el que trabajará y uso ocasional o frecuente.
- **Proyecto o reparación:** qué quiere construir o reparar y cuáles son las medidas o condiciones conocidas.
- **Problema cotidiano:** qué ocurre, dónde ocurre, desde cuándo y qué características puede describir.

El asistente no debería mostrar todas estas preguntas juntas; seleccionaría como máximo dos o tres según la ruta y la información ya escrita.

Para problemas, proyectos y reparaciones se priorizarán las especificaciones escritas y preguntas guiadas. No se dependerá del análisis de fotografías para diagnosticar o calcular, porque exigiría instrucciones visuales mucho más extensas y aumentaría tiempo y ambigüedad. El uso de fotografías se mantendrá en el módulo especializado de pintura ya existente.

### Flujo conversacional propuesto

1. Clasificar la consulta como producto, herramienta, proyecto o problema cotidiano.
2. Solicitar como máximo dos o tres datos simples por mensaje.
3. Evitar inicialmente términos técnicos que un cliente común pueda desconocer.
4. Transformar las respuestas cotidianas en datos estructurados para Django.
5. Consultar productos, precios y stock reales.
6. Calcular cantidades mediante reglas verificadas en Python.
7. Entregar una solución accionable y distinguir claramente lo disponible de lo faltante.

### Resultado esperado

La respuesta final debería separar:

- Solución recomendada.
- Productos disponibles en SFI, con cantidades y precios.
- Materiales necesarios que no existen actualmente en el catálogo.
- Elementos opcionales o dependientes de las condiciones del lugar.
- Presupuesto completo o indicación explícita de que es parcial.
- Opción de agregar al carrito los productos válidos.
- Maestros aprobados de la especialidad y comuna como ayuda opcional.

Un proyecto no debe presentarse como completo si falta un componente obligatorio. Si SFI no dispone de ese componente, el asistente debe nombrarlo y explicar su función, sin inventar un sustituto.

### Guías técnicas profesionales

Como evolución futura, se podrían crear guías por sistema constructivo revisadas por maestros aprobados y posteriormente autorizadas por administración. Cada guía conservaría especialidad, profesional revisor, fecha, versión, condiciones de uso y reglas de cálculo.

Gemini interpretaría y explicaría la consulta; Django seleccionaría productos y ejecutaría las fórmulas aprobadas. Contactar a un profesional seguiría siendo una opción del cliente, no una acción automática ni un reemplazo de los cálculos del sistema.

### Reglas obligatorias

- No inventar productos, compatibilidades, rendimientos, precios ni stock.
- No reemplazar automáticamente un material faltante por otro incompatible.
- No presentar un presupuesto parcial como costo completo.
- Solicitar solamente datos que influyan realmente en la recomendación.
- Mantener las validaciones y cálculos importantes en Django.
- Permitir que una consulta cambie de producto a proyecto o herramienta sin reiniciar innecesariamente la conversación.
- No contactar a terceros ni compartir datos del cliente sin una acción y consentimiento explícitos.

### Primera etapa sugerida

Evaluar primero el selector inicial porque es un cambio pequeño y puede mejorar la clasificación sin reemplazar la lógica actual. Antes de implementarlo se deberá comprobar que:

- Mejora la precisión de producto, herramienta y proyecto.
- No obliga a realizar pasos adicionales a quien escribe una consulta directa.
- Conserva correctamente el contexto cuando cambia la intención.
- Es accesible mediante teclado y funciona en dispositivos móviles.
- Conserva el acceso directo al visualizador de pintura.
- No altera los cálculos, la búsqueda de productos ni las sugerencias contextuales existentes.
