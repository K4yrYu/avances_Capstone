(() => {
  "use strict";
  const PHONE = /^\+?\d{9,15}$/;
  const readJson = async (response) => { try { return await response.json(); } catch { return {}; } };
  const firstError = (value) => Array.isArray(value)
    ? value.map(firstError).filter(Boolean).join(" ")
    : value && typeof value === "object"
      ? Object.values(value).map(firstError).filter(Boolean).join(" ")
      : typeof value === "string" ? value : "";

  document.addEventListener("DOMContentLoaded", () => {
    const root = document.getElementById("registro-cuenta");
    const form = document.getElementById("registro-form");
    if (!root || !form) return;
    const names = ["rut", "username", "first_name", "last_name", "telefono", "email", "password", "password2"];
    const fields = Object.fromEntries(names.map((name) => [name, form.elements[name]]));
    const errorBox = document.getElementById("register-error");
    const submit = document.getElementById("register-submit");
    const setError = (name, message) => {
      const error = form.querySelector(`[data-error-for="${name}"]`);
      if (error) error.textContent = message || "";
      fields[name]?.classList.toggle("is-invalid", Boolean(message));
    };
    const showError = (message) => { errorBox.textContent = message; errorBox.hidden = !message; };
    const updateRules = () => {
      const password = fields.password.value;
      const confirmation = fields.password2.value;
      document.getElementById("rule-length").classList.toggle("valid", password.length >= 8);
      document.getElementById("rule-nonnumeric").classList.toggle("valid", Boolean(password) && !/^\d+$/.test(password));
      document.getElementById("rule-match").classList.toggle("valid", Boolean(password) && password === confirmation);
    };

    fields.rut.addEventListener("input", () => { fields.rut.value = fields.rut.value.toUpperCase(); });
    fields.rut.addEventListener("blur", () => {
      const normalizado = window.SFIRut?.normalizar(fields.rut.value);
      if (normalizado) fields.rut.value = normalizado;
    });
    fields.telefono.addEventListener("input", () => {
      const plus = fields.telefono.value.trim().startsWith("+");
      fields.telefono.value = `${plus ? "+" : ""}${fields.telefono.value.replace(/\D/g, "")}`;
    });
    fields.email.addEventListener("blur", () => { fields.email.value = fields.email.value.trim().toLowerCase(); });
    fields.username.addEventListener("input", () => { fields.username.value = fields.username.value.replace(/\s/g, ""); });
    [fields.password, fields.password2].forEach((field) => field.addEventListener("input", updateRules));
    form.querySelectorAll("[data-password-toggle]").forEach((button) => button.addEventListener("click", () => {
      const input = document.getElementById(button.dataset.passwordToggle);
      const show = input.type === "text";
      input.type = show ? "password" : "text";
      const icon = button.querySelector("i");
      icon.classList.toggle("fa-eye", show);
      icon.classList.toggle("fa-eye-slash", !show);
    }));
    Object.entries(fields).forEach(([name, field]) => field.addEventListener("input", () => { setError(name, ""); showError(""); }));

    const validate = () => {
      names.forEach((name) => setError(name, ""));
      const errors = {};
      if (!fields.first_name.value.trim()) errors.first_name = "Ingresa tus nombres.";
      if (!fields.last_name.value.trim()) errors.last_name = "Ingresa tus apellidos.";
      if (!window.SFIRut?.esValido(fields.rut.value)) errors.rut = "Ingresa un RUT válido; revisa el dígito verificador.";
      if (!PHONE.test(fields.telefono.value.trim())) errors.telefono = "Ingresa entre 9 y 15 dígitos.";
      if (fields.username.value.trim().length < 3) errors.username = "El usuario debe tener al menos 3 caracteres.";
      if (!fields.email.validity.valid || !fields.email.value.trim()) errors.email = "Ingresa un correo válido.";
      if (fields.password.value.length < 8) errors.password = "Usa al menos 8 caracteres.";
      else if (/^\d+$/.test(fields.password.value)) errors.password = "La contraseña no puede ser solo numérica.";
      if (fields.password.value !== fields.password2.value) errors.password2 = "Las contraseñas no coinciden.";
      Object.entries(errors).forEach(([name, message]) => setError(name, message));
      form.querySelector(".is-invalid")?.focus();
      return !Object.keys(errors).length;
    };

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      showError("");
      if (!validate()) { showError("Revisa los campos marcados para continuar."); return; }
      const data = Object.fromEntries(new FormData(form).entries());
      delete data.csrfmiddlewaretoken;
      data.email = data.email.trim().toLowerCase();
      data.rut = window.SFIRut.normalizar(data.rut);
      data.username = data.username.trim();
      submit.disabled = true;
      submit.querySelector("span").textContent = "Creando cuenta…";
      try {
        const response = await fetch(root.dataset.registerUrl, {
          method: "POST",
          headers: { Accept: "application/json", "Content-Type": "application/json", "X-CSRFToken": form.elements.csrfmiddlewaretoken.value },
          body: JSON.stringify(data),
        });
        const result = await readJson(response);
        if (!response.ok) {
          Object.entries(result).forEach(([name, value]) => fields[name] && setError(name, firstError(value)));
          throw new Error(firstError(result) || "No fue posible completar el registro.");
        }
        window.location.assign(result.redirect_url || root.dataset.pendingUrl);
      } catch (error) {
        showError(error.message || "No fue posible completar el registro.");
        submit.disabled = false;
        submit.querySelector("span").textContent = "Crear cuenta y verificar correo";
      }
    });
  });
})();
