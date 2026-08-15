(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", function () {
        const pagina = document.getElementById("contenido-ventas");
        const tabla = document.getElementById("tabla-historial-ventas");
        const buscador = document.getElementById("buscar-venta");
        const fechaDesde = document.getElementById("fecha-desde-venta");
        const fechaHasta = document.getElementById("fecha-hasta-venta");
        const filtroEntrega = document.getElementById("filtro-entrega-venta");
        const filtroEstado = document.getElementById("filtro-estado-entrega");
        const selectorOrden = document.getElementById("orden-ventas");
        const botonLimpiar = document.getElementById("limpiar-filtros-ventas");
        const contador = document.getElementById("contador-ventas");
        const seguridad = window.FerremasSecurity;

        if (!pagina || !tabla || !seguridad) return;

        const {escapeHtml} = seguridad;
        const apiUrl = pagina.dataset.apiUrl;
        const receiptUrlBase = pagina.dataset.receiptUrl;
        let ventas = [];

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

        function crearUrl(base, id) {
            return base.replace(/\/0\/$/, `/${id}/`);
        }

        function precioClp(valor) {
            return new Intl.NumberFormat("es-CL", {
                style: "currency",
                currency: "CLP",
                maximumFractionDigits: 0,
            }).format(numeroSeguro(valor));
        }

        function fechaValida(valor) {
            const fecha = new Date(valor);
            return Number.isNaN(fecha.getTime()) ? null : fecha;
        }

        function fechaIso(venta) {
            return String(venta.fecha_compra || "").slice(0, 10);
        }

        function fechaFormateada(valor) {
            const fecha = fechaValida(valor);
            if (!fecha) return {fecha: "Sin fecha", hora: "—"};
            return {
                fecha: new Intl.DateTimeFormat("es-CL", {day: "2-digit", month: "short", year: "numeric"}).format(fecha),
                hora: new Intl.DateTimeFormat("es-CL", {hour: "2-digit", minute: "2-digit"}).format(fecha),
            };
        }

        function nombreCliente(venta) {
            const usuario = venta.id_usuario || {};
            const nombre = `${usuario.first_name || ""} ${usuario.last_name || ""}`.trim();
            return nombre || usuario.username || "Cliente sin nombre";
        }

        function iniciales(venta) {
            return nombreCliente(venta).split(/\s+/).filter(Boolean).slice(0, 2)
                .map(parte => parte.charAt(0)).join("").toUpperCase() || "C";
        }

        function textoPago(estado) {
            const normalizado = normalizar(estado);
            if (normalizado.includes("authoriz") || normalizado.includes("autoriz")) return "Autorizado";
            if (normalizado.includes("success") || normalizado.includes("exitos")) return "Confirmado";
            return estado ? String(estado) : "Confirmado";
        }

        function actualizarMetricas() {
            const ingresos = ventas.reduce((total, venta) => total + numeroSeguro(venta.total_venta), 0);
            const pendientes = ventas.filter(venta => venta.estado_entrega === "pendiente").length;
            document.getElementById("metrica-ventas-total").textContent = ventas.length;
            document.getElementById("metrica-ingresos-total").textContent = precioClp(ingresos);
            document.getElementById("metrica-ticket-promedio").textContent = precioClp(ventas.length ? ingresos / ventas.length : 0);
            document.getElementById("metrica-entregas-pendientes").textContent = pendientes;
        }

        function ventasVisibles() {
            const texto = normalizar(buscador.value.trim());
            const desde = fechaDesde.value;
            const hasta = fechaHasta.value;
            const entrega = filtroEntrega.value;
            const estado = filtroEstado.value;

            const filtradas = ventas.filter(venta => {
                const usuario = venta.id_usuario || {};
                const textoVenta = `${venta.id} ${nombreCliente(venta)} ${usuario.username || ""} ${usuario.rut || ""}`;
                const fecha = fechaIso(venta);
                return (!texto || normalizar(textoVenta).includes(texto))
                    && (!desde || fecha >= desde)
                    && (!hasta || fecha <= hasta)
                    && (!entrega || venta.tipo_entrega === entrega)
                    && (!estado || venta.estado_entrega === estado);
            });

            return filtradas.sort((a, b) => {
                const fechaA = fechaValida(a.fecha_compra)?.getTime() || 0;
                const fechaB = fechaValida(b.fecha_compra)?.getTime() || 0;
                if (selectorOrden.value === "antiguas") return fechaA - fechaB;
                if (selectorOrden.value === "total-desc") return numeroSeguro(b.total_venta) - numeroSeguro(a.total_venta) || fechaB - fechaA;
                if (selectorOrden.value === "total-asc") return numeroSeguro(a.total_venta) - numeroSeguro(b.total_venta) || fechaB - fechaA;
                return fechaB - fechaA;
            });
        }

        function filasDetalle(venta) {
            const detalles = Array.isArray(venta.detalles) ? venta.detalles : [];
            if (!detalles.length) {
                return '<tr><td colspan="4">No hay productos asociados a esta venta.</td></tr>';
            }
            return detalles.map(detalle => `
                <tr>
                    <td>${escapeHtml(detalle.nombre_producto || "Producto")}</td>
                    <td>${Math.max(0, Math.trunc(numeroSeguro(detalle.cantidad_producto)))}</td>
                    <td>${escapeHtml(precioClp(detalle.precio_unitario))}</td>
                    <td>${escapeHtml(precioClp(detalle.subtotal_venta))}</td>
                </tr>
            `).join("");
        }

        function filasVenta(venta) {
            const id = Math.max(0, Math.trunc(numeroSeguro(venta.id)));
            const usuario = venta.id_usuario || {};
            const nombre = escapeHtml(nombreCliente(venta));
            const username = escapeHtml(usuario.username || "Sin usuario");
            const rut = escapeHtml(usuario.rut || "Sin RUT");
            const fecha = fechaFormateada(venta.fecha_compra);
            const retiro = venta.tipo_entrega === "retiro";
            const completado = venta.estado_entrega === "completado";
            const productos = Array.isArray(venta.detalles) ? venta.detalles : [];
            const unidades = productos.reduce((total, detalle) => total + numeroSeguro(detalle.cantidad_producto), 0);
            const direccion = venta.direccion_despacho
                ? escapeHtml(venta.direccion_despacho)
                : "Entrega coordinada en tienda.";
            const digitos = venta.ultimos_digitos ? `•••• ${escapeHtml(venta.ultimos_digitos)}` : "Transacción Webpay";
            const detalleId = `detalle-venta-${id}`;

            return `
                <tr class="sale-main-row">
                    <td><strong class="sale-number">#${id}</strong></td>
                    <td>
                        <div class="sale-customer">
                            <span>${escapeHtml(iniciales(venta))}</span>
                            <div><strong>${nombre}</strong><small>@${username} · ${rut}</small></div>
                        </div>
                    </td>
                    <td><div class="sale-date"><strong>${escapeHtml(fecha.fecha)}</strong><small>${escapeHtml(fecha.hora)}</small></div></td>
                    <td>
                        <div class="payment-cell">
                            <span class="payment-status"><i class="fa-solid fa-circle" aria-hidden="true"></i> ${escapeHtml(textoPago(venta.webpay_payment_status))}</span>
                            <small>${digitos}</small>
                        </div>
                    </td>
                    <td><span class="delivery-type ${retiro ? "" : "dispatch"}"><i class="fa-solid ${retiro ? "fa-store" : "fa-truck-fast"}" aria-hidden="true"></i> ${retiro ? "Retiro" : "Despacho"}</span></td>
                    <td><span class="delivery-state ${completado ? "completed" : ""}"><i class="fa-solid fa-circle" aria-hidden="true"></i> ${completado ? "Completado" : "Pendiente"}</span></td>
                    <td class="text-end"><strong class="sale-total-value">${escapeHtml(precioClp(venta.total_venta))}</strong></td>
                    <td>
                        <div class="sale-actions">
                            <button class="sale-action sale-detail-toggle" type="button" data-sale-detail="${detalleId}" aria-expanded="false" aria-controls="${detalleId}">
                                Detalle <i class="fa-solid fa-chevron-down" aria-hidden="true"></i>
                            </button>
                            <a class="sale-action receipt" href="${crearUrl(receiptUrlBase, id)}"><i class="fa-solid fa-file-invoice" aria-hidden="true"></i> Boleta</a>
                        </div>
                    </td>
                </tr>
                <tr class="sale-detail-row" id="${detalleId}">
                    <td colspan="8">
                        <div class="sale-detail-panel">
                            <div class="sale-products">
                                <strong>Productos de la venta · ${Math.trunc(unidades)} ${Math.trunc(unidades) === 1 ? "unidad" : "unidades"}</strong>
                                <div class="table-responsive">
                                    <table class="detail-products-table">
                                        <thead><tr><th>Producto</th><th>Cantidad</th><th>Precio unitario</th><th>Subtotal</th></tr></thead>
                                        <tbody>${filasDetalle(venta)}</tbody>
                                    </table>
                                </div>
                            </div>
                            <aside class="sale-delivery-summary">
                                <span>Información de entrega</span>
                                <h3>${retiro ? "Retiro en tienda" : "Despacho a domicilio"}</h3>
                                <p>${direccion}</p>
                            </aside>
                        </div>
                    </td>
                </tr>
            `;
        }

        function renderizar() {
            const visibles = ventasVisibles();
            contador.textContent = `${visibles.length} ${visibles.length === 1 ? "venta" : "ventas"}`;

            if (!visibles.length) {
                tabla.innerHTML = `
                    <tr class="empty-sales-history-row">
                        <td colspan="8">
                            <div class="empty-sales-history">
                                <i class="fa-solid fa-receipt" aria-hidden="true"></i>
                                <strong>No encontramos ventas</strong>
                                <span>Prueba cambiando o limpiando los filtros.</span>
                            </div>
                        </td>
                    </tr>
                `;
            } else {
                tabla.innerHTML = visibles.map(filasVenta).join("");
            }
            tabla.setAttribute("aria-busy", "false");
        }

        function limpiarFiltros() {
            buscador.value = "";
            fechaDesde.value = "";
            fechaHasta.value = "";
            filtroEntrega.value = "";
            filtroEstado.value = "";
            selectorOrden.value = "recientes";
            renderizar();
            buscador.focus();
        }

        async function cargarVentas() {
            try {
                const respuesta = await fetch(apiUrl, {
                    credentials: "same-origin",
                    headers: {Accept: "application/json"},
                });
                if (!respuesta.ok) throw new Error("No fue posible cargar el historial.");
                const datos = await respuesta.json();
                if (!Array.isArray(datos)) throw new Error("El servidor devolvió un formato inválido.");

                ventas = datos;
                actualizarMetricas();
                renderizar();
            } catch (error) {
                contador.textContent = "No disponible";
                tabla.innerHTML = `
                    <tr class="empty-sales-history-row">
                        <td colspan="8">
                            <div class="empty-sales-history">
                                <i class="fa-solid fa-triangle-exclamation" aria-hidden="true"></i>
                                <strong>No pudimos cargar las ventas</strong>
                                <span>${escapeHtml(error.message)}</span>
                            </div>
                        </td>
                    </tr>
                `;
                tabla.setAttribute("aria-busy", "false");
            }
        }

        [buscador, fechaDesde, fechaHasta, filtroEntrega, filtroEstado, selectorOrden].forEach(control => {
            control.addEventListener(control === buscador ? "input" : "change", renderizar);
        });
        botonLimpiar.addEventListener("click", limpiarFiltros);
        tabla.addEventListener("click", function (evento) {
            const boton = evento.target.closest("[data-sale-detail]");
            if (!boton) return;
            const detalle = document.getElementById(boton.dataset.saleDetail);
            if (!detalle) return;
            const abrir = !detalle.classList.contains("open");
            detalle.classList.toggle("open", abrir);
            boton.setAttribute("aria-expanded", String(abrir));
        });

        cargarVentas();
    });
})();
