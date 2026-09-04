(() => {
  "use strict";

  const MAX_IMAGE_SIZE = 5 * 1024 * 1024;
  const ALLOWED_IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

  function getCookie(name) {
    const prefix = `${name}=`;
    const cookie = document.cookie.split(";").map((value) => value.trim()).find((value) => value.startsWith(prefix));
    return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : null;
  }

  async function readJson(response) {
    try { return await response.json(); } catch { return {}; }
  }

  function firstError(value) {
    if (Array.isArray(value)) return value.map(firstError).filter(Boolean).join(" ");
    if (value && typeof value === "object") return Object.values(value).map(firstError).filter(Boolean).join(" ");
    return typeof value === "string" ? value : "";
  }

  function parseSpecifications(text) {
    const result = {};
    const invalid = [];
    String(text || "").split(/\r?\n/).forEach((line, index) => {
      const clean = line.trim();
      if (!clean) return;
      const separator = clean.indexOf(":");
      if (separator < 1 || !clean.slice(separator + 1).trim()) {
        invalid.push(index + 1);
        return;
      }
      const key = clean.slice(0, separator).trim();
      const value = clean.slice(separator + 1).trim();
      result[key] = value;
    });
    return { result, invalid };
  }

  document.addEventListener("DOMContentLoaded", () => {
    const root = document.getElementById("contenido-formulario");
    const form = document.getElementById("form-producto");
    if (!root || !form) return;

    const mode = root.dataset.mode === "edit" ? "edit" : "create";
    const existingImage = root.dataset.existingImage || "";
    const fieldNames = [
      "nombre", "descripcion", "categoria", "precio", "marca", "modelo", "sku", "color", "color_hex", "ambiente_uso",
      "proveedor", "stock", "stock_minimo", "controla_vencimiento", "activo",
      "unidad_venta", "contenido", "unidad_contenido", "tipo_calculo", "rendimiento",
      "unidad_rendimiento", "capas_recomendadas", "porcentaje_desperdicio", "uso_recomendado",
      "tipo_pintura", "terminacion", "secado_tacto_horas", "repintado_min_horas", "repintado_max_horas",
      "especificaciones", "informacion_tecnica_verificada", "imagen",
    ];
    const fields = Object.fromEntries(fieldNames.map((name) => [name, form.elements[name]]));
    const imageZone = document.getElementById("image-upload-zone");
    const imagePreview = document.getElementById("image-preview");
    const uploadPlaceholder = document.getElementById("upload-placeholder");
    const changeImage = document.getElementById("change-image");
    const descriptionCount = document.getElementById("description-count");
    const pricePreview = document.getElementById("price-preview");
    const technicalPreview = document.getElementById("technical-preview");
    const colorPicker = document.getElementById("color-picker");
    const surfaceField = document.getElementById("superficies-compatibles-field");
    const surfaceOptions = [...document.querySelectorAll("#superficies-compatibles-group input[type='checkbox']")];
    const propertyField = document.getElementById("propiedades-pintura-field");
    const propertyOptions = [...document.querySelectorAll("#propiedades-pintura-group input[type='checkbox']")];
    const preparationField = document.getElementById("preparaciones-pintura-field");
    const preparationOptions = [...document.querySelectorAll("#preparaciones-pintura-group input[type='checkbox']")];
    const providerForm = document.getElementById("form-proveedor-producto");
    const providerModalElement = document.getElementById("modalProveedorProducto");
    const providerFeedback = document.getElementById("provider-form-feedback");
    const submitButton = document.getElementById("submit-product");
    const generalError = document.getElementById("form-general-error");
    const toastElement = document.getElementById("product-form-toast");
    const toast = toastElement && window.bootstrap
      ? window.bootstrap.Toast.getOrCreateInstance(toastElement, { delay: 1400 })
      : null;
    let previewUrl = "";

    function productUsesColor() {
      return fields.categoria.value === "Pinturas" || fields.tipo_calculo.value === "pintura";
    }

    function updateColorState() {
      const visible = productUsesColor();
      [fields.color, fields.color_hex].forEach((field) => {
        const container = field?.closest(".admin-field");
        if (container) container.hidden = !visible;
        if (field) field.disabled = !visible;
      });
      const environmentContainer = fields.ambiente_uso?.closest(".admin-field");
      if (environmentContainer) environmentContainer.hidden = !visible;
      if (fields.ambiente_uso) fields.ambiente_uso.disabled = !visible;
      if (surfaceField) surfaceField.hidden = !visible;
      surfaceOptions.forEach((option) => { option.disabled = !visible; });
      document.querySelectorAll(".paint-advanced-field").forEach((field) => { field.hidden = !visible; });
      [...propertyOptions, ...preparationOptions].forEach((option) => { option.disabled = !visible; });
      if (colorPicker) colorPicker.disabled = !visible;
    }

    function setFieldError(fieldName, message) {
      const error = form.querySelector(`[data-error-for="${fieldName}"]`);
      const field = fields[fieldName];
      if (error) error.textContent = message || "";
      field?.classList.toggle("is-invalid", Boolean(message));
      if (fieldName === "imagen") imageZone?.classList.toggle("has-error", Boolean(message));
      if (fieldName === "superficies_compatibles") surfaceField?.classList.toggle("has-error", Boolean(message));
      if (fieldName === "propiedades_pintura") propertyField?.classList.toggle("has-error", Boolean(message));
      if (fieldName === "preparaciones_recomendadas") preparationField?.classList.toggle("has-error", Boolean(message));
    }

    function clearErrors() {
      form.querySelectorAll(".field-error").forEach((error) => { error.textContent = ""; });
      form.querySelectorAll(".is-invalid").forEach((field) => field.classList.remove("is-invalid"));
      imageZone?.classList.remove("has-error");
      surfaceField?.classList.remove("has-error");
      propertyField?.classList.remove("has-error");
      preparationField?.classList.remove("has-error");
      generalError.textContent = "";
      generalError.hidden = true;
    }

    function showGeneralError(message) {
      generalError.textContent = message || "";
      generalError.hidden = !message;
    }

    function validateImage(file) {
      if (!file && mode === "create") return "Debes seleccionar una imagen del producto.";
      if (!file) return "";
      if (!ALLOWED_IMAGE_TYPES.has(file.type)) return "Solo se permiten imágenes JPG, PNG o WebP.";
      if (file.size > MAX_IMAGE_SIZE) return "La imagen no puede superar los 5 MB.";
      return "";
    }

    function showImage(file) {
      const error = validateImage(file);
      setFieldError("imagen", error);
      if (error || !file) return false;
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      previewUrl = URL.createObjectURL(file);
      imagePreview.src = previewUrl;
      imagePreview.hidden = false;
      uploadPlaceholder.hidden = true;
      changeImage.hidden = false;
      return true;
    }

    fields.imagen.addEventListener("change", () => showImage(fields.imagen.files[0]));
    ["dragenter", "dragover"].forEach((eventName) => imageZone.addEventListener(eventName, (event) => {
      event.preventDefault(); imageZone.classList.add("is-dragging");
    }));
    ["dragleave", "drop"].forEach((eventName) => imageZone.addEventListener(eventName, (event) => {
      event.preventDefault(); imageZone.classList.remove("is-dragging");
    }));
    imageZone.addEventListener("drop", (event) => {
      const file = event.dataTransfer.files[0];
      if (!file || !showImage(file)) return;
      const transfer = new DataTransfer();
      transfer.items.add(file);
      fields.imagen.files = transfer.files;
    });

    function updateDescriptionCount() {
      descriptionCount.textContent = `${fields.descripcion.value.length} caracteres`;
    }

    function updatePricePreview() {
      const value = Number(fields.precio.value);
      pricePreview.textContent = new Intl.NumberFormat("es-CL", {
        style: "currency", currency: "CLP", maximumFractionDigits: 0,
      }).format(Number.isFinite(value) && value > 0 ? value : 0);
    }

    function updateTechnicalState() {
      const calculationType = fields.tipo_calculo.value;
      document.querySelectorAll(".calculation-field").forEach((element) => {
        element.classList.toggle("technical-field-muted", calculationType === "ninguno");
      });
      document.querySelectorAll(".paint-field").forEach((element) => {
        element.hidden = calculationType !== "pintura";
      });
      const verified = fields.informacion_tecnica_verificada.checked;
      const repaintMin = Number(fields.repintado_min_horas.value);
      const repaintMax = Number(fields.repintado_max_horas.value);
      const touchDry = Number(fields.secado_tacto_horas.value);
      technicalPreview.textContent = verified
        ? (calculationType === "ninguno" ? "Ficha comercial verificada; sin cálculo automático." : "Ficha preparada para validación del asistente SFI.")
        : "Ficha técnica pendiente de verificación.";
      technicalPreview.classList.toggle("verified", verified);
      updateColorState();
    }

    fields.descripcion.addEventListener("input", updateDescriptionCount);
    fields.precio.addEventListener("input", updatePricePreview);
    fields.categoria.addEventListener("change", updateColorState);
    fields.tipo_calculo.addEventListener("change", updateTechnicalState);
    fields.informacion_tecnica_verificada.addEventListener("change", updateTechnicalState);
    colorPicker?.addEventListener("input", () => {
      fields.color_hex.value = colorPicker.value.toUpperCase();
      setFieldError("color_hex", "");
    });
    fields.color_hex?.addEventListener("input", () => {
      if (/^#[0-9a-f]{6}$/i.test(fields.color_hex.value)) colorPicker.value = fields.color_hex.value;
    });
    fieldNames.filter((name) => !["activo", "controla_vencimiento", "informacion_tecnica_verificada", "imagen"].includes(name)).forEach((name) => {
      fields[name]?.addEventListener("input", () => setFieldError(name, ""));
      fields[name]?.addEventListener("change", () => setFieldError(name, ""));
    });

    function validateForm() {
      clearErrors();
      const errors = {};
      const content = Number(fields.contenido.value);
      const performance = Number(fields.rendimiento.value);
      const waste = Number(fields.porcentaje_desperdicio.value);
      const layers = Number(fields.capas_recomendadas.value);
      const touchDry = Number(fields.secado_tacto_horas.value);
      const repaintMin = Number(fields.repintado_min_horas.value);
      const repaintMax = Number(fields.repintado_max_horas.value);
      const calculationType = fields.tipo_calculo.value;
      const verified = fields.informacion_tecnica_verificada.checked;
      const specifications = parseSpecifications(fields.especificaciones.value);

      if (fields.nombre.value.trim().length < 2) errors.nombre = "Ingresa un nombre de al menos 2 caracteres.";
      if (!fields.descripcion.value.trim()) errors.descripcion = "Ingresa una descripción del producto.";
      if (!fields.marca.value.trim()) errors.marca = "Ingresa la marca del producto.";
      if (!fields.categoria.value) errors.categoria = "Selecciona una categoría.";
      if (!Number.isInteger(Number(fields.precio.value)) || Number(fields.precio.value) < 1) errors.precio = "El precio debe ser un número entero mayor que cero.";
      if (!Number.isInteger(Number(fields.stock.value)) || Number(fields.stock.value) < 0) errors.stock = "El stock debe ser un número entero igual o mayor que cero.";
      if (!Number.isInteger(Number(fields.stock_minimo.value)) || Number(fields.stock_minimo.value) < 0 || Number(fields.stock_minimo.value) > 1000000) errors.stock_minimo = "El stock mínimo debe estar entre 0 y 1.000.000.";
      if (productUsesColor() && fields.color_hex.value && !/^#[0-9a-f]{6}$/i.test(fields.color_hex.value)) errors.color_hex = "Usa un color hexadecimal como #FFFFFF.";
      if (productUsesColor() && fields.ambiente_uso.value === "no_aplica") errors.ambiente_uso = "Selecciona el ambiente de uso de la pintura.";
      if (productUsesColor() && !surfaceOptions.some((option) => option.checked)) errors.superficies_compatibles = "Selecciona al menos una superficie compatible.";
      if (productUsesColor() && fields.tipo_pintura.value === "no_aplica") errors.tipo_pintura = "Selecciona el tipo de pintura.";
      if (productUsesColor() && fields.terminacion.value === "no_aplica") errors.terminacion = "Selecciona la terminaciÃ³n.";
      if (fields.secado_tacto_horas.value && (!Number.isFinite(touchDry) || touchDry <= 0 || touchDry > 168)) errors.secado_tacto_horas = "El secado debe estar entre 0,01 y 168 horas.";
      if (productUsesColor() && fields.repintado_min_horas.value && (!Number.isFinite(repaintMin) || repaintMin <= 0 || repaintMin > 720)) errors.repintado_min_horas = "Ingresa un tiempo de repintado vÃ¡lido.";
      if (fields.repintado_max_horas.value && (!Number.isFinite(repaintMax) || repaintMax <= 0 || repaintMax > 720)) errors.repintado_max_horas = "Ingresa un tiempo mÃ¡ximo vÃ¡lido.";
      if (fields.repintado_min_horas.value && fields.repintado_max_horas.value && repaintMax < repaintMin) errors.repintado_max_horas = "El mÃ¡ximo no puede ser menor que el mÃ­nimo.";
      if (fields.contenido.value && (!Number.isFinite(content) || content <= 0)) errors.contenido = "Ingresa un contenido mayor que cero.";
      if (Boolean(fields.contenido.value) !== Boolean(fields.unidad_contenido.value)) errors.contenido = "Indica el contenido y su unidad.";
      if (fields.rendimiento.value && (!Number.isFinite(performance) || performance <= 0)) errors.rendimiento = "Ingresa un rendimiento mayor que cero.";
      if (Boolean(fields.rendimiento.value) !== Boolean(fields.unidad_rendimiento.value)) errors.rendimiento = "Indica el rendimiento y su unidad.";
      if (!Number.isFinite(waste) || waste < 0 || waste > 50) errors.porcentaje_desperdicio = "El margen debe estar entre 0% y 50%.";
      if (specifications.invalid.length) errors.especificaciones = `Revisa el formato de la${specifications.invalid.length > 1 ? "s" : ""} línea${specifications.invalid.length > 1 ? "s" : ""} ${specifications.invalid.join(", ")}.`;
      if (Object.keys(specifications.result).length > 20) errors.especificaciones = "Registra como máximo 20 especificaciones.";
      if (calculationType === "pintura" && fields.unidad_contenido.value && fields.unidad_contenido.value !== "l") errors.unidad_contenido = "La pintura debe registrar el contenido en litros.";
      if (calculationType === "pintura" && fields.unidad_rendimiento.value && fields.unidad_rendimiento.value !== "m2_l") errors.unidad_rendimiento = "La pintura debe usar m² por litro.";

      if (verified && calculationType !== "ninguno") {
        if (!fields.contenido.value || !fields.unidad_contenido.value) errors.contenido = "Una ficha verificada necesita contenido y unidad.";
        if (["pintura", "superficie"].includes(calculationType) && (!fields.rendimiento.value || !fields.unidad_rendimiento.value)) errors.rendimiento = "Este cálculo necesita un rendimiento comprobado.";
        if (calculationType === "pintura" && (!Number.isInteger(layers) || layers < 1 || layers > 10)) errors.capas_recomendadas = "Indica entre 1 y 10 capas recomendadas.";
        if (calculationType === "pintura" && !propertyOptions.some((option) => option.checked)) errors.propiedades_pintura = "Registra al menos una propiedad verificada.";
        if (calculationType === "pintura" && !preparationOptions.some((option) => option.checked)) errors.preparaciones_recomendadas = "Registra al menos una preparaciÃ³n recomendada.";
        if (calculationType === "pintura" && !fields.repintado_min_horas.value) errors.repintado_min_horas = "Indica el tiempo mÃ­nimo de repintado.";
      }

      const imageError = validateImage(fields.imagen.files[0]);
      if (imageError) errors.imagen = imageError;
      Object.entries(errors).forEach(([field, message]) => setFieldError(field, message));
      const firstInvalid = form.querySelector(".is-invalid") || (errors.imagen ? imageZone : null);
      firstInvalid?.focus?.();
      return { valid: Object.keys(errors).length === 0, specifications: specifications.result };
    }

    function appendValue(payload, name) {
      const value = fields[name].value.trim();
      payload.append(name, value);
    }

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const validation = validateForm();
      if (!validation.valid) {
        showGeneralError("Revisa los campos marcados antes de guardar el producto.");
        return;
      }

      const payload = new FormData();
      ["nombre", "descripcion", "categoria", "precio", "marca", "modelo", "sku",
        "proveedor", "stock", "stock_minimo", "unidad_venta",
        "contenido", "unidad_contenido", "tipo_calculo", "rendimiento", "unidad_rendimiento",
        "capas_recomendadas", "porcentaje_desperdicio", "ambiente_uso", "tipo_pintura", "terminacion",
        "secado_tacto_horas", "repintado_min_horas", "repintado_max_horas", "uso_recomendado"].forEach((name) => appendValue(payload, name));
      payload.append("color", productUsesColor() ? fields.color.value.trim() : "");
      payload.append("color_hex", productUsesColor() ? fields.color_hex.value.trim() : "");
      payload.append("superficies_compatibles", JSON.stringify(
        productUsesColor() ? surfaceOptions.filter((option) => option.checked).map((option) => option.value) : []
      ));
      payload.append("propiedades_pintura", JSON.stringify(
        productUsesColor() ? propertyOptions.filter((option) => option.checked).map((option) => option.value) : []
      ));
      payload.append("preparaciones_recomendadas", JSON.stringify(
        productUsesColor() ? preparationOptions.filter((option) => option.checked).map((option) => option.value) : []
      ));
      payload.append("activo", fields.activo.checked ? "true" : "false");
      payload.append("controla_vencimiento", fields.controla_vencimiento.checked ? "true" : "false");
      payload.append("informacion_tecnica_verificada", fields.informacion_tecnica_verificada.checked ? "true" : "false");
      payload.append("especificaciones", JSON.stringify(validation.specifications));
      if (fields.imagen.files[0]) payload.append("imagen", fields.imagen.files[0]);

      submitButton.disabled = true;
      submitButton.querySelector("span").textContent = mode === "edit" ? "Guardando cambios…" : "Creando producto…";

      try {
        const response = await fetch(root.dataset.submitUrl, {
          method: mode === "edit" ? "PUT" : "POST",
          credentials: "same-origin",
          headers: { Accept: "application/json", "X-CSRFToken": getCookie("csrftoken") || "" },
          body: payload,
        });
        const data = await readJson(response);
        if (!response.ok) {
          Object.entries(data).forEach(([field, value]) => {
            if (fields[field]) setFieldError(field, firstError(value));
          });
          throw new Error(firstError(data) || "No fue posible guardar el producto.");
        }
        toast?.show();
        setTimeout(() => window.location.assign(root.dataset.productsUrl), 850);
      } catch (error) {
        showGeneralError(error.message || "No fue posible guardar el producto.");
        submitButton.disabled = false;
        submitButton.querySelector("span").textContent = mode === "edit" ? "Guardar cambios" : "Crear producto";
      }
    });

    if (mode === "edit" && existingImage) {
      imagePreview.src = existingImage;
      imagePreview.hidden = false;
      uploadPlaceholder.hidden = true;
      changeImage.hidden = false;
    }

    providerForm?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const submit = providerForm.querySelector("button[type='submit']");
      const name = providerForm.elements.nombre.value.trim();
      const email = providerForm.elements.email.value.trim();
      providerFeedback.hidden = true;
      if (!name || !email || !providerForm.checkValidity()) {
        providerFeedback.textContent = "Completa el nombre de la empresa y un correo valido.";
        providerFeedback.hidden = false;
        providerForm.reportValidity();
        return;
      }
      submit.disabled = true;
      try {
        const response = await fetch(root.dataset.providerUrl, {
          method: "POST",
          credentials: "same-origin",
          headers: {Accept: "application/json", "X-CSRFToken": getCookie("csrftoken") || ""},
          body: new FormData(providerForm),
        });
        const data = await readJson(response);
        if (!response.ok) throw new Error(firstError(data) || "No fue posible guardar el proveedor.");
        const option = new Option(`${data.nombre} - ${data.email}`, String(data.id), true, true);
        fields.proveedor.add(option);
        fields.proveedor.dispatchEvent(new Event("change", {bubbles: true}));
        providerForm.reset();
        window.bootstrap?.Modal.getOrCreateInstance(providerModalElement).hide();
      } catch (error) {
        providerFeedback.textContent = error.message || "No fue posible guardar el proveedor.";
        providerFeedback.hidden = false;
      } finally {
        submit.disabled = false;
      }
    });
    updateDescriptionCount();
    updatePricePreview();
    updateTechnicalState();
    window.addEventListener("beforeunload", () => { if (previewUrl) URL.revokeObjectURL(previewUrl); });
  });
})();
