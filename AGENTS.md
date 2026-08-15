# Guía de trabajo para continuar el proyecto SFI

## Objetivo general

Continuar mejorando SFI como un ecommerce ferretero profesional, seguro, fácil de usar y preparado para trabajar con el asistente de inteligencia artificial.

## Forma de trabajar

- Antes de modificar una función, revisar completamente sus vistas, modelos, URLs, templates, JavaScript, CSS y pruebas relacionadas.
- Mantener las funcionalidades que ya funcionan.
- Realizar solamente los cambios necesarios para la tarea solicitada.
- Reutilizar componentes existentes antes de crear otros nuevos.
- Mantener la lógica importante en el backend.
- No inventar datos, productos, precios, stock ni resultados.
- Explicar brevemente qué se modificó al terminar.
- Realizar verificaciones enfocadas en la función modificada, sin ejecutar pruebas excesivas.
- No borrar datos, usuarios, productos o archivos sin autorización.
- No agregar Docker; el proyecto funciona localmente con Python, Django y MySQL.

## Diseño e interfaz

Mantener y mejorar la identidad visual de SFI:

- Azul oscuro, amarillo, blanco y verde.
- Apariencia moderna y profesional.
- Buena distribución de espacios.
- Textos claros y correctamente escritos.
- Diseño adaptable a computadores y celulares.
- Botones, formularios, tablas y estados visuales consistentes.
- Mismo menú lateral en todas las páginas administrativas.
- Mismo encabezado y footer en las páginas públicas.
- Corregir cualquier texto con caracteres dañados, como `ReposiciÃ³n`.

Cuando se mejore una pantalla:

1. Revisar primero el diseño existente.
2. Mantener los colores y componentes de SFI.
3. Ordenar la información según su importancia.
4. Mostrar mensajes claros de éxito y error.
5. Comprobar la visualización en pantalla grande y celular.

## Productos

Los productos deben tener información completa para el ecommerce y el asistente:

- Nombre.
- Marca.
- SKU o código.
- Categoría.
- Descripción.
- Precio.
- Stock.
- Stock mínimo.
- Proveedor.
- Imagen subida como archivo.
- Unidad de medida.
- Contenido por envase.
- Ficha técnica.
- Superficies compatibles.
- Estado activo o deshabilitado.

Las pinturas también deben contener:

- Color y código hexadecimal.
- Uso interior, exterior, piscina o especial.
- Tipo de pintura.
- Terminación.
- Rendimiento por litro.
- Capas recomendadas.
- Margen adicional.
- Tiempo de secado.
- Superficies compatibles.

Los campos exclusivos de pintura solamente deben aparecer cuando el producto corresponda a una pintura o material similar.

## Carrito y compras

- Permitir agregar, aumentar, disminuir y eliminar productos.
- Permitir dejar el carrito completamente vacío.
- Validar el stock antes de agregar y antes de pagar.
- Calcular precios y totales nuevamente en el servidor.
- No confiar en valores enviados por JavaScript.
- Evitar compras duplicadas al recargar o volver atrás.
- Mostrar mensajes claros cuando no exista stock suficiente.
- Mantener separados los flujos de retiro y despacho.
- Las boletas del cliente deben volver a “Mis compras”.
- Las boletas administrativas deben volver al historial general.

## Administración

El panel administrativo debe permitir gestionar claramente:

- Productos.
- Proveedores.
- Reposición de stock.
- Usuarios.
- Ventas.
- Retiros.
- Despachos.

Debe mostrar información útil como:

- Productos activos.
- Productos sin stock.
- Productos con stock mínimo.
- Solicitudes de reposición.
- Ventas registradas.
- Promedio por venta.
- Entregas pendientes.

Solo los administradores pueden ingresar a estas funciones. Los permisos deben comprobarse en el backend, no solamente ocultando botones.

## Proveedores y reposición

- Cada producto puede estar relacionado con un proveedor.
- Debe poder crearse un proveedor desde la administración.
- Debe mostrarse qué productos maneja cada proveedor.
- Cuando el stock alcance el mínimo, debe aparecer en reposición.
- El administrador puede preparar una solicitud de compra.
- El correo al proveedor debe indicar productos, cantidades y datos necesarios.
- No enviar una solicitud sin confirmación del administrador.

## Asistente SFI

El asistente debe responder utilizando información real del catálogo.

Debe poder:

- Buscar productos según la necesidad del cliente.
- Calcular materiales para pintura y proyectos básicos.
- Recomendar alternativas según presupuesto.
- Informar cuando el presupuesto no sea suficiente.
- Explicar cuánto dinero falta.
- Ofrecer opciones más económicas existentes.
- Agregar al carrito cantidades calculadas.
- Mantener la conversación al volver desde un producto.
- Analizar fotografías para recomendar pinturas.
- Diferenciar interiores, exteriores y piscinas.

La IA no debe realizar directamente los cálculos importantes. Los cálculos deben hacerse con funciones de Python y la IA debe interpretar la consulta y explicar el resultado.

La IA nunca debe:

- Inventar productos.
- Inventar precios o stock.
- Recomendar una pintura incompatible.
- Asegurar que una simulación visual representa exactamente el resultado real.
- Agregar productos sin validar nuevamente el stock.

## Seguridad

- Mantener protección CSRF.
- Validar autenticación y permisos en el backend.
- No exponer contraseñas, claves, tokens ni configuraciones privadas.
- Leer las claves desde `.env`.
- No guardar fotografías del asistente sin consentimiento.
- Validar tipo, tamaño y resolución de las imágenes.
- Aplicar límites de solicitudes al asistente.
- No mostrar errores internos o trazas al usuario.
- No permitir que un cliente acceda a información de otros usuarios.

## Base de datos

- No borrar o recrear la base de datos sin autorización.
- Si cambia un modelo, crear una migración nueva.
- No modificar migraciones antiguas ya aplicadas.
- Mantener actualizados los datos necesarios del catálogo.
- No colocar contraseñas ni datos privados dentro de migraciones o fixtures.

## Verificación

Después de cada mejora ejecutar, como mínimo:

```bash
python manage.py check
```

Luego ejecutar únicamente las pruebas relacionadas con la función modificada.

También comprobar manualmente:

- Que la página abra correctamente.
- Que el formulario guarde.
- Que los permisos funcionen.
- Que los errores se muestren claramente.
- Que no se haya afectado otra funcionalidad relacionada.

La forma de trabajo esperada es: comprender lo existente, mejorar la función conservando el estilo SFI, validar en el backend y comprobar el módulo trabajado.
