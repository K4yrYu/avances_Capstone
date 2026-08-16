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
})();
