(() => {
  "use strict";

  document.addEventListener("DOMContentLoaded", () => {
    const root = document.getElementById("calculadora");
    const form = document.getElementById("paint-calculator-form");
    const results = document.getElementById("calculator-results");
    const list = document.getElementById("paint-recommendations");
    const summary = document.getElementById("results-summary");
    const count = document.getElementById("results-count");
    const errorBox = document.getElementById("calculator-error");
    const submit = document.getElementById("calculate-paint");
    const security = window.FerremasSecurity;
    if (!root || !form || !results || !list || !security) return;

    const {escapeHtml, safeUrl} = security;
    const fallbackImage = safeUrl(root.dataset.placeholderUrl);
    const addCartUrl = root.dataset.addCartUrl || "";
    const cartUrl = root.dataset.cartUrl || "/carrito/";
    const loginUrl = root.dataset.loginUrl || "/usuarios/iniciosesion/";
    const authenticated = root.dataset.authenticated === "true";

    function getCookie(name) {
      const prefix = `${name}=`;
      const cookie = document.cookie.split(";").map(value => value.trim()).find(value => value.startsWith(prefix));
      return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : "";
    }

    function firstError(value) {
      if (Array.isArray(value)) return value.map(firstError).filter(Boolean).join(" ");
      if (value && typeof value === "object") return Object.values(value).map(firstError).filter(Boolean).join(" ");
      return typeof value === "string" ? value : "";
    }

    function number(value) {
      const parsed = Number(value);
      return Number.isFinite(parsed) ? parsed : 0;
    }

    function formatNumber(value, maximumFractionDigits = 2) {
      return new Intl.NumberFormat("es-CL", {maximumFractionDigits, minimumFractionDigits: 0}).format(number(value));
    }

    function formatClp(value) {
      return new Intl.NumberFormat("es-CL", {style: "currency", currency: "CLP", maximumFractionDigits: 0}).format(number(value));
    }

    function safeColor(value) {
      const color = String(value || "").trim();
      return /^#[0-9a-f]{6}$/i.test(color) ? color : "";
    }

    function resultCard(item) {
      const id = Math.max(0, Math.trunc(number(item.producto_id)));
      const name = escapeHtml(item.nombre || "Pintura");
      const image = safeUrl(item.imagen) || fallbackImage;
      const color = escapeHtml(item.color || "Sin color indicado");
      const colorHex = safeColor(item.color_hex);
      const enough = Boolean(item.stock_suficiente);
      const stockText = enough
        ? `${item.stock_disponible} disponibles`
        : `Faltan ${item.envases_faltantes} envases`;
      const quantity = Math.max(1, Math.trunc(number(item.cantidad_envases)));
      const cartButton = enough
        ? `<button class="add-calculation-button" type="button" data-add-calculation="${id}"><i class="fa-solid fa-cart-plus"></i> Agregar ${quantity} al carrito</button>`
        : `<button class="add-calculation-button" type="button" disabled><i class="fa-solid fa-triangle-exclamation"></i> Stock insuficiente</button>`;

      return `
        <article class="paint-result-card">
          <div class="paint-result-image">
            <span class="paint-stock ${enough ? "" : "missing"}">${escapeHtml(stockText)}</span>
            <img src="${image}" alt="${name}" loading="lazy">
          </div>
          <div class="paint-result-body">
            <p class="paint-result-category">Pintura verificada</p>
            <h3>${name}</h3>
            <div class="paint-meta">
              <span>${escapeHtml(item.marca || "SFI")}</span>
              <span>${escapeHtml(item.presentacion || "Envase")}</span>
              <span>${colorHex ? `<i class="paint-swatch" style="--paint-color:${colorHex}"></i>` : ""}${color}</span>
              <span><i class="fa-solid fa-house-circle-check"></i>${escapeHtml(item.ambiente_uso_display || "Uso no indicado")}</span>
              <span><i class="fa-solid fa-brush"></i>${escapeHtml(item.tipo_pintura_display || "Pintura")}</span>
              <span><i class="fa-solid fa-circle-half-stroke"></i>${escapeHtml(item.terminacion_display || "Terminacion no indicada")}</span>
            </div>
            <div class="paint-calculation">
              <div><small>Necesitas</small><strong>${formatNumber(item.litros_necesarios, 0)} L</strong></div>
              <div><small>Debes comprar</small><strong>${item.cantidad_envases} envase${item.cantidad_envases === 1 ? "" : "s"}</strong></div>
              <div><small>Sobrante estimado</small><strong>${formatNumber(item.sobrante_estimado, 0)} L</strong></div>
              <div><small>Rendimiento</small><strong>${formatNumber(item.rendimiento_m2_litro, 3)} m²/L</strong></div>
              <div><small>Capas</small><strong>${item.capas}</strong></div>
              <div><small>Margen</small><strong>${formatNumber(item.desperdicio_porcentaje)}%</strong></div>
            </div>
            <div class="paint-guidance">
              <span><i class="fa-regular fa-clock"></i> Repintado: ${escapeHtml(item.tiempo_repintado_legible || "Revisar ficha")}</span>
              <span><i class="fa-solid fa-list-check"></i> Preparaci&oacute;n para tu proyecto: ${escapeHtml((item.preparacion_proyecto_display || []).join(", ") || "Revisar ficha del producto")}</span>
              ${item.advertencia_preparacion ? `<strong class="paint-warning"><i class="fa-solid fa-triangle-exclamation"></i> ${escapeHtml(item.advertencia_preparacion)}</strong>` : ""}
            </div>
            <div class="paint-budget">
              <div><small>Presupuesto estimado</small><strong>${formatClp(item.presupuesto_total)}</strong></div>
              <div class="paint-result-actions">
                ${cartButton}
                <a href="/productos/${id}/">Ver producto <i class="fa-solid fa-arrow-right"></i></a>
              </div>
            </div>
          </div>
        </article>`;
    }

    function connectImageFallbacks() {
      list.querySelectorAll("img").forEach(image => image.addEventListener("error", function replaceImage() {
        image.removeEventListener("error", replaceImage);
        if (fallbackImage) image.src = fallbackImage;
      }));
    }

    function currentCalculationPayload(productId) {
      return {
        producto: productId,
        superficie: Number(form.elements.superficie.value),
        ambiente: form.elements.ambiente.value,
        tipo_superficie: form.elements.tipo_superficie.value,
        estado_superficie: form.elements.estado_superficie.value,
        terminacion: form.elements.terminacion.value,
        capas: form.elements.capas.value ? Number(form.elements.capas.value) : null,
        desperdicio: form.elements.desperdicio.value || null,
      };
    }

    list.addEventListener("click", async event => {
      const button = event.target.closest("[data-add-calculation]");
      if (!button || button.disabled) return;
      if (!authenticated) {
        window.location.assign(loginUrl);
        return;
      }

      errorBox.hidden = true;
      const originalContent = button.innerHTML;
      button.disabled = true;
      button.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Verificando...';
      try {
        const response = await fetch(addCartUrl, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
            "X-CSRFToken": getCookie("csrftoken"),
          },
          body: JSON.stringify(currentCalculationPayload(Number(button.dataset.addCalculation))),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(firstError(data) || "No fue posible agregar la recomendación.");

        button.innerHTML = '<i class="fa-solid fa-circle-check"></i> Agregado';
        button.classList.add("added");

        const toastElement = document.getElementById("cart-toast");
        const messageElement = document.getElementById("cart-toast-message");
        if (messageElement && data.message) messageElement.textContent = data.message;
        if (toastElement) {
          if (window.bootstrap && window.bootstrap.Toast) {
            window.bootstrap.Toast.getOrCreateInstance(toastElement, { delay: 4000 }).show();
          } else {
            toastElement.classList.add("show");
            setTimeout(() => toastElement.classList.remove("show"), 4000);
          }
        }
      } catch (error) {
        errorBox.textContent = error.message || "No fue posible agregar la recomendación.";
        errorBox.hidden = false;
        errorBox.scrollIntoView({behavior: "smooth", block: "center"});
        button.disabled = false;
        button.innerHTML = originalContent;
      }
    });

    form.addEventListener("submit", async event => {
      event.preventDefault();
      errorBox.hidden = true;
      const surface = number(form.elements.superficie.value);
      if (!Number.isInteger(surface) || surface < 1 || surface > 100000) {
        errorBox.textContent = "Ingresa una superficie completa entre 1 y 100.000 m².";
        errorBox.hidden = false;
        return;
      }
      if (!form.elements.ambiente.value) {
        errorBox.textContent = "Selecciona si el proyecto es interior, exterior o especial.";
        errorBox.hidden = false;
        form.elements.ambiente.focus();
        return;
      }
      if (!form.elements.tipo_superficie.value) {
        errorBox.textContent = "Selecciona el tipo de superficie que vas a pintar.";
        errorBox.hidden = false;
        form.elements.tipo_superficie.focus();
        return;
      }
      if (!form.elements.estado_superficie.value) {
        errorBox.textContent = "Selecciona el estado actual de la superficie.";
        errorBox.hidden = false;
        form.elements.estado_superficie.focus();
        return;
      }

      const payload = {
        superficie: form.elements.superficie.value,
        ambiente: form.elements.ambiente.value,
        tipo_superficie: form.elements.tipo_superficie.value,
        estado_superficie: form.elements.estado_superficie.value,
        terminacion: form.elements.terminacion.value,
        capas: form.elements.capas.value ? Number(form.elements.capas.value) : null,
        desperdicio: form.elements.desperdicio.value ? form.elements.desperdicio.value : null,
        color: form.elements.color.value,
      };
      submit.disabled = true;
      submit.querySelector("span").textContent = "Calculando...";

      try {
        const response = await fetch(root.dataset.apiUrl, {
          method: "POST",
          credentials: "same-origin",
          headers: {"Content-Type": "application/json", Accept: "application/json", "X-CSRFToken": getCookie("csrftoken")},
          body: JSON.stringify(payload),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(firstError(data) || "No fue posible realizar el calculo.");

        results.hidden = false;
        count.textContent = `${data.total_resultados} alternativa${data.total_resultados === 1 ? "" : "s"}`;
        const finish = data.consulta.terminacion === "cualquiera"
          ? "sin terminacion preferida"
          : `terminacion ${String(data.consulta.terminacion_display || "").toLowerCase()}`;
        summary.textContent = `Calculo para ${formatNumber(data.consulta.superficie_m2, 0)} m², ambiente ${String(data.consulta.ambiente_display || "").toLowerCase()}, superficie ${String(data.consulta.tipo_superficie_display || "").toLowerCase()}, ${String(data.consulta.estado_superficie_display || "").toLowerCase()} y ${finish}.`;
        if (!data.recomendaciones.length) {
          list.innerHTML = `<div class="results-empty"><i class="fa-solid fa-paint-roller"></i><h3>No encontramos una pintura compatible</h3><p>Prueba cambiando el ambiente, la superficie, la terminaci&oacute;n o el color seleccionado.</p></div>`;
        } else {
          list.innerHTML = data.recomendaciones.map(resultCard).join("");
          connectImageFallbacks();
        }
        results.scrollIntoView({behavior: "smooth", block: "start"});
      } catch (error) {
        errorBox.textContent = error.message || "No fue posible realizar el calculo.";
        errorBox.hidden = false;
      } finally {
        submit.disabled = false;
        submit.querySelector("span").textContent = "Calcular materiales";
      }
    });

    if (new URLSearchParams(window.location.search).get("calculadora") === "1") {
      window.requestAnimationFrame(() => root.scrollIntoView({behavior: "smooth", block: "start"}));
    }
  });
})();
