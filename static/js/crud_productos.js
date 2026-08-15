(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", function () {
        const pagina = document.getElementById("contenido-productos");
        const tabla = document.getElementById("tabla-productos-admin");
        const buscador = document.getElementById("buscar-producto");
        const filtroCategoria = document.getElementById("filtro-categoria");
        const filtroEstado = document.getElementById("filtro-estado");
        const filtroStock = document.getElementById("filtro-stock");
        const selectorOrden = document.getElementById("orden-productos-admin");
        const botonLimpiar = document.getElementById("limpiar-filtros-admin");
        const contador = document.getElementById("contador-resultados");
        const seguridad = window.FerremasSecurity;

        if (!pagina || !tabla || !seguridad || !window.bootstrap) {
            return;
        }

        const {escapeHtml, safeUrl} = seguridad;
        const apiUrl = pagina.dataset.apiUrl;
        const toggleUrlBase = pagina.dataset.toggleUrl;
        const editUrlBase = pagina.dataset.editUrl;
        const imagenAlternativa = obtenerUrlSegura(pagina.dataset.placeholderUrl);
        const modalElemento = document.getElementById("modalEstadoProducto");
        const modal = new bootstrap.Modal(modalElemento);
        const toastElemento = document.getElementById("notificacionProducto");
        const toast = new bootstrap.Toast(toastElemento, {delay: 3500});
        let productos = [];
        let productoPendiente = null;

        function obtenerUrlSegura(valor) {
            try {
                const url = new URL(String(valor || ""), window.location.origin);
                return ["http:", "https:"].includes(url.protocol) ? url.href : "";
            } catch (_error) {
                return "";
            }
        }

        function numeroSeguro(valor) {
            const numero = Number(valor);
            return Number.isFinite(numero) ? numero : 0;
        }

        function normalizar(valor) {
            return String(valor || "")
                .normalize("NFD")
                .replace(/[\u0300-\u036f]/g, "")
                .toLocaleLowerCase("es");
        }

        function precioClp(valor) {
            return new Intl.NumberFormat("es-CL", {
                style: "currency",
                currency: "CLP",
                maximumFractionDigits: 0,
            }).format(numeroSeguro(valor));
        }

        function crearUrl(base, id) {
            return base.replace(/\/0\/$/, `/${id}/`);
        }

        function obtenerCookie(nombre) {
            const prefijo = `${nombre}=`;
            const cookie = document.cookie.split(";").map(valor => valor.trim()).find(valor => valor.startsWith(prefijo));
            return cookie ? decodeURIComponent(cookie.slice(prefijo.length)) : "";
        }

        function completarCategorias() {
            const categorias = [...new Set(
                productos.map(producto => String(producto.categoria || "Otra").trim()).filter(Boolean)
            )].sort((a, b) => a.localeCompare(b, "es", {sensitivity: "base"}));

            filtroCategoria.replaceChildren(new Option("Todas", ""));
            categorias.forEach(categoria => filtroCategoria.add(new Option(categoria, categoria)));
        }

        function actualizarMetricas() {
            const activos = productos.filter(producto => producto.activo);
            document.getElementById("metrica-total").textContent = productos.length;
            document.getElementById("metrica-activos").textContent = activos.length;
            document.getElementById("metrica-bajo").textContent = activos.filter(producto => {
                const stock = numeroSeguro(producto.stock);
                return stock > 0 && stock <= 5;
            }).length;
            document.getElementById("metrica-agotados").textContent = activos.filter(producto => numeroSeguro(producto.stock) === 0).length;
        }

        function productosVisibles() {
            const texto = normalizar(buscador.value.trim());
            const categoria = filtroCategoria.value;
            const estado = filtroEstado.value;
            const stockFiltro = filtroStock.value;

            const filtrados = productos.filter(producto => {
                const stock = numeroSeguro(producto.stock);
                const coincideTexto = !texto || normalizar(
                    `${producto.id} ${producto.nombre || ""} ${producto.descripcion || ""}`
                ).includes(texto);
                const coincideCategoria = !categoria || producto.categoria === categoria;
                const coincideEstado = !estado
                    || (estado === "activo" && producto.activo)
                    || (estado === "inactivo" && !producto.activo);
                const coincideStock = !stockFiltro
                    || (stockFiltro === "disponible" && stock > 5)
                    || (stockFiltro === "bajo" && stock > 0 && stock <= 5)
                    || (stockFiltro === "agotado" && stock === 0);
                return coincideTexto && coincideCategoria && coincideEstado && coincideStock;
            });

            return filtrados.sort((a, b) => {
                const nombreA = String(a.nombre || "");
                const nombreB = String(b.nombre || "");
                if (selectorOrden.value === "recientes") return numeroSeguro(b.id) - numeroSeguro(a.id);
                if (selectorOrden.value === "precio-desc") return numeroSeguro(b.precio) - numeroSeguro(a.precio) || nombreA.localeCompare(nombreB, "es");
                if (selectorOrden.value === "stock-asc") return numeroSeguro(a.stock) - numeroSeguro(b.stock) || nombreA.localeCompare(nombreB, "es");
                return nombreA.localeCompare(nombreB, "es", {sensitivity: "base"});
            });
        }

        function datosStock(stock) {
            if (stock <= 0) return {clase: "out", texto: "Sin stock"};
            if (stock <= 5) return {clase: "low", texto: `${stock} · Bajo`};
            return {clase: "", texto: `${stock} unidades`};
        }

        function filaProducto(producto) {
            const id = Math.max(0, Math.trunc(numeroSeguro(producto.id)));
            const stock = Math.max(0, Math.trunc(numeroSeguro(producto.stock)));
            const nombre = escapeHtml(producto.nombre || "Producto sin nombre");
            const descripcion = escapeHtml(producto.descripcion || "Sin descripción");
            const categoria = escapeHtml(producto.categoria || "Otra");
            const imagen = safeUrl(producto.imagen) || escapeHtml(imagenAlternativa);
            const stockInfo = datosStock(stock);
            const activo = Boolean(producto.activo);
            const editar = activo
                ? `<a class="action-button edit" href="${crearUrl(editUrlBase, id)}"><i class="fa-solid fa-pen" aria-hidden="true"></i> Editar</a>`
                : "";

            return `
                <tr>
                    <td>
                        <div class="product-cell">
                            <span class="product-thumb"><img src="${imagen}" alt="${nombre}" loading="lazy"></span>
                            <div>
                                <strong title="${nombre}">${nombre}</strong>
                                <small title="${descripcion}">${descripcion}</small>
                                <span class="product-id">ID #${id}</span>
                            </div>
                        </div>
                    </td>
                    <td><span class="category-badge">${categoria}</span></td>
                    <td><strong class="product-price-admin">${escapeHtml(precioClp(producto.precio))}</strong></td>
                    <td><span class="stock-admin-badge ${stockInfo.clase}">${escapeHtml(stockInfo.texto)}</span></td>
                    <td>
                        <span class="status-admin-badge ${activo ? "" : "inactive"}">
                            <i class="fa-solid fa-circle" aria-hidden="true"></i> ${activo ? "Activo" : "Deshabilitado"}
                        </span>
                    </td>
                    <td>
                        <div class="product-actions">
                            ${editar}
                            <button class="action-button toggle ${activo ? "" : "activate"}" type="button" data-toggle-product="${id}">
                                <i class="fa-solid ${activo ? "fa-eye-slash" : "fa-rotate-left"}" aria-hidden="true"></i>
                                ${activo ? "Desactivar" : "Reactivar"}
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        }

        function conectarImagenes() {
            tabla.querySelectorAll(".product-thumb img").forEach(imagen => {
                imagen.addEventListener("error", function reemplazarImagen() {
                    imagen.removeEventListener("error", reemplazarImagen);
                    if (imagenAlternativa) imagen.src = imagenAlternativa;
                });
            });
        }

        function renderizar() {
            const visibles = productosVisibles();
            contador.textContent = `${visibles.length} ${visibles.length === 1 ? "resultado" : "resultados"}`;

            if (!visibles.length) {
                tabla.innerHTML = `
                    <tr class="empty-inventory-row">
                        <td colspan="6">
                            <div class="empty-inventory">
                                <i class="fa-solid fa-magnifying-glass" aria-hidden="true"></i>
                                <strong>No encontramos productos</strong>
                                <span>Prueba cambiando o limpiando los filtros.</span>
                            </div>
                        </td>
                    </tr>
                `;
            } else {
                tabla.innerHTML = visibles.map(filaProducto).join("");
                conectarImagenes();
            }
            tabla.setAttribute("aria-busy", "false");
        }

        function limpiarFiltros() {
            buscador.value = "";
            filtroCategoria.value = "";
            filtroEstado.value = "";
            filtroStock.value = "";
            selectorOrden.value = "nombre-asc";
            renderizar();
            buscador.focus();
        }

        function prepararCambioEstado(producto) {
            productoPendiente = producto;
            const activar = !producto.activo;
            const icono = document.getElementById("iconoModalEstado");
            const confirmar = document.getElementById("confirmarEstadoProducto");

            document.getElementById("tituloModalEstado").textContent = activar ? "Reactivar producto" : "Desactivar producto";
            document.getElementById("mensajeModalEstado").textContent = activar
                ? "El producto volverá a mostrarse en el catálogo público."
                : "El producto dejará de mostrarse a los clientes, pero sus datos se conservarán.";
            document.getElementById("productoModalEstado").textContent = producto.nombre || "Producto sin nombre";
            document.getElementById("ayudaModalEstado").textContent = activar
                ? "Podrás editarlo y administrarlo normalmente."
                : "Puedes reactivarlo en cualquier momento desde esta misma pantalla.";
            confirmar.textContent = activar ? "Sí, reactivar" : "Sí, desactivar";
            confirmar.classList.toggle("activate", activar);
            icono.classList.toggle("activate", activar);
            icono.innerHTML = `<i class="fa-solid ${activar ? "fa-rotate-left" : "fa-eye-slash"}" aria-hidden="true"></i>`;
            modal.show();
        }

        function mostrarNotificacion(mensaje, esError) {
            document.getElementById("mensajeNotificacion").textContent = mensaje;
            document.getElementById("iconoNotificacion").className = esError
                ? "fa-solid fa-circle-exclamation"
                : "fa-solid fa-circle-check";
            toastElemento.classList.toggle("error", Boolean(esError));
            toast.show();
        }

        async function cambiarEstado() {
            if (!productoPendiente) return;

            const confirmar = document.getElementById("confirmarEstadoProducto");
            const textoOriginal = confirmar.textContent;
            confirmar.disabled = true;
            confirmar.innerHTML = '<i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i> Guardando';

            try {
                const respuesta = await fetch(crearUrl(toggleUrlBase, productoPendiente.id), {
                    method: "PATCH",
                    credentials: "same-origin",
                    headers: {"X-CSRFToken": obtenerCookie("csrftoken"), Accept: "application/json"},
                });
                const datos = await respuesta.json().catch(() => ({}));
                if (!respuesta.ok) throw new Error(datos.error || "No fue posible actualizar el producto.");

                productoPendiente.activo = Boolean(datos.activo);
                actualizarMetricas();
                renderizar();
                modal.hide();
                mostrarNotificacion(datos.mensaje || "Estado actualizado correctamente.", false);
                productoPendiente = null;
            } catch (error) {
                mostrarNotificacion(error.message || "Error al conectar con el servidor.", true);
            } finally {
                confirmar.disabled = false;
                confirmar.textContent = textoOriginal;
            }
        }

        async function cargarProductos() {
            try {
                const respuesta = await fetch(apiUrl, {
                    credentials: "same-origin",
                    headers: {Accept: "application/json"},
                });
                if (!respuesta.ok) throw new Error("No fue posible cargar el inventario.");
                const datos = await respuesta.json();
                if (!Array.isArray(datos)) throw new Error("El servidor devolvió un formato inválido.");

                productos = datos;
                completarCategorias();
                actualizarMetricas();
                renderizar();
            } catch (error) {
                contador.textContent = "No disponible";
                tabla.innerHTML = `
                    <tr class="empty-inventory-row">
                        <td colspan="6">
                            <div class="empty-inventory">
                                <i class="fa-solid fa-triangle-exclamation" aria-hidden="true"></i>
                                <strong>No pudimos cargar los productos</strong>
                                <span>${escapeHtml(error.message)}</span>
                            </div>
                        </td>
                    </tr>
                `;
                tabla.setAttribute("aria-busy", "false");
            }
        }

        [buscador, filtroCategoria, filtroEstado, filtroStock, selectorOrden].forEach(control => {
            control.addEventListener(control === buscador ? "input" : "change", renderizar);
        });
        botonLimpiar.addEventListener("click", limpiarFiltros);
        tabla.addEventListener("click", function (evento) {
            const boton = evento.target.closest("[data-toggle-product]");
            if (!boton) return;
            const id = numeroSeguro(boton.dataset.toggleProduct);
            const producto = productos.find(item => numeroSeguro(item.id) === id);
            if (producto) prepararCambioEstado(producto);
        });
        document.getElementById("confirmarEstadoProducto").addEventListener("click", cambiarEstado);
        modalElemento.addEventListener("hidden.bs.modal", function () {
            productoPendiente = null;
        });

        cargarProductos();
    });
})();
