(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", () => {
    const panel = document.getElementById("panel-repartidor");
    const list = document.getElementById("lista-despachos-repartidor");
    const search = document.getElementById("buscar-despacho-repartidor");
    const dateFilter = document.getElementById("filtro-fecha-repartidor");
    const statusFilter = document.getElementById("filtro-estado-repartidor");
    const toast = document.getElementById("mensaje-repartidor");
    const security = window.FerremasSecurity;
    if (!panel || !list || !security) return;

    const {escapeHtml} = security;
    let dispatches = [];

    const cookie = (name) => {
      const prefix = `${name}=`;
      const value = document.cookie.split(";").map(item => item.trim()).find(item => item.startsWith(prefix));
      return value ? decodeURIComponent(value.slice(prefix.length)) : "";
    };
    const normalize = (value) => String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
    const customerName = (item) => {
      const user = item.id_usuario || {};
      return `${user.first_name || ""} ${user.last_name || ""}`.trim() || user.username || "Cliente";
    };
    const formattedDate = (value) => new Intl.DateTimeFormat("es-CL", {weekday: "long", day: "2-digit", month: "long", year: "numeric"}).format(new Date(`${value}T12:00:00`));
    const statusLabel = (item) => ({programado: "Programado", preparacion: "En preparación", en_ruta: "En ruta", entregado: "Entregado"})[item.estado] || item.estado;
    const statusUrl = (id) => panel.dataset.statusUrl.replace(/\/0\/estado\/$/, `/${id}/estado/`);
    const isCompleted = (item) => item.estado === "entregado";
    const isOverdue = (item) => !isCompleted(item) && item.fecha_programada < panel.dataset.today;

    function notify(message, error = false) {
      toast.textContent = message;
      toast.classList.toggle("error", error);
      toast.hidden = false;
      window.setTimeout(() => { toast.hidden = true; }, 3500);
    }

    function updateSummary() {
      const today = panel.dataset.today;
      document.getElementById("resumen-atrasados").textContent = dispatches.filter(isOverdue).length;
      document.getElementById("resumen-hoy").textContent = dispatches.filter(item => item.fecha_programada === today && !isCompleted(item)).length;
      document.getElementById("resumen-ruta").textContent = dispatches.filter(item => item.estado === "en_ruta").length;
      document.getElementById("resumen-entregados").textContent = dispatches.filter(isCompleted).length;
    }

    function productList(item) {
      const products = Array.isArray(item.detalles) ? item.detalles : [];
      return products.length
        ? products.map(product => `<li><span>${escapeHtml(product.nombre_producto || "Producto")}</span><b>× ${Number(product.cantidad_producto) || 0}</b></li>`).join("")
        : "<li><span>Sin productos detallados</span></li>";
    }

    function card(item) {
      const phone = String(item.comprador_telefono || "");
      const safePhone = phone.replace(/[^+\d]/g, "");
      const email = String(item.comprador_email || "");
      const nextAction = ["programado", "preparacion"].includes(item.estado)
        ? `<button data-status-id="${Number(item.id)}" data-next-status="en_ruta"><i class="fa-solid fa-route"></i> Iniciar ruta</button>`
        : item.estado === "en_ruta"
          ? `<button class="complete" data-status-id="${Number(item.id)}" data-next-status="entregado"><i class="fa-solid fa-check"></i> Marcar entregado</button>`
          : '<span class="delivery-complete"><i class="fa-solid fa-circle-check"></i> Entrega completada</span>';
      const overdueFlag = isOverdue(item) ? '<span class="overdue-flag"><i class="fa-solid fa-triangle-exclamation"></i> Atrasado</span>' : "";
      return `<article class="driver-card${isOverdue(item) ? " is-overdue" : ""}">
        <header><div><span>Venta #${Number(item.venta_id)} · Despacho ${Number(item.numero)} ${overdueFlag}</span><h3>${escapeHtml(customerName(item))}</h3></div><b class="driver-status status-${escapeHtml(item.estado)}">${escapeHtml(statusLabel(item))}</b></header>
        <div class="driver-address"><i class="fa-solid fa-location-dot"></i><div><small>Dirección de entrega</small><strong>${escapeHtml(item.direccion_despacho || "Dirección no registrada")}</strong></div></div>
        <div class="driver-contact"><a class="${safePhone ? "" : "disabled"}" href="${safePhone ? `tel:${safePhone}` : "#"}"><i class="fa-solid fa-phone"></i><span><small>Teléfono</small><b>${escapeHtml(phone || "No registrado")}</b></span></a><a class="${email ? "" : "disabled"}" href="${email ? `mailto:${encodeURIComponent(email)}` : "#"}"><i class="fa-solid fa-envelope"></i><span><small>Correo</small><b>${escapeHtml(email || "No registrado")}</b></span></a></div>
        <details><summary><span><i class="fa-solid fa-box-open"></i> Ver productos del despacho</span><i class="fa-solid fa-chevron-down"></i></summary><ul>${productList(item)}</ul></details>
        <footer>${nextAction}</footer>
      </article>`;
    }

    function visibleDispatches() {
      const query = normalize(search.value.trim());
      return dispatches.filter(item => {
        const content = `${item.venta_id} ${customerName(item)} ${item.direccion_despacho} ${item.comprador_telefono} ${item.comprador_email}`;
        return (!query || normalize(content).includes(query))
          && (!dateFilter.value || item.fecha_programada === dateFilter.value)
          && (!statusFilter.value || item.estado === statusFilter.value);
      }).sort((a, b) => a.fecha_programada.localeCompare(b.fecha_programada) || Number(a.numero) - Number(b.numero));
    }

    function groupedCards(items, urgent = false) {
      let previousDate = "";
      return items.map(item => {
        const count = items.filter(other => other.fecha_programada === item.fecha_programada).length;
        const heading = item.fecha_programada !== previousDate
          ? `<section class="driver-day${urgent ? " urgent" : ""}"><i class="fa-solid fa-calendar-day"></i><div><small>Jornada de entrega${urgent ? ' <span class="day-urgent"><i class="fa-solid fa-triangle-exclamation"></i> Requiere atención</span>' : ""}</small><h2>${escapeHtml(formattedDate(item.fecha_programada))}</h2></div><b>${count} despacho(s)</b></section>`
          : "";
        previousDate = item.fecha_programada;
        return heading + card(item);
      }).join("");
    }

    function completedRows(items) {
      if (!items.length) return "";
      const rows = items.map(item => `<li><span><b>Venta #${Number(item.venta_id)} · Despacho ${Number(item.numero)}</b><small>${escapeHtml(customerName(item))} · ${escapeHtml(formattedDate(item.fecha_programada))}</small></span><span>${escapeHtml(item.direccion_despacho || "Dirección no registrada")}</span></li>`).join("");
      return `<details class="completed-dispatches"><summary><span><i class="fa-solid fa-circle-check"></i> Entregas completadas</span><b>${items.length}</b><i class="fa-solid fa-chevron-down"></i></summary><p>Estas entregas ya fueron cerradas. Ábrelas solo si necesitas revisar su información.</p><ul>${rows}</ul></details>`;
    }

    function render() {
      const visible = visibleDispatches();
      if (!visible.length) {
        list.innerHTML = '<div class="driver-empty"><i class="fa-solid fa-truck"></i><strong>No hay despachos para mostrar</strong><span>Revisa los filtros o vuelve más tarde.</span></div>';
        return;
      }
      const overdue = visible.filter(isOverdue);
      const active = visible.filter(item => !isCompleted(item) && !isOverdue(item));
      const completed = visible.filter(isCompleted);
      const urgentTitle = overdue.length
        ? '<section class="priority-intro"><i class="fa-solid fa-triangle-exclamation"></i><div><strong>Despachos atrasados</strong><span>Resuélvelos primero: su fecha programada ya pasó.</span></div></section>'
        : "";
      list.innerHTML = urgentTitle + groupedCards(overdue, true) + groupedCards(active) + completedRows(completed);
    }

    async function updateStatus(button) {
      button.disabled = true;
      try {
        const response = await fetch(statusUrl(button.dataset.statusId), {
          method: "PATCH",
          credentials: "same-origin",
          headers: {"Content-Type": "application/json", Accept: "application/json", "X-CSRFToken": cookie("csrftoken")},
          body: JSON.stringify({estado: button.dataset.nextStatus}),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || "No fue posible actualizar el despacho.");
        const item = dispatches.find(dispatch => Number(dispatch.id) === Number(button.dataset.statusId));
        if (item) item.estado = data.estado;
        updateSummary();
        render();
        notify(data.mensaje || "Estado actualizado.");
      } catch (error) {
        button.disabled = false;
        notify(error.message, true);
      }
    }

    async function load() {
      try {
        const response = await fetch(panel.dataset.apiUrl, {credentials: "same-origin", headers: {Accept: "application/json"}});
        const data = await response.json().catch(() => []);
        if (!response.ok || !Array.isArray(data)) throw new Error("No fue posible cargar los despachos.");
        dispatches = data;
        [...new Set(dispatches.map(item => item.fecha_programada))].sort().forEach(date => {
          const option = document.createElement("option");
          option.value = date;
          option.textContent = formattedDate(date);
          dateFilter.appendChild(option);
        });
        updateSummary();
        render();
      } catch (error) {
        list.innerHTML = `<div class="driver-empty error"><i class="fa-solid fa-triangle-exclamation"></i><strong>No pudimos cargar la ruta</strong><span>${escapeHtml(error.message)}</span></div>`;
      }
    }

    search.addEventListener("input", render);
    dateFilter.addEventListener("change", render);
    statusFilter.addEventListener("change", render);
    list.addEventListener("click", event => {
      const button = event.target.closest("[data-status-id]");
      if (button) updateStatus(button);
    });
    load();
  });
}());
