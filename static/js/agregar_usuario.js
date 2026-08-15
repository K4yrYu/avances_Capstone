(() => {
  "use strict";

  const RUT_PATTERN = /^\d{7,8}-[\dkK]$/;
  const PHONE_PATTERN = /^\+?\d{9,15}$/;

  async function readJson(response) {
    try {
      return await response.json();
    } catch {
      return {};
    }
  }

  function firstError(value) {
    if (Array.isArray(value)) return value.map(firstError).filter(Boolean).join(" ");
    if (value && typeof value === "object") return Object.values(value).map(firstError).filter(Boolean).join(" ");
    return typeof value === "string" ? value : "";
  }

  document.addEventListener("DOMContentLoaded", () => {
    const root = document.getElementById("contenido-agregar-usuario");
    const form = document.getElementById("form-usuario");
    if (!root || !form) return;

    const fields = Object.fromEntries(
      ["rut", "username", "first_name", "last_name", "email", "telefono", "password", "password2"]
        .map((name) => [name, form.elements[name]])
    );
    const submitButton = document.getElementById("submit-user");
    const generalError = document.getElementById("user-general-error");
    const adminWarning = document.getElementById("admin-role-warning");
    const toastElement = document.getElementById("user-form-toast");
    const toast = toastElement && window.bootstrap
      ? window.bootstrap.Toast.getOrCreateInstance(toastElement, { delay: 1400 })
      : null;

    function setFieldError(name, message) {
      const error = form.querySelector(`[data-error-for="${name}"]`);
      if (error) error.textContent = message || "";
      fields[name]?.classList.toggle("is-invalid", Boolean(message));
    }

    function showGeneralError(message) {
      if (!generalError) return;
      generalError.textContent = message;
      generalError.hidden = !message;
    }

    function clearErrors() {
      Object.keys(fields).forEach((name) => setFieldError(name, ""));
      showGeneralError("");
    }

    function updatePasswordRequirements() {
      const password = fields.password.value;
      const confirmation = fields.password2.value;
      document.getElementById("password-length")?.classList.toggle("valid", password.length >= 8);
      document.getElementById("password-nonnumeric")?.classList.toggle("valid", Boolean(password) && !/^\d+$/.test(password));
      document.getElementById("password-match")?.classList.toggle("valid", Boolean(password) && password === confirmation);
    }

    fields.rut.addEventListener("input", () => {
      fields.rut.value = fields.rut.value.replace(/[.\s]/g, "").toUpperCase();
    });

    fields.telefono.addEventListener("input", () => {
      const hasPlus = fields.telefono.value.trim().startsWith("+");
      fields.telefono.value = `${hasPlus ? "+" : ""}${fields.telefono.value.replace(/\D/g, "")}`;
    });

    fields.email.addEventListener("blur", () => {
      fields.email.value = fields.email.value.trim().toLowerCase();
    });

    fields.username.addEventListener("input", () => {
      fields.username.value = fields.username.value.replace(/\s/g, "");
    });

    [fields.password, fields.password2].forEach((field) => field.addEventListener("input", updatePasswordRequirements));

    form.querySelectorAll("[data-password-toggle]").forEach((button) => {
      button.addEventListener("click", () => {
        const input = document.getElementById(button.dataset.passwordToggle);
        const showing = input.type === "text";
        input.type = showing ? "password" : "text";
        button.setAttribute("aria-label", showing ? "Mostrar contraseña" : "Ocultar contraseña");
        const icon = button.querySelector("i");
        icon.classList.toggle("fa-eye", showing);
        icon.classList.toggle("fa-eye-slash", !showing);
      });
    });

    form.querySelectorAll('[name="is_staff"]').forEach((radio) => {
      radio.addEventListener("change", () => {
        adminWarning.hidden = form.elements.is_staff.value !== "true";
      });
    });

    Object.entries(fields).forEach(([name, field]) => {
      field.addEventListener("input", () => setFieldError(name, ""));
      field.addEventListener("change", () => setFieldError(name, ""));
    });

    function validateForm() {
      clearErrors();
      const errors = {};
      if (!fields.first_name.value.trim()) errors.first_name = "Ingresa los nombres.";
      if (!fields.last_name.value.trim()) errors.last_name = "Ingresa los apellidos.";
      if (!RUT_PATTERN.test(fields.rut.value.trim())) errors.rut = "Usa el formato 12345678-9, sin puntos.";
      if (!PHONE_PATTERN.test(fields.telefono.value.trim())) errors.telefono = "Ingresa entre 9 y 15 dígitos, opcionalmente con +.";
      if (fields.username.value.trim().length < 3) errors.username = "El nombre de usuario debe tener al menos 3 caracteres.";
      if (!fields.email.validity.valid || !fields.email.value.trim()) errors.email = "Ingresa un correo electrónico válido.";
      if (fields.password.value.length < 8) errors.password = "La contraseña debe tener al menos 8 caracteres.";
      else if (/^\d+$/.test(fields.password.value)) errors.password = "La contraseña no puede ser completamente numérica.";
      if (fields.password.value !== fields.password2.value) errors.password2 = "Las contraseñas no coinciden.";

      Object.entries(errors).forEach(([name, message]) => setFieldError(name, message));
      form.querySelector(".is-invalid")?.focus();
      return Object.keys(errors).length === 0;
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!validateForm()) {
        showGeneralError("Revisa los campos marcados antes de crear el usuario.");
        return;
      }

      const payload = Object.fromEntries(new FormData(form).entries());
      delete payload.csrfmiddlewaretoken;
      payload.rut = payload.rut.trim().toUpperCase();
      payload.email = payload.email.trim().toLowerCase();
      payload.username = payload.username.trim();
      payload.first_name = payload.first_name.trim();
      payload.last_name = payload.last_name.trim();
      payload.telefono = payload.telefono.trim();
      payload.is_staff = payload.is_staff === "true";

      submitButton.disabled = true;
      submitButton.querySelector("span").textContent = "Creando usuario…";

      try {
        const response = await fetch(root.dataset.submitUrl, {
          method: "POST",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
            "X-CSRFToken": form.elements.csrfmiddlewaretoken.value,
          },
          body: JSON.stringify(payload),
        });
        const data = await readJson(response);
        if (!response.ok) {
          Object.entries(data).forEach(([name, value]) => {
            if (fields[name]) setFieldError(name, firstError(value));
          });
          throw new Error(firstError(data) || "No fue posible crear el usuario.");
        }

        toast?.show();
        setTimeout(() => window.location.assign(root.dataset.usersUrl), 850);
      } catch (error) {
        showGeneralError(error.message || "No fue posible crear el usuario.");
        submitButton.disabled = false;
        submitButton.querySelector("span").textContent = "Crear usuario";
      }
    });
  });
})();
