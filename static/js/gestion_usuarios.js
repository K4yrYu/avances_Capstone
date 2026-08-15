(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", function () {
        const pagina = document.getElementById("contenido-usuarios");
        const tabla = document.getElementById("tabla-usuarios-admin");
        const buscador = document.getElementById("buscar-usuario");
        const filtroRol = document.getElementById("filtro-rol-usuario");
        const filtroEstado = document.getElementById("filtro-estado-usuario");
        const filtroVerificacion = document.getElementById("filtro-verificacion-usuario");
        const selectorOrden = document.getElementById("orden-usuarios");
        const botonLimpiar = document.getElementById("limpiar-filtros-usuarios");
        const contador = document.getElementById("contador-usuarios");
        const seguridad = window.FerremasSecurity;

        if (!pagina || !tabla || !seguridad || !window.bootstrap) return;

        const {escapeHtml} = seguridad;
        const apiUrl = pagina.dataset.apiUrl;
        const toggleUrlBase = pagina.dataset.toggleUrl;
        const editUrlBase = pagina.dataset.editUrl;
        const usuarioActualId = numeroSeguro(pagina.dataset.currentUserId);
        const modalElemento = document.getElementById("modalEstadoUsuario");
        const modal = new bootstrap.Modal(modalElemento);
        const toastElemento = document.getElementById("notificacionUsuario");
        const toast = new bootstrap.Toast(toastElemento, {delay: 3500});
        let usuarios = [];
        let usuarioPendiente = null;

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

        function obtenerCookie(nombre) {
            const prefijo = `${nombre}=`;
            const cookie = document.cookie.split(";").map(valor => valor.trim()).find(valor => valor.startsWith(prefijo));
            return cookie ? decodeURIComponent(cookie.slice(prefijo.length)) : "";
        }

        function estadoUsuario(usuario) {
            if (usuario.is_active) return "activo";
            return usuario.email_confirmado ? "suspendido" : "pendiente";
        }

        function nombreCompleto(usuario) {
            const nombre = `${usuario.first_name || ""} ${usuario.last_name || ""}`.trim();
            return nombre || usuario.username || "Usuario sin nombre";
        }

        function iniciales(usuario) {
            const partes = nombreCompleto(usuario).split(/\s+/).filter(Boolean);
            return partes.slice(0, 2).map(parte => parte.charAt(0)).join("").toUpperCase() || "U";
        }

        function actualizarMetricas() {
            document.getElementById("metrica-usuarios-total").textContent = usuarios.length;
            document.getElementById("metrica-usuarios-activos").textContent = usuarios.filter(usuario => estadoUsuario(usuario) === "activo").length;
            document.getElementById("metrica-usuarios-suspendidos").textContent = usuarios.filter(usuario => estadoUsuario(usuario) === "suspendido").length;
            document.getElementById("metrica-usuarios-pendientes").textContent = usuarios.filter(usuario => estadoUsuario(usuario) === "pendiente").length;
        }

        function usuariosVisibles() {
            const texto = normalizar(buscador.value.trim());
            const rol = filtroRol.value;
            const estado = filtroEstado.value;
            const verificacion = filtroVerificacion.value;

            const filtrados = usuarios.filter(usuario => {
                const coincideTexto = !texto || normalizar(
                    `${usuario.id} ${nombreCompleto(usuario)} ${usuario.username || ""} ${usuario.email || ""} ${usuario.rut || ""} ${usuario.telefono || ""}`
                ).includes(texto);
                const coincideRol = !rol
                    || (rol === "admin" && usuario.is_staff)
                    || (rol === "cliente" && !usuario.is_staff);
                const coincideEstado = !estado || estadoUsuario(usuario) === estado;
                const coincideVerificacion = !verificacion
                    || (verificacion === "verificado" && usuario.email_confirmado)
                    || (verificacion === "sin-verificar" && !usuario.email_confirmado);
                return coincideTexto && coincideRol && coincideEstado && coincideVerificacion;
            });

            return filtrados.sort((a, b) => {
                if (selectorOrden.value === "recientes") return numeroSeguro(b.id) - numeroSeguro(a.id);
                if (selectorOrden.value === "usuario-asc") {
                    return String(a.username || "").localeCompare(String(b.username || ""), "es", {sensitivity: "base"});
                }
                return nombreCompleto(a).localeCompare(nombreCompleto(b), "es", {sensitivity: "base"});
            });
        }

        function etiquetaEstado(usuario, esActual) {
            if (esActual) {
                return '<span class="account-status current"><i class="fa-solid fa-circle" aria-hidden="true"></i> Sesión actual</span>';
            }
            const estado = estadoUsuario(usuario);
            if (estado === "suspendido") {
                return '<span class="account-status suspended"><i class="fa-solid fa-circle" aria-hidden="true"></i> Suspendido</span>';
            }
            if (estado === "pendiente") {
                return '<span class="account-status pending"><i class="fa-solid fa-circle" aria-hidden="true"></i> Pendiente</span>';
            }
            return '<span class="account-status"><i class="fa-solid fa-circle" aria-hidden="true"></i> Activo</span>';
        }

        function filaUsuario(usuario) {
            const id = Math.max(0, Math.trunc(numeroSeguro(usuario.id)));
            const esActual = id === usuarioActualId;
            const activo = Boolean(usuario.is_active);
            const estado = estadoUsuario(usuario);
            const nombre = escapeHtml(nombreCompleto(usuario));
            const username = escapeHtml(usuario.username || "Sin usuario");
            const email = escapeHtml(usuario.email || "Sin correo");
            const telefono = escapeHtml(usuario.telefono || "Sin teléfono");
            const rut = escapeHtml(usuario.rut || "Sin RUT");
            const avatar = escapeHtml(iniciales(usuario));
            const editar = activo && !esActual
                ? `<a class="user-action edit" href="${crearUrl(editUrlBase, id)}"><i class="fa-solid fa-pen" aria-hidden="true"></i> Editar</a>`
                : "";
            let accionEstado = "";

            if (!esActual) {
                accionEstado = activo
                    ? `<button class="user-action suspend" type="button" data-toggle-user="${id}"><i class="fa-solid fa-user-lock" aria-hidden="true"></i> Suspender</button>`
                    : `<button class="user-action activate" type="button" data-toggle-user="${id}"><i class="fa-solid fa-user-check" aria-hidden="true"></i> ${estado === "pendiente" ? "Activar" : "Reactivar"}</button>`;
            }

            return `
                <tr>
                    <td>
                        <div class="user-cell">
                            <span class="user-avatar ${usuario.is_staff ? "admin" : ""}">${avatar}</span>
                            <div><strong>${nombre}</strong><small>@${username} · ID #${id}</small></div>
                        </div>
                    </td>
                    <td><span class="rut-value">${rut}</span></td>
                    <td><div class="contact-user-cell"><strong>${email}</strong><small>${telefono}</small></div></td>
                    <td><span class="role-badge ${usuario.is_staff ? "admin" : ""}"><i class="fa-solid ${usuario.is_staff ? "fa-shield-halved" : "fa-user"}" aria-hidden="true"></i> ${usuario.is_staff ? "Administrador" : "Cliente"}</span></td>
                    <td><span class="verification-badge ${usuario.email_confirmado ? "" : "pending"}"><i class="fa-solid fa-circle" aria-hidden="true"></i> ${usuario.email_confirmado ? "Verificado" : "Sin verificar"}</span></td>
                    <td>${etiquetaEstado(usuario, esActual)}</td>
                    <td>
                        <div class="user-actions">
                            ${editar}${accionEstado}
                            ${esActual ? '<span class="current-session-label">Sin acciones</span>' : ""}
                        </div>
                    </td>
                </tr>
            `;
        }

        function renderizar() {
            const visibles = usuariosVisibles();
            contador.textContent = `${visibles.length} ${visibles.length === 1 ? "resultado" : "resultados"}`;

            if (!visibles.length) {
                tabla.innerHTML = `
                    <tr class="empty-users-row">
                        <td colspan="7">
                            <div class="empty-users">
                                <i class="fa-solid fa-user-slash" aria-hidden="true"></i>
                                <strong>No encontramos usuarios</strong>
                                <span>Prueba cambiando o limpiando los filtros.</span>
                            </div>
                        </td>
                    </tr>
                `;
            } else {
                tabla.innerHTML = visibles.map(filaUsuario).join("");
            }
            tabla.setAttribute("aria-busy", "false");
        }

        function limpiarFiltros() {
            buscador.value = "";
            filtroRol.value = "";
            filtroEstado.value = "";
            filtroVerificacion.value = "";
            selectorOrden.value = "nombre-asc";
            renderizar();
            buscador.focus();
        }

        function prepararCambioEstado(usuario) {
            usuarioPendiente = usuario;
            const activar = !usuario.is_active;
            const pendiente = estadoUsuario(usuario) === "pendiente";
            const nombre = nombreCompleto(usuario);
            const icono = document.getElementById("iconoModalUsuario");
            const confirmar = document.getElementById("confirmarEstadoUsuario");
            const titulo = activar ? (pendiente ? "Activar cuenta" : "Reactivar cuenta") : "Suspender cuenta";

            document.getElementById("tituloModalUsuario").textContent = titulo;
            document.getElementById("mensajeModalUsuario").textContent = activar
                ? "La persona recuperará el acceso y podrá iniciar sesión en SFI."
                : "La persona perderá el acceso a SFI hasta que un administrador reactive su cuenta.";
            document.getElementById("avatarModalUsuario").textContent = iniciales(usuario);
            document.getElementById("nombreModalUsuario").textContent = nombre;
            document.getElementById("correoModalUsuario").textContent = usuario.email || "Sin correo";
            document.getElementById("ayudaModalUsuario").textContent = activar
                ? "Los datos y compras anteriores de la cuenta se conservarán."
                : "La suspensión no elimina sus datos ni su historial de compras.";
            confirmar.textContent = activar ? (pendiente ? "Sí, activar" : "Sí, reactivar") : "Sí, suspender";
            confirmar.classList.toggle("activate", activar);
            icono.classList.toggle("activate", activar);
            icono.innerHTML = `<i class="fa-solid ${activar ? "fa-user-check" : "fa-user-lock"}" aria-hidden="true"></i>`;
            modal.show();
        }

        function mostrarNotificacion(mensaje, esError) {
            document.getElementById("mensajeNotificacionUsuario").textContent = mensaje;
            document.getElementById("iconoNotificacionUsuario").className = esError
                ? "fa-solid fa-circle-exclamation"
                : "fa-solid fa-circle-check";
            toastElemento.classList.toggle("error", Boolean(esError));
            toast.show();
        }

        async function cambiarEstado() {
            if (!usuarioPendiente) return;

            const confirmar = document.getElementById("confirmarEstadoUsuario");
            const textoOriginal = confirmar.textContent;
            confirmar.disabled = true;
            confirmar.innerHTML = '<i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i> Guardando';

            try {
                const respuesta = await fetch(crearUrl(toggleUrlBase, usuarioPendiente.id), {
                    method: "PATCH",
                    credentials: "same-origin",
                    headers: {"X-CSRFToken": obtenerCookie("csrftoken"), Accept: "application/json"},
                });
                const datos = await respuesta.json().catch(() => ({}));
                if (!respuesta.ok) throw new Error(datos.error || "No fue posible actualizar la cuenta.");

                usuarioPendiente.is_active = Boolean(datos.is_active);
                actualizarMetricas();
                renderizar();
                modal.hide();
                mostrarNotificacion(datos.message || "Estado actualizado correctamente.", false);
                usuarioPendiente = null;
            } catch (error) {
                mostrarNotificacion(error.message || "Error al conectar con el servidor.", true);
            } finally {
                confirmar.disabled = false;
                confirmar.textContent = textoOriginal;
            }
        }

        async function cargarUsuarios() {
            try {
                const respuesta = await fetch(apiUrl, {
                    credentials: "same-origin",
                    headers: {Accept: "application/json"},
                });
                if (!respuesta.ok) throw new Error("No fue posible cargar los usuarios.");
                const datos = await respuesta.json();
                if (!Array.isArray(datos)) throw new Error("El servidor devolvió un formato inválido.");

                usuarios = datos;
                actualizarMetricas();
                renderizar();
            } catch (error) {
                contador.textContent = "No disponible";
                tabla.innerHTML = `
                    <tr class="empty-users-row">
                        <td colspan="7">
                            <div class="empty-users">
                                <i class="fa-solid fa-triangle-exclamation" aria-hidden="true"></i>
                                <strong>No pudimos cargar los usuarios</strong>
                                <span>${escapeHtml(error.message)}</span>
                            </div>
                        </td>
                    </tr>
                `;
                tabla.setAttribute("aria-busy", "false");
            }
        }

        [buscador, filtroRol, filtroEstado, filtroVerificacion, selectorOrden].forEach(control => {
            control.addEventListener(control === buscador ? "input" : "change", renderizar);
        });
        botonLimpiar.addEventListener("click", limpiarFiltros);
        tabla.addEventListener("click", function (evento) {
            const boton = evento.target.closest("[data-toggle-user]");
            if (!boton) return;
            const id = numeroSeguro(boton.dataset.toggleUser);
            const usuario = usuarios.find(item => numeroSeguro(item.id) === id);
            if (usuario) prepararCambioEstado(usuario);
        });
        document.getElementById("confirmarEstadoUsuario").addEventListener("click", cambiarEstado);
        modalElemento.addEventListener("hidden.bs.modal", function () {
            usuarioPendiente = null;
        });

        cargarUsuarios();
    });
})();
