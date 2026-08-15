(() => {
  "use strict";

  document.addEventListener("DOMContentLoaded", () => {
    const root = document.getElementById("chat-sfi");
    const workbench = document.getElementById("paint-workbench");
    const attach = document.getElementById("attach-paint-photo");
    const close = document.getElementById("close-paint-workbench");
    const fileInput = document.getElementById("paint-photo-input");
    const fileName = document.getElementById("paint-photo-name");
    const canvas = document.getElementById("paint-photo-canvas");
    const emptyState = document.getElementById("paint-empty-state");
    const hint = document.getElementById("paint-canvas-hint");
    const tolerance = document.getElementById("paint-tolerance");
    const toleranceValue = document.getElementById("paint-tolerance-value");
    const selectedProduct = document.getElementById("selected-paint-product");
    const reset = document.getElementById("reset-paint-mask");
    const compare = document.getElementById("compare-original");
    const download = document.getElementById("download-paint-preview");
    const analyze = document.getElementById("analyze-paint-photo");
    const analysis = document.getElementById("paint-analysis");
    const security = window.FerremasSecurity;
    if (!root || !workbench || !canvas || !fileInput || !security) return;

    const STORAGE_KEY = "sfi_paint_assistant_v1";
    const context = canvas.getContext("2d", {willReadFrequently: true});
    const {safeUrl} = security;
    let photoFile = null;
    let sourcePixels = null;
    let selectedMask = null;
    let selectedColor = "";
    let selectedProductId = null;
    let selectedPaintName = "";
    let marks = [];
    let lastAnalysis = null;
    let imageDataUrl = "";

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

    function saveState() {
      try {
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
          imageDataUrl,
          fileName: photoFile ? photoFile.name : "foto-sfi.jpg",
          selectedColor,
          selectedProductId,
          selectedPaintName,
          marks,
          analysis: lastAnalysis,
          tolerance: Number(tolerance.value),
        }));
      } catch (_error) {
        // Si el navegador limita el almacenamiento, la herramienta continúa funcionando.
      }
    }

    function clearState() {
      sessionStorage.removeItem(STORAGE_KEY);
      photoFile = null;
      sourcePixels = null;
      selectedMask = null;
      selectedColor = "";
      selectedProductId = null;
      selectedPaintName = "";
      marks = [];
      lastAnalysis = null;
      imageDataUrl = "";
      fileInput.value = "";
      canvas.hidden = true;
      emptyState.hidden = false;
      hint.hidden = true;
      analysis.hidden = true;
      fileName.textContent = "JPG, PNG o WebP · máximo 4 MB";
      selectedProduct.textContent = "Analiza la foto para recibir colores recomendados.";
      analyze.disabled = true;
      reset.disabled = true;
      compare.disabled = true;
      download.disabled = true;
    }

    function hexToRgb(hex) {
      const clean = String(hex || "").replace("#", "");
      return {r: parseInt(clean.slice(0, 2), 16) || 0, g: parseInt(clean.slice(2, 4), 16) || 0, b: parseInt(clean.slice(4, 6), 16) || 0};
    }

    function rgbToHsl(r, g, b) {
      const red = r / 255;
      const green = g / 255;
      const blue = b / 255;
      const max = Math.max(red, green, blue);
      const min = Math.min(red, green, blue);
      let hue = 0;
      let saturation = 0;
      const lightness = (max + min) / 2;
      if (max !== min) {
        const delta = max - min;
        saturation = lightness > 0.5 ? delta / (2 - max - min) : delta / (max + min);
        if (max === red) hue = (green - blue) / delta + (green < blue ? 6 : 0);
        if (max === green) hue = (blue - red) / delta + 2;
        if (max === blue) hue = (red - green) / delta + 4;
        hue /= 6;
      }
      return {h: hue, s: saturation, l: lightness};
    }

    function hslToRgb(h, s, l) {
      if (s === 0) {
        const gray = Math.round(l * 255);
        return {r: gray, g: gray, b: gray};
      }
      const hueToRgb = (p, q, raw) => {
        let value = raw;
        if (value < 0) value += 1;
        if (value > 1) value -= 1;
        if (value < 1 / 6) return p + (q - p) * 6 * value;
        if (value < 1 / 2) return q;
        if (value < 2 / 3) return p + (q - p) * (2 / 3 - value) * 6;
        return p;
      };
      const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
      const p = 2 * l - q;
      return {r: Math.round(hueToRgb(p, q, h + 1 / 3) * 255), g: Math.round(hueToRgb(p, q, h) * 255), b: Math.round(hueToRgb(p, q, h - 1 / 3) * 255)};
    }

    function renderPreview(showOriginal = false) {
      if (!sourcePixels) return;
      if (showOriginal || !selectedMask || !selectedColor) {
        context.putImageData(sourcePixels, 0, 0);
        return;
      }
      const output = new ImageData(new Uint8ClampedArray(sourcePixels.data), canvas.width, canvas.height);
      const target = hexToRgb(selectedColor);
      const targetHsl = rgbToHsl(target.r, target.g, target.b);
      for (let pixel = 0; pixel < selectedMask.length; pixel += 1) {
        if (!selectedMask[pixel]) continue;
        const index = pixel * 4;
        const sourceHsl = rgbToHsl(sourcePixels.data[index], sourcePixels.data[index + 1], sourcePixels.data[index + 2]);
        const adjustedLight = Math.max(0.04, Math.min(0.96, sourceHsl.l * 0.68 + targetHsl.l * 0.32));
        const colored = hslToRgb(targetHsl.h, targetHsl.s, adjustedLight);
        const strength = 0.82;
        output.data[index] = sourcePixels.data[index] * (1 - strength) + colored.r * strength;
        output.data[index + 1] = sourcePixels.data[index + 1] * (1 - strength) + colored.g * strength;
        output.data[index + 2] = sourcePixels.data[index + 2] * (1 - strength) + colored.b * strength;
      }
      context.putImageData(output, 0, 0);
    }

    function markConnectedRegion(startX, startY, record = true, sensitivity = Number(tolerance.value)) {
      if (!sourcePixels || !selectedMask || !selectedColor) {
        hint.hidden = false;
        hint.textContent = "Primero analiza la foto y elige un color recomendado";
        return;
      }
      const width = canvas.width;
      const height = canvas.height;
      const start = startY * width + startX;
      const startIndex = start * 4;
      const seedR = sourcePixels.data[startIndex];
      const seedG = sourcePixels.data[startIndex + 1];
      const seedB = sourcePixels.data[startIndex + 2];
      const limit = Number(sensitivity) ** 2;
      const visited = new Uint8Array(width * height);
      const queue = new Int32Array(width * height);
      let head = 0;
      let tail = 0;
      queue[tail++] = start;
      visited[start] = 1;
      const tryAdd = position => {
        if (position < 0 || position >= visited.length || visited[position]) return;
        visited[position] = 1;
        const index = position * 4;
        const red = sourcePixels.data[index] - seedR;
        const green = sourcePixels.data[index + 1] - seedG;
        const blue = sourcePixels.data[index + 2] - seedB;
        if (red * red * 0.3 + green * green * 0.59 + blue * blue * 0.11 <= limit) queue[tail++] = position;
      };
      while (head < tail) {
        const position = queue[head++];
        selectedMask[position] = 1;
        const x = position % width;
        if (x > 0) tryAdd(position - 1);
        if (x < width - 1) tryAdd(position + 1);
        if (position >= width) tryAdd(position - width);
        if (position < width * (height - 1)) tryAdd(position + width);
      }
      if (record) {
        marks.push({x: startX / width, y: startY / height, sensitivity: Number(sensitivity)});
        saveState();
      }
      reset.disabled = false;
      compare.disabled = false;
      download.disabled = false;
      hint.hidden = true;
      renderPreview();
    }

    async function decodePhoto(file) {
      if ("createImageBitmap" in window) return window.createImageBitmap(file, {imageOrientation: "from-image"});
      return new Promise((resolve, reject) => {
        const image = new Image();
        const url = URL.createObjectURL(file);
        image.onload = () => { URL.revokeObjectURL(url); resolve(image); };
        image.onerror = () => { URL.revokeObjectURL(url); reject(new Error("No se pudo abrir la fotografía.")); };
        image.src = url;
      });
    }

    async function loadPhoto(file, persist = true) {
      if (!file || !["image/jpeg", "image/png", "image/webp"].includes(file.type)) throw new Error("Selecciona una imagen JPG, PNG o WebP.");
      if (file.size > 4 * 1024 * 1024) throw new Error("La fotografía no puede superar 4 MB.");
      const image = await decodePhoto(file);
      const width = image.width || image.naturalWidth;
      const height = image.height || image.naturalHeight;
      if (width * height > 12_000_000) {
        if (image.close) image.close();
        throw new Error("La fotografía no puede superar 12 megapíxeles.");
      }
      const scale = Math.min(1, 1100 / width, 780 / height);
      canvas.width = Math.max(1, Math.round(width * scale));
      canvas.height = Math.max(1, Math.round(height * scale));
      context.drawImage(image, 0, 0, canvas.width, canvas.height);
      if (image.close) image.close();
      sourcePixels = context.getImageData(0, 0, canvas.width, canvas.height);
      selectedMask = new Uint8Array(canvas.width * canvas.height);
      photoFile = file;
      fileName.textContent = `${file.name} · ${(file.size / 1024 / 1024).toFixed(1)} MB`;
      workbench.hidden = false;
      emptyState.hidden = true;
      canvas.hidden = false;
      hint.hidden = false;
      hint.textContent = selectedColor ? "Haz clic en la pared que quieres pintar" : "Analiza la foto para recibir colores";
      analyze.disabled = false;
      if (persist) {
        marks = [];
        lastAnalysis = null;
        analysis.hidden = true;
        selectedColor = "";
        selectedProductId = null;
        selectedPaintName = "";
        imageDataUrl = canvas.toDataURL("image/jpeg", 0.78);
        saveState();
      }
    }

    function fillList(elementId, values, fallback) {
      const list = document.getElementById(elementId);
      list.replaceChildren();
      const items = Array.isArray(values) && values.length ? values : [fallback];
      items.forEach(value => {
        const item = document.createElement("li");
        item.textContent = value;
        list.appendChild(item);
      });
    }

    function selectPaint(paint) {
      if (!paint || !/^#[0-9A-Fa-f]{6}$/.test(String(paint.color_hex || ""))) return;
      selectedColor = paint.color_hex;
      selectedProductId = Number(paint.id) || null;
      selectedPaintName = paint.nombre || "Pintura SFI";
      selectedProduct.textContent = `${paint.color || "Color recomendado"} · ${selectedPaintName}`;
      document.querySelectorAll("[data-recommended-product]").forEach(button => button.classList.toggle("active", Number(button.dataset.recommendedProduct) === selectedProductId));
      const productLink = document.getElementById("paint-analysis-product");
      const url = safeUrl(paint.url);
      if (url) {
        productLink.href = url;
        productLink.hidden = false;
      }
      hint.hidden = false;
      hint.textContent = "Haz clic en la pared que quieres pintar";
      renderPreview();
      saveState();
    }

    function renderAnalysis(data, persist = true) {
      const result = data.analisis || {};
      analysis.hidden = false;
      document.getElementById("paint-analysis-title").textContent = result.superficie_detectada || "Superficie revisada";
      document.getElementById("paint-analysis-summary").textContent = result.resumen || "Revisa la preparación antes de pintar.";
      fillList("paint-analysis-observations", result.observaciones, "No se identificaron observaciones concluyentes.");
      fillList("paint-analysis-preparation", result.preparacion_sugerida, "Limpiar, secar y revisar antes de pintar.");
      const recommendedSection = document.getElementById("paint-recommended-colors");
      const recommendedList = document.getElementById("paint-recommended-color-list");
      recommendedList.replaceChildren();
      const recommendations = Array.isArray(data.colores_recomendados) ? data.colores_recomendados : [];
      recommendations.forEach(paint => {
        if (!/^#[0-9A-Fa-f]{6}$/.test(String(paint.color_hex || ""))) return;
        const button = document.createElement("button");
        button.type = "button";
        button.className = "paint-recommended-color";
        button.dataset.recommendedProduct = String(paint.id || "");
        const swatch = document.createElement("span");
        swatch.style.backgroundColor = paint.color_hex;
        const label = document.createElement("small");
        label.textContent = `${paint.color || "Color"} · ${paint.ambiente || ""}`;
        button.append(swatch, label);
        button.addEventListener("click", () => selectPaint(paint));
        recommendedList.appendChild(button);
      });
      recommendedSection.hidden = !recommendedList.children.length;
      lastAnalysis = data;
      if (!selectedProductId && recommendations.length) selectPaint(recommendations[0]);
      if (persist) saveState();
    }

    function showError(message) {
      analysis.hidden = false;
      document.getElementById("paint-analysis-title").textContent = "No fue posible completar el análisis";
      document.getElementById("paint-analysis-summary").textContent = message;
      document.getElementById("paint-analysis-observations").replaceChildren();
      document.getElementById("paint-analysis-preparation").replaceChildren();
      document.getElementById("paint-recommended-colors").hidden = true;
    }

    attach.addEventListener("click", () => { workbench.hidden = false; fileInput.click(); });
    document.querySelectorAll("[data-open-visualizer]").forEach(button => button.addEventListener("click", () => attach.click()));
    close.addEventListener("click", () => { workbench.hidden = true; });
    fileInput.addEventListener("change", async () => {
      const file = fileInput.files && fileInput.files[0];
      if (!file) return;
      try {
        await loadPhoto(file);
        workbench.scrollIntoView({behavior: "smooth", block: "nearest"});
      } catch (error) {
        showError(error.message || "No se pudo abrir la fotografía.");
      }
    });
    canvas.addEventListener("click", event => {
      if (!sourcePixels) return;
      const bounds = canvas.getBoundingClientRect();
      const x = Math.max(0, Math.min(canvas.width - 1, Math.floor((event.clientX - bounds.left) * canvas.width / bounds.width)));
      const y = Math.max(0, Math.min(canvas.height - 1, Math.floor((event.clientY - bounds.top) * canvas.height / bounds.height)));
      markConnectedRegion(x, y);
    });
    tolerance.addEventListener("input", () => { toleranceValue.textContent = tolerance.value; saveState(); });
    reset.addEventListener("click", () => {
      if (!sourcePixels) return;
      selectedMask = new Uint8Array(canvas.width * canvas.height);
      marks = [];
      renderPreview();
      reset.disabled = true;
      compare.disabled = true;
      download.disabled = true;
      hint.hidden = false;
      saveState();
    });
    const showOriginal = () => renderPreview(true);
    const showPreview = () => renderPreview(false);
    ["pointerdown", "touchstart"].forEach(type => compare.addEventListener(type, showOriginal, {passive: true}));
    ["pointerup", "pointerleave", "touchend", "touchcancel"].forEach(type => compare.addEventListener(type, showPreview, {passive: true}));
    download.addEventListener("click", () => {
      if (!sourcePixels) return;
      renderPreview();
      const link = document.createElement("a");
      link.download = `sfi-vista-previa-${selectedColor.replace("#", "")}.png`;
      link.href = canvas.toDataURL("image/png");
      link.click();
    });
    analyze.addEventListener("click", async () => {
      if (!photoFile || analyze.disabled) return;
      const original = analyze.innerHTML;
      analyze.disabled = true;
      analyze.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Analizando foto';
      const form = new FormData();
      form.append("imagen", photoFile);
      form.append("color_hex", selectedColor || "#FFFFFF");
      if (selectedProductId) form.append("producto_id", String(selectedProductId));
      try {
        const response = await fetch(root.dataset.photoApiUrl, {method: "POST", credentials: "same-origin", headers: {Accept: "application/json", "X-CSRFToken": getCookie("csrftoken")}, body: form});
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(firstError(data) || "No fue posible analizar la fotografía.");
        renderAnalysis(data);
      } catch (error) {
        showError(error.message || "No fue posible analizar la fotografía.");
      } finally {
        analyze.disabled = false;
        analyze.innerHTML = original;
      }
    });

    async function restoreState() {
      let stored;
      try { stored = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || "null"); } catch (_error) { return; }
      if (!stored || !stored.imageDataUrl) return;
      try {
        const blob = await fetch(stored.imageDataUrl).then(response => response.blob());
        const restoredFile = new File([blob], stored.fileName || "foto-sfi.jpg", {type: blob.type || "image/jpeg"});
        imageDataUrl = stored.imageDataUrl;
        selectedColor = stored.selectedColor || "";
        selectedProductId = Number(stored.selectedProductId) || null;
        selectedPaintName = stored.selectedPaintName || "";
        marks = Array.isArray(stored.marks) ? stored.marks : [];
        lastAnalysis = stored.analysis || null;
        tolerance.value = Number(stored.tolerance) || 55;
        toleranceValue.textContent = tolerance.value;
        await loadPhoto(restoredFile, false);
        if (lastAnalysis) renderAnalysis(lastAnalysis, false);
        const restoredPaint = lastAnalysis && Array.isArray(lastAnalysis.colores_recomendados)
          ? lastAnalysis.colores_recomendados.find(paint => Number(paint.id) === selectedProductId)
          : null;
        if (restoredPaint) selectPaint(restoredPaint);
        else if (selectedPaintName) selectedProduct.textContent = selectedPaintName;
        const savedMarks = [...marks];
        marks = [];
        savedMarks.forEach(mark => markConnectedRegion(Math.min(canvas.width - 1, Math.round(mark.x * canvas.width)), Math.min(canvas.height - 1, Math.round(mark.y * canvas.height)), false, mark.sensitivity));
        marks = savedMarks;
        workbench.hidden = false;
      } catch (_error) {
        clearState();
      }
    }

    document.getElementById("clear-chat").addEventListener("click", () => { clearState(); workbench.hidden = true; });
    restoreState();
  });
})();
