# Ideas posibles para SFI

Este documento conserva propuestas teóricas que podrían incorporarse al proyecto en el futuro. No forman parte del alcance actual y no deben implementarse sin una solicitud explícita.

## Estado de las ideas

- **Posible:** propuesta aceptada para análisis futuro.
- **Priorizada:** seleccionada para diseñar su alcance.
- **En desarrollo:** implementación autorizada y comenzada.
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
