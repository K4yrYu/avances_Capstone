(() => {
  "use strict";

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
      };

      toggle.addEventListener("change", updateResult);
      resultSelect.addEventListener("change", updateResult);
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
