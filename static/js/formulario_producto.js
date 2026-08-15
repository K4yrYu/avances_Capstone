(() => {
  "use strict";

  const MAX_IMAGE_SIZE = 5 * 1024 * 1024;
  const ALLOWED_IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

  function getCookie(name) {
    const prefix = `${name}=`;
    const cookie = document.cookie
      .split(";")
      .map((value) => value.trim())
      .find((value) => value.startsWith(prefix));
    return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : null;
  }

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
    const root = document.getElementById("contenido-formulario");
    const form = document.getElementById("form-producto");
    if (!root || !form) return;

    const nameInput = document.getElementById("nombre");
    const descriptionInput = document.getElementById("descripcion");
    const categoryInput = document.getElementById("categoria");
    const priceInput = document.getElementById("precio");
    const stockInput = document.getElementById("stock");
    const activeInput = document.getElementById("activo");
    const imageInput = document.getElementById("imagen");
    const imageZone = document.getElementById("image-upload-zone");
    const imagePreview = document.getElementById("image-preview");
    const uploadPlaceholder = document.getElementById("upload-placeholder");
    const changeImage = document.getElementById("change-image");
    const descriptionCount = document.getElementById("description-count");
    const pricePreview = document.getElementById("price-preview");
    const submitButton = document.getElementById("submit-product");
    const generalError = document.getElementById("form-general-error");
    const toastElement = document.getElementById("product-form-toast");
    const toast = toastElement && window.bootstrap
      ? window.bootstrap.Toast.getOrCreateInstance(toastElement, { delay: 1400 })
      : null;

    let previewUrl = "";

    function setFieldError(fieldName, message) {
      const error = form.querySelector(`[data-error-for="${fieldName}"]`);
      const field = form.elements[fieldName];
      if (error) error.textContent = message || "";
      field?.classList.toggle("is-invalid", Boolean(message));
      if (fieldName === "imagen") imageZone?.classList.toggle("has-error", Boolean(message));
    }

    function clearErrors() {
      form.querySelectorAll(".field-error").forEach((error) => { error.textContent = ""; });
      form.querySelectorAll(".is-invalid").forEach((field) => field.classList.remove("is-invalid"));
      imageZone?.classList.remove("has-error");
      if (generalError) {
        generalError.textContent = "";
        generalError.hidden = true;
      }
    }

    function showGeneralError(message) {
      if (!generalError) return;
      generalError.textContent = message;
      generalError.hidden = !message;
    }

    function validateImage(file) {
      if (!file) return "Debes seleccionar una imagen del producto.";
      if (!ALLOWED_IMAGE_TYPES.has(file.type)) return "Solo se permiten imágenes JPG, PNG o WebP.";
      if (file.size > MAX_IMAGE_SIZE) return "La imagen no puede superar los 5 MB.";
      return "";
    }

    function showImage(file) {
      const error = validateImage(file);
      setFieldError("imagen", error);
      if (error) return false;

      if (previewUrl) URL.revokeObjectURL(previewUrl);
      previewUrl = URL.createObjectURL(file);
      imagePreview.src = previewUrl;
      imagePreview.hidden = false;
      uploadPlaceholder.hidden = true;
      changeImage.hidden = false;
      return true;
    }

    imageInput.addEventListener("change", () => showImage(imageInput.files[0]));

    ["dragenter", "dragover"].forEach((eventName) => {
      imageZone.addEventListener(eventName, (event) => {
        event.preventDefault();
        imageZone.classList.add("is-dragging");
      });
    });

    ["dragleave", "drop"].forEach((eventName) => {
      imageZone.addEventListener(eventName, (event) => {
        event.preventDefault();
        imageZone.classList.remove("is-dragging");
      });
    });

    imageZone.addEventListener("drop", (event) => {
      const file = event.dataTransfer.files[0];
      if (!file || !showImage(file)) return;
      const transfer = new DataTransfer();
      transfer.items.add(file);
      imageInput.files = transfer.files;
    });

    descriptionInput.addEventListener("input", () => {
      descriptionCount.textContent = `${descriptionInput.value.length} caracteres`;
    });

    priceInput.addEventListener("input", () => {
      const value = Number(priceInput.value);
      pricePreview.textContent = new Intl.NumberFormat("es-CL", {
        style: "currency",
        currency: "CLP",
        maximumFractionDigits: 0,
      }).format(Number.isFinite(value) && value > 0 ? value : 0);
    });

    [nameInput, descriptionInput, categoryInput, priceInput, stockInput].forEach((field) => {
      field.addEventListener("input", () => setFieldError(field.name, ""));
      field.addEventListener("change", () => setFieldError(field.name, ""));
    });

    function validateForm() {
      clearErrors();
      const errors = {};
      if (nameInput.value.trim().length < 2) errors.nombre = "Ingresa un nombre de al menos 2 caracteres.";
      if (!descriptionInput.value.trim()) errors.descripcion = "Ingresa una descripción del producto.";
      if (!categoryInput.value) errors.categoria = "Selecciona una categoría.";
      if (!Number.isInteger(Number(priceInput.value)) || Number(priceInput.value) < 1) errors.precio = "El precio debe ser un número entero mayor que cero.";
      if (!Number.isInteger(Number(stockInput.value)) || Number(stockInput.value) < 0) errors.stock = "El stock debe ser un número entero igual o mayor que cero.";
      const imageError = validateImage(imageInput.files[0]);
      if (imageError) errors.imagen = imageError;

      Object.entries(errors).forEach(([field, message]) => setFieldError(field, message));
      const firstInvalid = form.querySelector(".is-invalid") || (errors.imagen ? imageZone : null);
      firstInvalid?.focus?.();
      return Object.keys(errors).length === 0;
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!validateForm()) {
        showGeneralError("Revisa los campos marcados antes de crear el producto.");
        return;
      }

      const payload = new FormData();
      payload.append("nombre", nameInput.value.trim());
      payload.append("descripcion", descriptionInput.value.trim());
      payload.append("categoria", categoryInput.value);
      payload.append("precio", priceInput.value);
      payload.append("stock", stockInput.value);
      payload.append("activo", activeInput.checked ? "true" : "false");
      payload.append("imagen", imageInput.files[0]);

      submitButton.disabled = true;
      submitButton.querySelector("span").textContent = "Creando producto…";

      try {
        const response = await fetch(root.dataset.submitUrl, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            Accept: "application/json",
            "X-CSRFToken": getCookie("csrftoken") || "",
          },
          body: payload,
        });
        const data = await readJson(response);
        if (!response.ok) {
          Object.entries(data).forEach(([field, value]) => {
            if (form.elements[field]) setFieldError(field, firstError(value));
          });
          throw new Error(firstError(data) || "No fue posible crear el producto.");
        }

        toast?.show();
        setTimeout(() => window.location.assign(root.dataset.productsUrl), 850);
      } catch (error) {
        showGeneralError(error.message || "No fue posible crear el producto.");
        submitButton.disabled = false;
        submitButton.querySelector("span").textContent = "Crear producto";
      }
    });

    window.addEventListener("beforeunload", () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    });
  });
})();
