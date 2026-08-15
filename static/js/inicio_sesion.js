(() => {
  "use strict";
  async function readJson(response) { try { return await response.json(); } catch { return {}; } }
  function firstError(value) {
    if (Array.isArray(value)) return value.map(firstError).filter(Boolean).join(" ");
    if (value && typeof value === "object") return Object.values(value).map(firstError).filter(Boolean).join(" ");
    return typeof value === "string" ? value : "";
  }
  document.addEventListener("DOMContentLoaded", () => {
    const root = document.getElementById("inicio-sesion");
    const form = document.getElementById("form-login");
    if (!root || !form) return;
    const username = form.elements.username;
    const password = form.elements.password;
    const errorBox = document.getElementById("login-error");
    const submitButton = document.getElementById("login-submit");
    const togglePassword = document.getElementById("toggle-password");
    function setFieldError(name, message) {
      const input = form.elements[name];
      const error = form.querySelector(`[data-error-for="${name}"]`);
      input?.classList.toggle("is-invalid", Boolean(message));
      if (error) error.textContent = message || "";
    }
    function showError(message, success = false) {
      errorBox.textContent = message;
      errorBox.hidden = !message;
      errorBox.classList.toggle("is-success", success);
    }
    [username, password].forEach((input) => input.addEventListener("input", () => { setFieldError(input.name, ""); showError(""); }));
    togglePassword.addEventListener("click", () => {
      const showing = password.type === "text";
      password.type = showing ? "password" : "text";
      togglePassword.setAttribute("aria-label", showing ? "Mostrar contraseña" : "Ocultar contraseña");
      const icon = togglePassword.querySelector("i");
      icon.classList.toggle("fa-eye", showing);
      icon.classList.toggle("fa-eye-slash", !showing);
    });
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      setFieldError("username", ""); setFieldError("password", ""); showError("");
      if (!username.value.trim()) { setFieldError("username", "Ingresa tu nombre de usuario."); username.focus(); return; }
      if (!password.value) { setFieldError("password", "Ingresa tu contraseña."); password.focus(); return; }
      submitButton.disabled = true;
      submitButton.querySelector("span").textContent = "Verificando acceso…";
      try {
        const response = await fetch(root.dataset.loginUrl, {
          method:"POST",
          headers:{Accept:"application/json","Content-Type":"application/json","X-CSRFToken":form.elements.csrfmiddlewaretoken.value},
          body:JSON.stringify({username:username.value.trim(),password:password.value,next:root.dataset.nextUrl}),
        });
        const data = await readJson(response);
        if (!response.ok) throw new Error(firstError(data) || "Usuario o contraseña incorrectos.");
        showError("Acceso correcto. Redirigiendo…", true);
        submitButton.querySelector("span").textContent = "Acceso correcto";
        setTimeout(() => window.location.assign(data.redirect_url || "/"), 450);
      } catch (error) {
        showError(error.message || "No fue posible iniciar sesión.");
        submitButton.disabled = false;
        submitButton.querySelector("span").textContent = "Ingresar a mi cuenta";
      }
    });
  });
})();
