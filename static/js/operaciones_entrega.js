(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", function () {
        const pagina = document.getElementById("contenido-operaciones");
        const tabla = document.getElementById("tabla-operaciones");
        const buscador = document.getElementById("buscar-operacion");
        const filtroEstado = document.getElementById("filtro-estado-operacion");
        const fechaDesde = document.getElementById("fecha-desde-operacion");
        const fechaHasta = document.getElementById("fecha-hasta-operacion");
        const selectorOrden = document.getElementById("orden-operaciones");
        const botonLimpiar = document.getElementById("limpiar-filtros-operaciones");
        const contador = document.getElementById("contador-operaciones");
        const seguridad = window.FerremasSecurity;

        if (!pagina || !tabla || !seguridad || !window.bootstrap) return;

        const {escapeHtml} = seguridad;
        const operacion = pagina.dataset.operation;
        const esRetiro = operacion === "retiro";
        const apiUrl = pagina.dataset.apiUrl;
        const confirmUrlBase = pagina.dataset.confirmUrl;
        const receiptUrlBase = pagina.dataset.receiptUrl;
        const modalElemento = document.getElementById("modalConfirmarOperacion");
        const modal = new bootstrap.Modal(modalElemento);
        const toastElemento = document.getElementById("notificacionOperacion");
        const toast = new bootstrap.Toast(toastElemento, {delay: 3500});
        let operaciones = [];
        let operacionPendiente = null;

        function numeroSeguro(valor) {
            const numero = Number(valor);
            return Number.isFinite(numero) ? numero : 0;
        }

        function normalizar(valor) {
            return String(valor || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("es");
        }

        function crearUrl(base, id) {
            return base.replace(/\/0\/$/, `/${id}/`);
        }

        function obtenerCookie(nombre) {
            const prefijo = `${nombre}=`;
            const cookie = document.cookie.split(";").map(valor => valor.trim()).find(valor => valor.startsWith(prefijo));
            return cookie ? decodeURIComponent(cookie.slice(prefijo.length)) : "";
        }

        function precioClp(valor) {
            return new Intl.NumberFormat("es-CL", {style: "currency", currency: "CLP", maximumFractionDigits: 0}).format(numeroSeguro(valor));
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
            return `${usuario.first_name || ""} ${usuario.last_name || ""}`.trim() || usuario.username || "Cliente sin nombre";
        }

        function iniciales(venta) {
            return nombreCliente(venta).split(/\s+/).filter(Boolean).slice(0, 2).map(parte => parte.charAt(0)).join("").toUpperCase() || "C";
        }

        function cantidadProductos(venta) {
            const detalles = Array.isArray(venta.detalles) ? venta.detalles : [];
            return detalles.reduce((total, detalle) => total + numeroSeguro(detalle.cantidad_producto), 0);
        }

        function actualizarMetricas() {
            const pendientes = operaciones.filter(item => item.estado_entrega === "pendiente");
            document.getElementById("metrica-operaciones-total").textContent = operaciones.length;
            document.getElementById("metrica-operaciones-pendientes").textContent = pendientes.length;
            document.getElementById("metrica-operaciones-completadas").textContent = operaciones.filter(item => item.estado_entrega === "completado").length;
            document.getElementById("metrica-operaciones-valor").textContent = precioClp(
                pendientes.reduce((total, item) => total + numeroSeguro(item.total_venta), 0)
            );
        }

        function operacionesVisibles() {
            const texto = normalizar(buscador.value.trim());
            const estado = filtroEstado.value;
            const desde = fechaDesde.value;
            const hasta = fechaHasta.value;
            const filtradas = operaciones.filter(item => {
                const usuario = item.id_usuario || {};
                const textoItem = `${item.id} ${nombreCliente(item)} ${usuario.username || ""} ${usuario.rut || ""} ${item.direccion_despacho || ""}`;
                const fecha = fechaIso(item);
                return (!texto || normalizar(textoItem).includes(texto))
                    && (!estado || item.estado_entrega === estado)
                    && (!desde || fecha >= desde)
                    && (!hasta || fecha <= hasta);
            });
            return filtradas.sort((a, b) => {
                const fechaA = fechaValida(a.fecha_compra)?.getTime() || 0;
                const fechaB = fechaValida(b.fecha_compra)?.getTime() || 0;
                if (selectorOrden.value === "antiguas") return fechaA - fechaB;
                if (selectorOrden.value === "total-desc") return numeroSeguro(b.total_venta) - numeroSeguro(a.total_venta) || fechaB - fechaA;
                return fechaB - fechaA;
            });
        }

        function filaOperacion(item) {
            const id = Math.max(0, Math.trunc(numeroSeguro(item.id)));
            const usuario = item.id_usuario || {};
            const nombre = escapeHtml(nombreCliente(item));
            const username = escapeHtml(usuario.username || "Sin usuario");
            const fecha = fechaFormateada(item.fecha_compra);
            const completado = item.estado_entrega === "completado";
            const unidades = Math.trunc(cantidadProductos(item));
            const direccion = escapeHtml(item.direccion_despacho || "Dirección no especificada");
            const accion = completado
                ? '<span class="delivered-label"><i class="fa-solid fa-circle-check" aria-hidden="true"></i> Entregado</span>'
                : `<button class="operation-action confirm" type="button" data-confirm-operation="${id}"><i class="fa-solid ${esRetiro ? "fa-id-card" : "fa-circle-check"}" aria-hidden="true"></i> ${esRetiro ? "Validar retiro" : "Confirmar entrega"}</button>`;
            const columnaDireccion = esRetiro ? "" : `<td><div class="operation-address"><strong title="${direccion}">${direccion}</strong><small>Destino del pedido</small></div></td>`;

            return `
                <tr>
                    <td><strong class="operation-number">#${id}</strong></td>
                    <td><div class="operation-customer"><span>${escapeHtml(iniciales(item))}</span><div><strong>${nombre}</strong><small>@${username}</small></div></div></td>
                    ${columnaDireccion}
                    <td><div class="operation-date"><strong>${escapeHtml(fecha.fecha)}</strong><small>${escapeHtml(fecha.hora)}</small></div></td>
                    <td><span class="products-count"><i class="fa-solid fa-box" aria-hidden="true"></i> ${unidades} ${unidades === 1 ? "unidad" : "unidades"}</span></td>
                    <td><strong class="operation-total">${escapeHtml(precioClp(item.total_venta))}</strong></td>
                    <td><span class="operation-status ${completado ? "completed" : ""}"><i class="fa-solid fa-circle" aria-hidden="true"></i> ${completado ? "Completado" : (esRetiro ? "Por retirar" : "Por despachar")}</span></td>
                    <td><div class="operation-actions">${accion}<a class="operation-action receipt" href="${crearUrl(receiptUrlBase, id)}"><i class="fa-solid fa-file-invoice" aria-hidden="true"></i> Boleta</a></div></td>
                </tr>
            `;
        }

        function renderizar() {
            const visibles = operacionesVisibles();
            const etiqueta = esRetiro ? "retiro" : "despacho";
            contador.textContent = `${visibles.length} ${visibles.length === 1 ? etiqueta : `${etiqueta}s`}`;
            const columnas = esRetiro ? 7 : 8;
            if (!visibles.length) {
                tabla.innerHTML = `<tr class="empty-operations-row"><td colspan="${columnas}"><div class="empty-operations"><i class="fa-solid ${esRetiro ? "fa-store" : "fa-truck-fast"}" aria-hidden="true"></i><strong>No encontramos ${esRetiro ? "retiros" : "despachos"}</strong><span>Prueba cambiando o limpiando los filtros.</span></div></td></tr>`;
            } else {
                tabla.innerHTML = visibles.map(filaOperacion).join("");
            }
            tabla.setAttribute("aria-busy", "false");
        }

        function limpiarFiltros() {
            buscador.value = "";
            filtroEstado.value = "";
            fechaDesde.value = "";
            fechaHasta.value = "";
            selectorOrden.value = "recientes";
            renderizar();
            buscador.focus();
        }

        function prepararConfirmacion(item) {
            operacionPendiente = item;
            document.getElementById("avatarModalOperacion").textContent = iniciales(item);
            document.getElementById("nombreModalOperacion").textContent = nombreCliente(item);
            document.getElementById("ventaModalOperacion").textContent = `Venta #${item.id} · ${precioClp(item.total_venta)}`;
            const direccion = document.getElementById("direccionModalOperacion");
            if (direccion) direccion.textContent = item.direccion_despacho || "Dirección no especificada";
            const rut = document.getElementById("rut-confirmacion");
            if (rut) rut.value = "";
            const error = document.getElementById("errorModalOperacion");
            error.textContent = "";
            error.classList.remove("visible");
            modal.show();
        }

        function mostrarNotificacion(mensaje, esError) {
            document.getElementById("mensajeNotificacionOperacion").textContent = mensaje;
            document.getElementById("iconoNotificacionOperacion").className = esError ? "fa-solid fa-circle-exclamation" : "fa-solid fa-circle-check";
            toastElemento.classList.toggle("error", Boolean(esError));
            toast.show();
        }

        async function confirmarOperacion() {
            if (!operacionPendiente) return;
            const errorModal = document.getElementById("errorModalOperacion");
            const rutInput = document.getElementById("rut-confirmacion");
            const rut = rutInput ? rutInput.value.trim() : "";
            if (esRetiro && !rut) {
                errorModal.textContent = "Ingresa el RUT del cliente para continuar.";
                errorModal.classList.add("visible");
                rutInput.focus();
                return;
            }

            const confirmar = document.getElementById("confirmarOperacion");
            const textoOriginal = confirmar.textContent;
            confirmar.disabled = true;
            confirmar.innerHTML = '<i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i> Guardando';
            errorModal.classList.remove("visible");

            try {
                const respuesta = await fetch(crearUrl(confirmUrlBase, operacionPendiente.id), {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {"Content-Type": "application/json", "X-CSRFToken": obtenerCookie("csrftoken"), Accept: "application/json"},
                    body: JSON.stringify(esRetiro ? {rut} : {}),
                });
                const datos = await respuesta.json().catch(() => ({}));
                if (!respuesta.ok) throw new Error(datos.detail || "No fue posible confirmar la entrega.");

                operacionPendiente.estado_entrega = "completado";
                actualizarMetricas();
                renderizar();
                modal.hide();
                mostrarNotificacion(datos.mensaje || "Entrega confirmada correctamente.", false);
                operacionPendiente = null;
            } catch (error) {
                errorModal.textContent = error.message || "Error al conectar con el servidor.";
                errorModal.classList.add("visible");
                mostrarNotificacion(errorModal.textContent, true);
            } finally {
                confirmar.disabled = false;
                confirmar.textContent = textoOriginal;
            }
        }

        async function cargarOperaciones() {
            try {
                const respuesta = await fetch(apiUrl, {credentials: "same-origin", headers: {Accept: "application/json"}});
                if (!respuesta.ok) throw new Error(`No fue posible cargar los ${esRetiro ? "retiros" : "despachos"}.`);
                const datos = await respuesta.json();
                if (!Array.isArray(datos)) throw new Error("El servidor devolvió un formato inválido.");
                operaciones = datos.filter(item => numeroSeguro(item.total_venta) > 0);
                actualizarMetricas();
                renderizar();
            } catch (error) {
                contador.textContent = "No disponible";
                tabla.innerHTML = `<tr class="empty-operations-row"><td colspan="${esRetiro ? 7 : 8}"><div class="empty-operations"><i class="fa-solid fa-triangle-exclamation" aria-hidden="true"></i><strong>No pudimos cargar los datos</strong><span>${escapeHtml(error.message)}</span></div></td></tr>`;
                tabla.setAttribute("aria-busy", "false");
            }
        }

        [buscador, filtroEstado, fechaDesde, fechaHasta, selectorOrden].forEach(control => control.addEventListener(control === buscador ? "input" : "change", renderizar));
        botonLimpiar.addEventListener("click", limpiarFiltros);
        tabla.addEventListener("click", function (evento) {
            const boton = evento.target.closest("[data-confirm-operation]");
            if (!boton) return;
            const id = numeroSeguro(boton.dataset.confirmOperation);
            const item = operaciones.find(venta => numeroSeguro(venta.id) === id);
            if (item) prepararConfirmacion(item);
        });
        document.getElementById("confirmarOperacion").addEventListener("click", confirmarOperacion);
        modalElemento.addEventListener("shown.bs.modal", function () {
            const rut = document.getElementById("rut-confirmacion");
            if (rut) rut.focus();
        });
        modalElemento.addEventListener("hidden.bs.modal", function () { operacionPendiente = null; });

        cargarOperaciones();
    });
})();
