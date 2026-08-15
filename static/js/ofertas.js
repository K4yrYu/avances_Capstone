(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", function () {
        const pagina = document.getElementById("ofertas");
        const contenedor = document.getElementById("contenedor-ofertas");
        const contador = document.getElementById("contador-ofertas");
        const selectorOrden = document.getElementById("orden-ofertas");
        const seguridad = window.FerremasSecurity;

        if (!pagina || !contenedor || !contador || !selectorOrden || !seguridad) {
            return;
        }

        const {escapeHtml, safeUrl} = seguridad;
        const apiUrl = pagina.dataset.apiUrl;
        const imagenAlternativa = obtenerUrlSegura(pagina.dataset.placeholderUrl);
        let ofertas = [];

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

        function colorHexSeguro(valor) {
            const color = String(valor || "").trim();
            return /^#[0-9a-f]{6}$/i.test(color) ? color : "";
        }

        function precioClp(valor) {
            return new Intl.NumberFormat("es-CL", {
                style: "currency",
                currency: "CLP",
                maximumFractionDigits: 0,
            }).format(numeroSeguro(valor));
        }

        function calcularOferta(producto) {
            const precioAnterior = numeroSeguro(producto.precio_anterior);
            const precioActual = numeroSeguro(producto.precio);
            const ahorro = Math.max(0, precioAnterior - precioActual);
            const porcentaje = precioAnterior > 0 ? Math.round((ahorro / precioAnterior) * 100) : 0;
            return {precioAnterior, precioActual, ahorro, porcentaje};
        }

        function datosStock(stock, minimo) {
            if (stock <= 0) return {clase: "out", texto: "Agotado"};
            if (stock <= minimo) return {clase: "low", texto: `Últimas ${stock}`};
            return {clase: "", texto: `${stock} disponibles`};
        }

        function ordenar(lista) {
            return [...lista].sort((a, b) => {
                const ofertaA = calcularOferta(a);
                const ofertaB = calcularOferta(b);

                if (selectorOrden.value === "descuento-desc") {
                    return ofertaB.porcentaje - ofertaA.porcentaje || a._indice - b._indice;
                }
                if (selectorOrden.value === "ahorro-desc") {
                    return ofertaB.ahorro - ofertaA.ahorro || a._indice - b._indice;
                }
                if (selectorOrden.value === "precio-asc") {
                    return ofertaA.precioActual - ofertaB.precioActual || a._indice - b._indice;
                }
                return a._indice - b._indice;
            });
        }

        function tarjeta(producto) {
            const id = Math.max(0, Math.trunc(numeroSeguro(producto.id)));
            const stock = Math.max(0, Math.trunc(numeroSeguro(producto.stock)));
            const stockMinimo = Math.max(0, Math.trunc(numeroSeguro(producto.stock_minimo)));
            const nombre = escapeHtml(producto.nombre || "Producto sin nombre");
            const categoria = escapeHtml(producto.categoria || "Oferta SFI");
            const descripcion = escapeHtml(producto.descripcion || "Producto con precio rebajado.");
            const imagen = safeUrl(producto.imagen) || escapeHtml(imagenAlternativa);
            const detalleUrl = `/productos/${id}/`;
            const oferta = calcularOferta(producto);
            const stockInfo = datosStock(stock, stockMinimo);
            const marca = escapeHtml(producto.marca || "SFI");
            const presentacion = escapeHtml(producto.presentacion || "Unidad");
            const color = escapeHtml(producto.color || "");
            const colorHex = colorHexSeguro(producto.color_hex);
            const colorMeta = color
                ? `<span class="offer-color-meta">${colorHex ? `<i style="--product-color:${colorHex}" aria-hidden="true"></i>` : ""}${color}</span>`
                : "";
            const boton = stock > 0
                ? `<a class="offer-detail-button" href="${detalleUrl}">Ver producto <i class="fa-solid fa-arrow-right" aria-hidden="true"></i></a>`
                : `<span class="offer-detail-button disabled" aria-disabled="true">Sin stock</span>`;

            return `
                <article class="offer-card">
                    <a class="offer-image-link" href="${detalleUrl}" aria-label="Ver ${nombre}">
                        <span class="discount-badge"><strong>-${oferta.porcentaje}%</strong><span>descuento</span></span>
                        <span class="offer-stock ${stockInfo.clase}">${escapeHtml(stockInfo.texto)}</span>
                        <img class="offer-image" src="${imagen}" alt="${nombre}" loading="lazy">
                    </a>
                    <div class="offer-card-body">
                        <p class="offer-category">${categoria}</p>
                        <h2><a href="${detalleUrl}">${nombre}</a></h2>
                        <div class="offer-technical-meta"><span>${marca}</span><span>${presentacion}</span>${colorMeta}</div>
                        <p class="offer-description">${descripcion}</p>
                        <div class="offer-pricing">
                            <div class="offer-price-values">
                                <span class="old-price">Antes ${escapeHtml(precioClp(oferta.precioAnterior))}</span>
                                <strong class="current-price">${escapeHtml(precioClp(oferta.precioActual))}</strong>
                                <span class="saving-label">Ahorras ${escapeHtml(precioClp(oferta.ahorro))}</span>
                            </div>
                            ${boton}
                        </div>
                    </div>
                </article>
            `;
        }

        function conectarImagenesAlternativas() {
            contenedor.querySelectorAll(".offer-image").forEach(imagen => {
                imagen.addEventListener("error", function reemplazarImagen() {
                    imagen.removeEventListener("error", reemplazarImagen);
                    if (imagenAlternativa) imagen.src = imagenAlternativa;
                });
            });
        }

        function renderizar() {
            const ordenadas = ordenar(ofertas);
            contador.textContent = `${ordenadas.length} ${ordenadas.length === 1 ? "oferta" : "ofertas"}`;

            if (!ordenadas.length) {
                contenedor.innerHTML = `
                    <div class="offers-empty">
                        <i class="fa-solid fa-tags" aria-hidden="true"></i>
                        <h2>No hay ofertas activas por ahora</h2>
                        <p>Cuando el precio de un producto baje respecto de su último precio, aparecerá automáticamente en esta sección.</p>
                    </div>
                `;
            } else {
                contenedor.innerHTML = ordenadas.map(tarjeta).join("");
                conectarImagenesAlternativas();
            }
            contenedor.setAttribute("aria-busy", "false");
        }

        async function cargarOfertas() {
            try {
                const separador = apiUrl.includes("?") ? "&" : "?";
                const respuesta = await fetch(`${apiUrl}${separador}nocache=${Date.now()}`, {
                    headers: {Accept: "application/json"},
                });
                if (!respuesta.ok) throw new Error(`Respuesta ${respuesta.status}`);

                const datos = await respuesta.json();
                if (!Array.isArray(datos)) throw new Error("Formato de ofertas inválido");

                ofertas = datos
                    .filter(producto => numeroSeguro(producto.precio_anterior) > numeroSeguro(producto.precio))
                    .map((producto, indice) => ({...producto, _indice: indice}));
                renderizar();
            } catch (_error) {
                contador.textContent = "Ofertas no disponibles";
                contenedor.innerHTML = `
                    <div class="offers-error" role="alert">
                        <i class="fa-solid fa-triangle-exclamation" aria-hidden="true"></i>
                        <h2>No pudimos cargar las ofertas</h2>
                        <p>Revisa tu conexión e intenta recargar la página.</p>
                    </div>
                `;
                contenedor.setAttribute("aria-busy", "false");
            }
        }

        selectorOrden.addEventListener("change", renderizar);
        cargarOfertas();
    });
})();
