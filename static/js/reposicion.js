(() => {
  "use strict";

  const detail = document.getElementById("rotation-detail");
  const parseData = (id) => {
    const node = document.getElementById(id);
    try { return node ? JSON.parse(node.textContent) : []; } catch { return []; }
  };
  const showRotationDetail = (item) => {
    if (!detail || !item) return;
    detail.innerHTML = `<div><span class="rotation-level ${item.rotacion.toLowerCase().replace(" ", "-")}">${item.rotacion}</span><h3>${item.nombre}</h3><small>${item.sku}</small></div><dl><div><dt>Vendidas</dt><dd>${item.vendidas}</dd></div><div><dt>Stock actual</dt><dd>${item.stock}</dd></div><div><dt>Stock mínimo</dt><dd>${item.stock_minimo}</dd></div><div><dt>Pendientes</dt><dd>${item.pendientes}</dd></div><div class="suggestion"><dt>Compra sugerida</dt><dd>${item.sugerida} unidades</dd></div></dl>`;
  };
  const buildChart = (canvasId, items, color, highlightZero = false) => {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !window.Chart) return;
    new Chart(canvas, {
      type: "bar",
      data: { labels: items.map((item) => item.nombre), datasets: [{
        data: items.map((item) => item.vendidas),
        backgroundColor: highlightZero
          ? items.map((item) => Number(item.vendidas) === 0 ? "#d64550" : color)
          : color,
        borderRadius: 7,
        minBarLength: highlightZero ? 6 : 0,
      }] },
      options: {
        responsive: true, maintainAspectRatio: false, indexAxis: "y",
        plugins: { legend: { display: false }, tooltip: { callbacks: {
          label: (context) => Number(context.raw) === 0 ? " 0 unidades (sin ventas)" : ` ${context.raw} unidad(es) vendida(s)`,
          afterLabel: () => "Haz clic para ver detalles",
        } } },
        scales: { x: { beginAtZero: true, ticks: { precision: 0 } }, y: { ticks: { autoSkip: false } } },
        onClick: (_event, elements) => { if (elements.length) showRotationDetail(items[elements[0].index]); },
      },
    });
  };
  buildChart("chart-mas-vendidos", parseData("datos-mas-vendidos"), "#164d73");
  buildChart("chart-baja-rotacion", parseData("datos-baja-rotacion"), "#e6aa00", true);

  document.querySelectorAll("[data-order-form]").forEach((form) => {
    const button = form.querySelector(".send-order-button");
    const update = () => {
      const selected = form.querySelectorAll('input[name="productos"]:checked').length;
      button.disabled = selected === 0;
      button.querySelector("span").textContent = !selected
        ? "Selecciona productos"
        : `Crear y enviar solicitud (${selected})`;
    };
    form.querySelectorAll('input[name="productos"]').forEach((checkbox) => {
      checkbox.addEventListener("change", update);
    });
    form.addEventListener("submit", (event) => {
      if (!form.querySelector('input[name="productos"]:checked')) {
        event.preventDefault();
        return;
      }
      button.disabled = true;
      button.querySelector("span").textContent = "Enviando correo…";
    });
    update();
  });

  document.querySelectorAll("[data-reception-form]").forEach((form) => {
    form.querySelectorAll("[data-reception-item]").forEach((item) => {
      const toggle = item.querySelector("[data-incident-toggle]");
      const fields = item.querySelector("[data-incident-fields]");
      const resultSelect = item.querySelector("[data-result-select]");
      const resultInput = item.querySelector("[data-result-input]");
      const quantity = item.querySelector("[data-received-quantity]");
      const reason = item.querySelector("[data-incident-reason]");
      const reasonLabel = item.querySelector("[data-reason-label]");
      const pending = Number(item.dataset.pending);
      const lotsContainer = item.querySelector("[data-lots-container]");
      const lotRows = item.querySelector("[data-lot-rows]");
      const addLot = item.querySelector("[data-add-lot]");

      const syncFirstLotQuantity = () => {
        const rows = lotRows?.querySelectorAll("[data-lot-row]") || [];
        if (rows.length === 1) rows[0].querySelector("[data-lot-quantity]").value = quantity.value;
      };
      addLot?.addEventListener("click", () => {
        const source = lotRows.querySelector("[data-lot-row]");
        const clone = source.cloneNode(true);
        clone.querySelectorAll("input").forEach((input) => {
          if (input.type === "date" && input.name.includes("ingreso")) return;
          input.value = input.type === "number" ? "1" : "";
        });
        lotRows.appendChild(clone);
      });
      lotRows?.addEventListener("click", (event) => {
        const remove = event.target.closest("[data-remove-lot]");
        if (!remove) return;
        const rows = lotRows.querySelectorAll("[data-lot-row]");
        if (rows.length > 1) remove.closest("[data-lot-row]").remove();
      });

      const updateResult = () => {
        const hasIncident = toggle.checked;
        item.classList.toggle("has-incident", hasIncident);
        fields.hidden = !hasIncident;
        const reasonIsRequired = hasIncident && resultSelect.value !== "no_llego";
        reason.required = reasonIsRequired;
        reasonLabel.textContent = reasonIsRequired ? "Explicación obligatoria" : "Explicación opcional";
        reason.placeholder = reasonIsRequired
          ? "Explica qué ocurrió con este producto"
          : "Puedes agregar un detalle si lo necesitas";
        resultInput.value = hasIncident ? resultSelect.value : "completo";
        if (!hasIncident) {
          quantity.value = pending;
          quantity.readOnly = true;
          reason.value = "";
        } else if (resultSelect.value === "parcial") {
          quantity.readOnly = false;
          if (Number(quantity.value) <= 0 || Number(quantity.value) >= pending) {
            quantity.value = Math.max(pending - 1, 1);
          }
        } else {
          quantity.value = 0;
          quantity.readOnly = true;
        }
        if (lotsContainer) lotsContainer.hidden = Number(quantity.value) <= 0;
        lotsContainer?.querySelectorAll("input").forEach((input) => { input.disabled = lotsContainer.hidden; });
        syncFirstLotQuantity();
      };

      toggle.addEventListener("change", updateResult);
      resultSelect.addEventListener("change", updateResult);
      quantity.addEventListener("input", syncFirstLotQuantity);
      updateResult();
    });

    form.addEventListener("submit", (event) => {
      let valid = true;
      form.querySelectorAll("[data-reception-item].has-incident").forEach((item) => {
        const reason = item.querySelector("[data-incident-reason]");
        const result = item.querySelector("[data-result-select]").value;
        const quantity = Number(item.querySelector("[data-received-quantity]").value);
        const pending = Number(item.dataset.pending);
        const reasonIsRequired = result !== "no_llego";
        reason.setCustomValidity(reasonIsRequired && reason.value.trim().length < 10 ? "Explica el problema con al menos 10 caracteres." : "");
        if (result === "parcial" && !(quantity > 0 && quantity < pending)) {
          item.querySelector("[data-received-quantity]").setCustomValidity("Indica una cantidad mayor que cero y menor que la pendiente.");
        } else {
          item.querySelector("[data-received-quantity]").setCustomValidity("");
        }
        if (!reason.checkValidity() || !item.querySelector("[data-received-quantity]").checkValidity()) valid = false;
      });
      if (!valid) {
        event.preventDefault();
        form.querySelector(":invalid")?.reportValidity();
        return;
      }
      const button = form.querySelector(".confirm-reception-button");
      button.disabled = true;
      button.setAttribute("aria-busy", "true");
      button.innerHTML = '<i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i> Registrando recepción…';
    });
  });
})();
