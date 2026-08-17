(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", function () {
        const catalogo = document.getElementById("catalogo");
        if (!catalogo) {
            return;
        }

        const seguridad = window.FerremasSecurity;
        const lista = document.getElementById("product-list");
        const buscador = document.getElementById("buscador-productos");
        const filtroCategoria = document.getElementById("filtro-categoria");
        const selectorOrden = document.getElementById("orden-productos");
        const selectorMoneda = document.getElementById("moneda-selector");
        const botonLimpiar = document.getElementById("limpiar-filtros");
        const contador = document.getElementById("contador-resultados");
        const totalHero = document.getElementById("total-productos-hero");
        const avisoMoneda = document.getElementById("aviso-moneda");

        if (!seguridad || !lista || !buscador || !filtroCategoria || !selectorOrden || !selectorMoneda) {
            if (lista) {
                lista.innerHTML = estadoError("No fue posible iniciar el catálogo.");
                lista.setAttribute("aria-busy", "false");
            }
            return;
        }

        const {escapeHtml, safeUrl} = seguridad;
        const monedasPermitidas = new Set(["CLP", "USD", "EUR", "BRL"]);
        const apiUrl = catalogo.dataset.apiUrl;
        const imagenAlternativa = obtenerUrlSegura(catalogo.dataset.placeholderUrl);
        let productos = [];
        let tasaCambio = 1;
        let monedaActual = localStorage.getItem("moneda") || "CLP";

        if (!monedasPermitidas.has(monedaActual)) {
            monedaActual = "CLP";
        }
        selectorMoneda.value = monedaActual;

        function obtenerUrlSegura(valor) {
            try {
                const url = new URL(String(valor || ""), window.location.origin);
                return ["http:", "https:"].includes(url.protocol) ? url.href : "";
            } catch (_error) {
                return "";
            }
        }

        function normalizar(valor) {
            return String(valor || "")
                .normalize("NFD")
                .replace(/[\u0300-\u036f]/g, "")
                .toLocaleLowerCase("es");
        }

        function numeroSeguro(valor) {
            const numero = Number(valor);
            return Number.isFinite(numero) ? numero : 0;
        }

        function colorHexSeguro(valor) {
            const color = String(valor || "").trim();
            return /^#[0-9a-f]{6}$/i.test(color) ? color : "";
        }

        function formatoPrecio(precio) {
            return new Intl.NumberFormat("es-CL", {
                style: "currency",
                currency: monedaActual,
                maximumFractionDigits: monedaActual === "CLP" ? 0 : 2,
            }).format(numeroSeguro(precio) * tasaCambio);
        }

        function estadoError(mensaje) {
            return `
                <div class="catalog-error" role="alert">
                    <i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
                    <h2>No pudimos cargar los productos</h2>
                    <p>${escapeHtml(mensaje)}</p>
                </div>
            `;
        }

        function completarCategorias() {
            const categorias = [...new Set(
                productos
                    .map(producto => String(producto.categoria || "").trim())
                    .filter(Boolean)
            )].sort((a, b) => a.localeCompare(b, "es", {sensitivity: "base"}));

            filtroCategoria.replaceChildren(new Option("Todas las categorías", ""));
            categorias.forEach(categoria => filtroCategoria.add(new Option(categoria, categoria)));
        }

        function leerFiltrosDesdeUrl() {
            const parametros = new URLSearchParams(window.location.search);
            const categoria = parametros.get("categoria") || "";
            const orden = parametros.get("orden") || "destacados";

            buscador.value = parametros.get("buscar") || "";
            filtroCategoria.value = [...filtroCategoria.options].some(opcion => opcion.value === categoria)
                ? categoria
                : "";
            selectorOrden.value = [...selectorOrden.options].some(opcion => opcion.value === orden)
                ? orden
                : "destacados";
        }

        function actualizarUrl() {
            const parametros = new URLSearchParams();
            const busqueda = buscador.value.trim();

            if (busqueda) parametros.set("buscar", busqueda);
            if (filtroCategoria.value) parametros.set("categoria", filtroCategoria.value);
            if (selectorOrden.value !== "destacados") parametros.set("orden", selectorOrden.value);

            const consulta = parametros.toString();
            const nuevaUrl = `${window.location.pathname}${consulta ? `?${consulta}` : ""}${window.location.hash}`;
            window.history.replaceState({}, "", nuevaUrl);
        }

        function ordenarProductos(listaProductos) {
            const orden = selectorOrden.value;
            const porNombre = (a, b) => String(a.nombre || "").localeCompare(
                String(b.nombre || ""), "es", {sensitivity: "base"}
            );

            return [...listaProductos].sort((a, b) => {
                if (orden === "nombre-asc") return porNombre(a, b);
                if (orden === "nombre-desc") return porNombre(b, a);
                if (orden === "precio-asc") return numeroSeguro(a.precio) - numeroSeguro(b.precio) || porNombre(a, b);
                if (orden === "precio-desc") return numeroSeguro(b.precio) - numeroSeguro(a.precio) || porNombre(a, b);
                if (orden === "stock-desc") return numeroSeguro(b.stock) - numeroSeguro(a.stock) || porNombre(a, b);
                return numeroSeguro(b.id) - numeroSeguro(a.id);
            });
        }

        function obtenerProductosVisibles() {
            const texto = normalizar(buscador.value.trim());
            const categoria = filtroCategoria.value;

            const filtrados = productos.filter(producto => {
                const coincideTexto = !texto || normalizar(
                    `${producto.sku || ""} ${producto.nombre || ""} ${producto.descripcion || ""} ${producto.categoria || ""} ${producto.marca || ""} ${producto.modelo || ""} ${producto.color || ""} ${producto.ambiente_uso_display || ""} ${producto.presentacion || ""}`
                ).includes(texto);
                const coincideCategoria = !categoria || producto.categoria === categoria;
                return coincideTexto && coincideCategoria;
            });

            return ordenarProductos(filtrados);
        }

        function datosStock(stock, minimo) {
            if (stock <= 0) {
                return {clase: "stock-out", texto: "Agotado"};
            }
            if (stock <= minimo) {
                return {clase: "stock-low", texto: `Últimas ${stock} unidades`};
            }
            return {clase: "stock-available", texto: `${stock} disponibles`};
        }

        function tarjetaProducto(producto) {
            const id = Math.max(0, Math.trunc(numeroSeguro(producto.id)));
            const stock = Math.max(0, Math.trunc(numeroSeguro(producto.stock)));
            const stockMinimo = Math.max(0, Math.trunc(numeroSeguro(producto.stock_minimo)));
            const nombre = escapeHtml(producto.nombre || "Producto sin nombre");
            const categoria = escapeHtml(producto.categoria || "Sin categoría");
            const descripcion = escapeHtml(producto.descripcion || "Conoce los detalles de este producto.");
            const imagen = safeUrl(producto.imagen) || escapeHtml(imagenAlternativa);
            const stockInfo = datosStock(stock, stockMinimo);
            const marca = escapeHtml(producto.marca || "SFI");
            const presentacion = escapeHtml(producto.presentacion || "Unidad");
            const color = escapeHtml(producto.color || "");
            const colorHex = colorHexSeguro(producto.color_hex);
            const colorMeta = color
                ? `<span class="product-color-meta">${colorHex ? `<i style="--product-color:${colorHex}" aria-hidden="true"></i>` : ""}${color}</span>`
                : "";
            const environment = producto.ambiente_uso && producto.ambiente_uso !== "no_aplica"
                ? `<span><i class="fa-solid fa-house-circle-check" aria-hidden="true"></i>${escapeHtml(producto.ambiente_uso_display || producto.ambiente_uso)}</span>`
                : "";
            const detalleUrl = `/productos/${id}/`;
            const boton = stock > 0
                ? `<a class="product-detail-button" href="${detalleUrl}">Ver producto <i class="fas fa-arrow-right" aria-hidden="true"></i></a>`
                : `<span class="product-detail-button disabled" aria-disabled="true">Sin stock</span>`;

            return `
                <article class="catalog-card">
                    <a class="catalog-image-link" href="${detalleUrl}" aria-label="Ver ${nombre}">
                        <span class="stock-badge ${stockInfo.clase}">
                            <i class="fas fa-circle" aria-hidden="true"></i>${escapeHtml(stockInfo.texto)}
                        </span>
                        <img class="catalog-image" src="${imagen}" alt="${nombre}" loading="lazy">
                    </a>
                    <div class="catalog-card-body">
                        <p class="product-category">${categoria}</p>
                        <h2><a href="${detalleUrl}">${nombre}</a></h2>
                        <div class="product-technical-meta"><span><i class="fa-solid fa-copyright" aria-hidden="true"></i>${marca}</span><span><i class="fa-solid fa-box-open" aria-hidden="true"></i>${presentacion}</span>${colorMeta}${environment}</div>
                        <p class="product-description">${descripcion}</p>
                        <div class="card-purchase-row">
                            <div class="price-wrap">
                                <span class="price-label">Precio</span>
                                <strong class="product-price">${escapeHtml(formatoPrecio(producto.precio))}</strong>
                            </div>
                            ${boton}
                        </div>
                    </div>
                </article>
            `;
        }

        function conectarImagenesAlternativas() {
            lista.querySelectorAll(".catalog-image").forEach(imagen => {
                imagen.addEventListener("error", function reemplazarImagen() {
                    imagen.removeEventListener("error", reemplazarImagen);
                    if (imagenAlternativa) {
                        imagen.src = imagenAlternativa;
                        imagen.classList.add("catalog-image-fallback");
                    }
                });
            });
        }

        function renderizar() {
            const visibles = obtenerProductosVisibles();
            const cantidad = visibles.length;
            contador.textContent = `${cantidad} ${cantidad === 1 ? "producto" : "productos"}`;
            actualizarUrl();

            if (!cantidad) {
                lista.innerHTML = `
                    <div class="catalog-empty">
                        <i class="fas fa-magnifying-glass" aria-hidden="true"></i>
                        <h2>No encontramos coincidencias</h2>
                        <p>Prueba con otro término o limpia los filtros para ver todo el catálogo.</p>
                        <button type="button" class="btn btn-sfi-primary" id="reiniciar-catalogo">Ver todos los productos</button>
                    </div>
                `;
                document.getElementById("reiniciar-catalogo").addEventListener("click", limpiarFiltros);
            } else {
                lista.innerHTML = visibles.map(tarjetaProducto).join("");
                conectarImagenesAlternativas();
            }
            lista.setAttribute("aria-busy", "false");
        }

        function limpiarFiltros() {
            buscador.value = "";
            filtroCategoria.value = "";
            selectorOrden.value = "destacados";
            renderizar();
            buscador.focus();
        }

        async function configurarMoneda(moneda) {
            if (!monedasPermitidas.has(moneda) || moneda === "CLP") {
                monedaActual = "CLP";
                tasaCambio = 1;
                selectorMoneda.value = "CLP";
                localStorage.setItem("moneda", "CLP");
                avisoMoneda.textContent = "";
                return;
            }

            avisoMoneda.textContent = "Actualizando conversión…";
            try {
                const respuesta = await fetch("https://open.er-api.com/v6/latest/CLP");
                if (!respuesta.ok) throw new Error("Servicio de conversión no disponible");
                const datos = await respuesta.json();
                const nuevaTasa = numeroSeguro(datos.rates?.[moneda]);
                if (nuevaTasa <= 0) throw new Error("Tasa de conversión inválida");

                monedaActual = moneda;
                tasaCambio = nuevaTasa;
                localStorage.setItem("moneda", monedaActual);
                avisoMoneda.textContent = "Conversión referencial actualizada.";
            } catch (_error) {
                monedaActual = "CLP";
                tasaCambio = 1;
                selectorMoneda.value = "CLP";
                localStorage.setItem("moneda", "CLP");
                avisoMoneda.textContent = "No pudimos convertir ahora; los precios se muestran en CLP.";
            }
        }

        async function cargarProductos() {
            try {
                const separador = apiUrl.includes("?") ? "&" : "?";
                const respuesta = await fetch(`${apiUrl}${separador}nocache=${Date.now()}`, {
                    headers: {Accept: "application/json"},
                });
                if (!respuesta.ok) throw new Error(`Respuesta ${respuesta.status}`);

                const datos = await respuesta.json();
                if (!Array.isArray(datos)) throw new Error("Formato de catálogo inválido");

                productos = datos;
                totalHero.textContent = productos.length;
                completarCategorias();
                leerFiltrosDesdeUrl();
                await configurarMoneda(monedaActual);
                renderizar();
            } catch (_error) {
                contador.textContent = "Catálogo no disponible";
                totalHero.textContent = "0";
                lista.innerHTML = estadoError("Revisa tu conexión e intenta recargar la página.");
                lista.setAttribute("aria-busy", "false");
            }
        }

        buscador.addEventListener("input", renderizar);
        filtroCategoria.addEventListener("change", renderizar);
        selectorOrden.addEventListener("change", renderizar);
        botonLimpiar.addEventListener("click", limpiarFiltros);
        selectorMoneda.addEventListener("change", async function () {
            await configurarMoneda(selectorMoneda.value);
            renderizar();
        });

        cargarProductos();
    });
})();
