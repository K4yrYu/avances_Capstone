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
    const brushSize = document.getElementById("paint-brush-size");
    const brushSizeValue = document.getElementById("paint-brush-size-value");
    const maskPreview = document.getElementById("toggle-paint-mask");
    const maskToolButtons = Array.from(document.querySelectorAll("[data-mask-tool]"));
    const autoPaint = document.getElementById("auto-paint-surface");
    const applyPaint = document.getElementById("apply-paint-mask");
    const selectedProduct = document.getElementById("selected-paint-product");
    const reset = document.getElementById("reset-paint-mask");
    const compare = document.getElementById("compare-original");
    const download = document.getElementById("download-paint-preview");
    const analyze = document.getElementById("analyze-paint-photo");
    const analysis = document.getElementById("paint-analysis");
    const generalFlow = document.getElementById("general-chat-flow");
    const miniChat = document.getElementById("paint-mini-chat");
    const photoChatMessages = document.getElementById("paint-chat-messages");
    const photoChatForm = document.getElementById("paint-chat-form");
    const photoChatInput = document.getElementById("paint-chat-input");
    const photoChatSend = document.getElementById("paint-chat-send");
    const photoChatError = document.getElementById("paint-chat-error");
    const security = window.FerremasSecurity;
    if (!root || !workbench || !canvas || !fileInput || !security) return;

    const userKey = root.dataset.userKey || "guest";
    const STORAGE_KEY = `sfi_paint_assistant_v2:${userKey}`;
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
    let photoHistory = [];
    let recommendedPaints = new Map();
    let lastChatProducts = [];
    let activeMaskTool = "smart";
    let showMask = false;
    let showingOriginal = false;
    let drawingMask = false;

    function setPhotoMode(active) {
      workbench.hidden = !active;
      if (generalFlow) generalFlow.hidden = active;
      root.classList.toggle("photo-mode", active);
    }

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
          photoHistory: photoHistory.slice(-6),
          recommendedPaints: Array.from(recommendedPaints.values()),
          lastChatProducts,
          tolerance: Number(tolerance.value),
          brushSize: Number(brushSize.value),
          showMask,
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
      photoHistory = [];
      recommendedPaints = new Map();
      lastChatProducts = [];
      fileInput.value = "";
      canvas.hidden = true;
      emptyState.hidden = false;
      hint.hidden = true;
      analysis.hidden = true;
      miniChat.hidden = true;
      photoChatMessages.replaceChildren();
      photoChatInput.value = "";
      photoChatError.hidden = true;
      fileName.textContent = "JPG, PNG o WebP · máximo 4 MB";
      selectedProduct.textContent = "Analiza la foto para recibir colores recomendados.";
      analyze.disabled = true;
      reset.disabled = true;
      compare.disabled = true;
      download.disabled = true;
      maskPreview.disabled = true;
      showMask = false;
      showingOriginal = false;
      maskPreview.classList.remove("active");
      maskPreview.setAttribute("aria-pressed", "false");
      autoPaint.disabled = true;
      applyPaint.disabled = true;
      compare.classList.remove("active");
      compare.setAttribute("aria-pressed", "false");
      compare.innerHTML = '<i class="fa-solid fa-eye"></i> Ver antes';
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

    function renderPreview(showOriginal = showingOriginal) {
      if (!sourcePixels) return;
      if (showOriginal || !selectedMask || (!selectedColor && !showMask)) {
        context.putImageData(sourcePixels, 0, 0);
        return;
      }
      const output = new ImageData(new Uint8ClampedArray(sourcePixels.data), canvas.width, canvas.height);
      const target = hexToRgb(selectedColor);
      const targetHsl = rgbToHsl(target.r, target.g, target.b);
      for (let pixel = 0; pixel < selectedMask.length; pixel += 1) {
        if (!selectedMask[pixel]) continue;
        const index = pixel * 4;
        if (showMask) {
          output.data[index] = sourcePixels.data[index] * 0.45 + 255 * 0.55;
          output.data[index + 1] = sourcePixels.data[index + 1] * 0.45 + 189 * 0.55;
          output.data[index + 2] = sourcePixels.data[index + 2] * 0.45;
          continue;
        }
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

    function updateAutoPaintButton() {
      autoPaint.disabled = !(sourcePixels && selectedColor && lastAnalysis);
    }

    function pixelDistance(firstIndex, secondIndex) {
      const red = sourcePixels.data[firstIndex] - sourcePixels.data[secondIndex];
      const green = sourcePixels.data[firstIndex + 1] - sourcePixels.data[secondIndex + 1];
      const blue = sourcePixels.data[firstIndex + 2] - sourcePixels.data[secondIndex + 2];
      return red * red * 0.3 + green * green * 0.59 + blue * blue * 0.11;
    }

    function autoDetectSurface(record = true) {
      if (!sourcePixels || !selectedColor || !lastAnalysis) return;
      const width = canvas.width;
      const height = canvas.height;
      const total = width * height;
      const candidates = new Uint8Array(total);
      const visited = new Uint8Array(total);
      const minX = Math.floor(width * 0.035);
      const maxX = Math.ceil(width * 0.965);
      const minY = Math.floor(height * 0.12);
      const maxY = Math.ceil(height * 0.86);

      for (let y = minY; y < maxY; y += 1) {
        for (let x = minX; x < maxX; x += 1) {
          const position = y * width + x;
          const index = position * 4;
          const hsl = rgbToHsl(sourcePixels.data[index], sourcePixels.data[index + 1], sourcePixels.data[index + 2]);
          if (hsl.l < 0.2 || hsl.l > 0.95) continue;
          const likelyVegetation = hsl.h > 0.18 && hsl.h < 0.48 && hsl.s > 0.2;
          const likelySky = hsl.h > 0.5 && hsl.h < 0.72 && hsl.s > 0.16 && y < height * 0.58;
          if (likelyVegetation || likelySky) continue;
          const rightIndex = (position + Math.min(2, maxX - x - 1)) * 4;
          const downIndex = (position + Math.min(2, maxY - y - 1) * width) * 4;
          if (pixelDistance(index, rightIndex) > 1450 || pixelDistance(index, downIndex) > 1450) continue;
          candidates[position] = 1;
        }
      }

      const components = [];
      const queue = new Int32Array(total);
      for (let start = 0; start < total; start += 1) {
        if (!candidates[start] || visited[start]) continue;
        let head = 0;
        let tail = 0;
        let sumX = 0;
        let sumY = 0;
        const pixels = [];
        queue[tail++] = start;
        visited[start] = 1;
        while (head < tail) {
          const position = queue[head++];
          const x = position % width;
          const y = Math.floor(position / width);
          pixels.push(position);
          sumX += x;
          sumY += y;
          const neighbours = [x > 0 ? position - 1 : -1, x < width - 1 ? position + 1 : -1, y > 0 ? position - width : -1, y < height - 1 ? position + width : -1];
          neighbours.forEach(next => {
            if (next >= 0 && candidates[next] && !visited[next]) {
              visited[next] = 1;
              queue[tail++] = next;
            }
          });
        }
        if (pixels.length < total * 0.0025) continue;
        const centerX = sumX / pixels.length / width;
        const centerY = sumY / pixels.length / height;
        const centerWeight = Math.max(0.25, 1.25 - Math.abs(centerX - 0.5) * 1.4);
        const verticalWeight = centerY > 0.22 && centerY < 0.78 ? 1 : 0.55;
        components.push({pixels, score: pixels.length * centerWeight * verticalWeight});
      }

      selectedMask = new Uint8Array(total);
      components.sort((first, second) => second.score - first.score);
      const bestScore = components.length ? components[0].score : 0;
      let selectedCount = 0;
      components.slice(0, 5).forEach(component => {
        if (component.score < bestScore * 0.22 || selectedCount + component.pixels.length > total * 0.55) return;
        component.pixels.forEach(position => { selectedMask[position] = 1; });
        selectedCount += component.pixels.length;
      });

      if (!selectedCount) {
        hint.hidden = false;
        hint.textContent = "No se detectó una superficie clara. Usa Selección o Añadir.";
        renderPreview();
        return;
      }
      if (record) marks = [{mode: "auto"}];
      showMask = true;
      maskPreview.disabled = false;
      maskPreview.classList.add("active");
      maskPreview.setAttribute("aria-pressed", "true");
      maskPreview.innerHTML = '<i class="fa-solid fa-eye-slash"></i> Ocultar selección';
      reset.disabled = false;
      compare.disabled = false;
      download.disabled = false;
      applyPaint.disabled = false;
      hint.hidden = false;
      hint.textContent = "Revisa la selección amarilla y corrige con Añadir o Borrar";
      renderPreview();
      if (record) saveState();
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
      const tryAdd = (position, fromPosition) => {
        if (position < 0 || position >= visited.length || visited[position]) return;
        visited[position] = 1;
        const index = position * 4;
        const fromIndex = fromPosition * 4;
        const red = sourcePixels.data[index] - seedR;
        const green = sourcePixels.data[index + 1] - seedG;
        const blue = sourcePixels.data[index + 2] - seedB;
        const localRed = sourcePixels.data[index] - sourcePixels.data[fromIndex];
        const localGreen = sourcePixels.data[index + 1] - sourcePixels.data[fromIndex + 1];
        const localBlue = sourcePixels.data[index + 2] - sourcePixels.data[fromIndex + 2];
        const seedDistance = red * red * 0.3 + green * green * 0.59 + blue * blue * 0.11;
        const localDistance = localRed * localRed * 0.3 + localGreen * localGreen * 0.59 + localBlue * localBlue * 0.11;
        if (seedDistance <= limit && localDistance <= limit * 0.38) queue[tail++] = position;
      };
      while (head < tail) {
        const position = queue[head++];
        selectedMask[position] = 1;
        const x = position % width;
        if (x > 0) tryAdd(position - 1, position);
        if (x < width - 1) tryAdd(position + 1, position);
        if (position >= width) tryAdd(position - width, position);
        if (position < width * (height - 1)) tryAdd(position + width, position);
      }
      if (record) {
        marks.push({x: startX / width, y: startY / height, sensitivity: Number(sensitivity)});
        saveState();
      }
      reset.disabled = false;
      compare.disabled = false;
      download.disabled = false;
      maskPreview.disabled = false;
      applyPaint.disabled = false;
      hint.hidden = true;
      renderPreview();
    }

    function paintMaskCircle(centerX, centerY, mode, radius = Number(brushSize.value), record = true) {
      if (!selectedMask || !sourcePixels) return;
      const scaledRadius = Math.max(2, Math.round(radius * canvas.width / Math.max(1, canvas.clientWidth)));
      const minX = Math.max(0, centerX - scaledRadius);
      const maxX = Math.min(canvas.width - 1, centerX + scaledRadius);
      const minY = Math.max(0, centerY - scaledRadius);
      const maxY = Math.min(canvas.height - 1, centerY + scaledRadius);
      const value = mode === "erase" ? 0 : 1;
      for (let y = minY; y <= maxY; y += 1) {
        for (let x = minX; x <= maxX; x += 1) {
          if ((x - centerX) ** 2 + (y - centerY) ** 2 <= scaledRadius ** 2) selectedMask[y * canvas.width + x] = value;
        }
      }
      if (record) {
        marks.push({mode, x: centerX / canvas.width, y: centerY / canvas.height, radius: Number(radius)});
        if (marks.length > 1200) marks = marks.slice(-1200);
      }
      reset.disabled = false;
      compare.disabled = false;
      download.disabled = false;
      maskPreview.disabled = false;
      applyPaint.disabled = false;
      hint.hidden = true;
      renderPreview();
    }

    function canvasPoint(event) {
      const bounds = canvas.getBoundingClientRect();
      return {
        x: Math.max(0, Math.min(canvas.width - 1, Math.floor((event.clientX - bounds.left) * canvas.width / bounds.width))),
        y: Math.max(0, Math.min(canvas.height - 1, Math.floor((event.clientY - bounds.top) * canvas.height / bounds.height))),
      };
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
      reset.disabled = true;
      compare.disabled = true;
      download.disabled = true;
      maskPreview.disabled = true;
      applyPaint.disabled = true;
      showMask = false;
      showingOriginal = false;
      compare.classList.remove("active");
      compare.setAttribute("aria-pressed", "false");
      compare.innerHTML = '<i class="fa-solid fa-eye"></i> Ver antes';
      maskPreview.classList.remove("active");
      maskPreview.setAttribute("aria-pressed", "false");
      if (persist) {
        marks = [];
        lastAnalysis = null;
        photoHistory = [];
        recommendedPaints = new Map();
        lastChatProducts = [];
        analysis.hidden = true;
        miniChat.hidden = true;
        photoChatMessages.replaceChildren();
        photoChatError.hidden = true;
        selectedColor = "";
        selectedProductId = null;
        selectedPaintName = "";
        imageDataUrl = canvas.toDataURL("image/jpeg", 0.78);
        saveState();
      }
      updateAutoPaintButton();
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
      updateAutoPaintButton();
      saveState();
    }

    function renderRecommendations(recommendations, resetList = false) {
      const recommendedSection = document.getElementById("paint-recommended-colors");
      const recommendedList = document.getElementById("paint-recommended-color-list");
      if (resetList) recommendedPaints = new Map();
      recommendations.forEach(paint => {
        const productId = Number(paint && paint.id);
        if (productId && /^#[0-9A-Fa-f]{6}$/.test(String(paint.color_hex || ""))) {
          recommendedPaints.set(productId, paint);
        }
      });
      recommendedList.replaceChildren();
      recommendedPaints.forEach(paint => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "paint-recommended-color";
        button.dataset.recommendedProduct = String(paint.id || "");
        if (Number(paint.id) === selectedProductId) button.classList.add("active");
        const swatch = document.createElement("span");
        swatch.style.backgroundColor = paint.color_hex;
        const label = document.createElement("small");
        label.textContent = `${paint.color || "Color"} · ${paint.ambiente || ""}`;
        button.append(swatch, label);
        button.addEventListener("click", () => selectPaint(paint));
        recommendedList.appendChild(button);
      });
      recommendedSection.hidden = !recommendedList.children.length;
    }

    function renderAnalysis(data, persist = true) {
      const result = data.analisis || {};
      analysis.hidden = false;
      document.getElementById("paint-analysis-title").textContent = result.superficie_detectada || "Superficie revisada";
      document.getElementById("paint-analysis-summary").textContent = result.resumen || "Revisa la preparación antes de pintar.";
      fillList("paint-analysis-observations", result.observaciones, "No se identificaron observaciones concluyentes.");
      fillList("paint-analysis-preparation", result.preparacion_sugerida, "Limpiar, secar y revisar antes de pintar.");
      const recommendations = Array.isArray(data.colores_recomendados) ? data.colores_recomendados : [];
      renderRecommendations(recommendations, true);
      lastAnalysis = data;
      selectedProduct.textContent = recommendations.length
        ? "Selecciona un color y usa el chat para calcular cantidades y costos."
        : "Usa el chat para indicar el color, las medidas y las condiciones del proyecto.";
      miniChat.hidden = !["interior", "exterior", "piscina", "no_determinado"].includes(data.contexto_pintura);
      if (!miniChat.hidden && !photoHistory.length) {
        const contexto = data.contexto_pintura;
        const contextoTexto = contexto === "no_determinado" ? "cuyo ambiente no se pudo determinar" : contexto;
        const greeting = `¡Listo! La fotografía parece corresponder a un proyecto ${contextoTexto}. Si quieres probar un tono, dime algo como “quiero verla en azul claro”. Solo te pediré medidas y condiciones si necesitas calcular cuánto comprar o cuánto costaría.`;
        addPhotoChatMessage("assistant", greeting);
        photoHistory = [{role: "assistant", content: greeting}];
      }
      if (persist) saveState();
      updateAutoPaintButton();
    }

    function addPhotoChatMessage(role, text) {
      const message = document.createElement("p");
      message.className = `paint-chat-message ${role}`;
      message.textContent = text;
      photoChatMessages.appendChild(message);
      photoChatMessages.scrollTop = photoChatMessages.scrollHeight;
    }

    function formatPrice(value) {
      return new Intl.NumberFormat("es-CL", {style: "currency", currency: "CLP", maximumFractionDigits: 0}).format(Number(value) || 0);
    }

    function renderPhotoProducts(products) {
      if (!products.length) return;
      const list = document.createElement("div");
      list.className = "paint-chat-products";
      products.forEach(paint => {
        const card = document.createElement("article");
        card.className = "paint-chat-product";
        const swatch = document.createElement("span");
        swatch.className = "paint-chat-product-swatch";
        swatch.style.backgroundColor = /^#[0-9A-Fa-f]{6}$/.test(String(paint.color_hex || "")) ? paint.color_hex : "#ffffff";
        const content = document.createElement("div");
        const title = document.createElement("strong");
        title.textContent = paint.nombre || "Pintura SFI";
        const detail = document.createElement("span");
        detail.textContent = [paint.color, paint.terminacion, paint.presentacion].filter(Boolean).join(" · ");
        const calculation = document.createElement("span");
        calculation.className = "paint-chat-product-calculation";
        calculation.textContent = paint.cantidad_envases
          ? `Necesitas ${paint.cantidad_envases} envase(s) · ${paint.litros_necesarios} L · Total ${formatPrice(paint.presupuesto_total)}`
          : `Precio ${formatPrice(paint.precio)} · Stock ${paint.stock}`;
        content.append(title, detail, calculation);
        const actions = document.createElement("div");
        actions.className = "paint-chat-product-actions";
        if (/^#[0-9A-Fa-f]{6}$/.test(String(paint.color_hex || ""))) {
          const select = document.createElement("button");
          select.type = "button";
          select.textContent = "Probar en foto";
          select.addEventListener("click", () => selectPaint(paint));
          actions.appendChild(select);
        }
        const url = safeUrl(paint.url);
        if (url) {
          const link = document.createElement("a");
          link.href = url;
          link.textContent = "Ver producto";
          actions.appendChild(link);
        }
        card.append(swatch, content, actions);
        list.appendChild(card);
      });
      photoChatMessages.appendChild(list);
      photoChatMessages.scrollTop = photoChatMessages.scrollHeight;
    }

    function showError(message) {
      analysis.hidden = false;
      document.getElementById("paint-analysis-title").textContent = "No fue posible completar el análisis";
      document.getElementById("paint-analysis-summary").textContent = message;
      document.getElementById("paint-analysis-observations").replaceChildren();
      document.getElementById("paint-analysis-preparation").replaceChildren();
      document.getElementById("paint-recommended-colors").hidden = true;
    }

    attach.addEventListener("click", () => { setPhotoMode(true); fileInput.click(); });
    document.querySelectorAll("[data-open-visualizer]").forEach(button => button.addEventListener("click", () => attach.click()));
    close.addEventListener("click", () => { setPhotoMode(false); });
    fileInput.addEventListener("change", async () => {
      const file = fileInput.files && fileInput.files[0];
      if (!file) return;
      try {
        setPhotoMode(true);
        await loadPhoto(file);
        workbench.scrollIntoView({behavior: "smooth", block: "nearest"});
      } catch (error) {
        showError(error.message || "No se pudo abrir la fotografía.");
      }
    });
    function selectMaskTool(tool) {
      activeMaskTool = ["smart", "brush", "erase"].includes(tool) ? tool : "smart";
      maskToolButtons.forEach(button => {
        const active = button.dataset.maskTool === activeMaskTool;
        button.classList.toggle("active", active);
        button.setAttribute("aria-pressed", String(active));
      });
      canvas.dataset.maskTool = activeMaskTool;
    }

    maskToolButtons.forEach(button => button.addEventListener("click", () => selectMaskTool(button.dataset.maskTool)));
    autoPaint.addEventListener("click", () => autoDetectSurface());
    applyPaint.addEventListener("click", () => {
      if (!sourcePixels || !selectedMask || !selectedColor || applyPaint.disabled) return;
      showMask = false;
      maskPreview.classList.remove("active");
      maskPreview.setAttribute("aria-pressed", "false");
      maskPreview.innerHTML = '<i class="fa-solid fa-highlighter"></i> Ver selección';
      hint.hidden = false;
      hint.textContent = "Pintura aplicada en las zonas marcadas";
      renderPreview();
      saveState();
    });
    brushSize.addEventListener("input", () => {
      brushSizeValue.textContent = brushSize.value;
      saveState();
    });
    maskPreview.addEventListener("click", () => {
      showMask = !showMask;
      maskPreview.classList.toggle("active", showMask);
      maskPreview.setAttribute("aria-pressed", String(showMask));
      maskPreview.innerHTML = showMask
        ? '<i class="fa-solid fa-eye-slash"></i> Ocultar selección'
        : '<i class="fa-solid fa-highlighter"></i> Ver selección';
      renderPreview();
    });
    canvas.addEventListener("pointerdown", event => {
      if (!sourcePixels || !selectedColor) return;
      const point = canvasPoint(event);
      if (activeMaskTool === "smart") {
        markConnectedRegion(point.x, point.y);
        return;
      }
      drawingMask = true;
      canvas.setPointerCapture(event.pointerId);
      paintMaskCircle(point.x, point.y, activeMaskTool);
    });
    canvas.addEventListener("pointermove", event => {
      if (!drawingMask || activeMaskTool === "smart") return;
      const point = canvasPoint(event);
      paintMaskCircle(point.x, point.y, activeMaskTool);
    });
    const finishMaskStroke = event => {
      if (!drawingMask) return;
      drawingMask = false;
      if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
      saveState();
    };
    canvas.addEventListener("pointerup", finishMaskStroke);
    canvas.addEventListener("pointercancel", finishMaskStroke);
    tolerance.addEventListener("input", () => { toleranceValue.textContent = tolerance.value; saveState(); });
    reset.addEventListener("click", () => {
      if (!sourcePixels) return;
      selectedMask = new Uint8Array(canvas.width * canvas.height);
      marks = [];
      renderPreview();
      reset.disabled = true;
      compare.disabled = true;
      download.disabled = true;
      maskPreview.disabled = true;
      applyPaint.disabled = true;
      showMask = false;
      maskPreview.classList.remove("active");
      maskPreview.setAttribute("aria-pressed", "false");
      maskPreview.innerHTML = '<i class="fa-solid fa-highlighter"></i> Ver selección';
      hint.hidden = false;
      saveState();
    });
    compare.addEventListener("click", () => {
      showingOriginal = !showingOriginal;
      compare.classList.toggle("active", showingOriginal);
      compare.setAttribute("aria-pressed", String(showingOriginal));
      compare.innerHTML = showingOriginal
        ? '<i class="fa-solid fa-eye-slash"></i> Ver resultado'
        : '<i class="fa-solid fa-eye"></i> Ver antes';
      renderPreview(showingOriginal);
    });
    download.addEventListener("click", () => {
      if (!sourcePixels) return;
      renderPreview(false);
      const link = document.createElement("a");
      link.download = `sfi-vista-previa-${selectedColor.replace("#", "")}.png`;
      link.href = canvas.toDataURL("image/png");
      link.click();
      if (showingOriginal) renderPreview(true);
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

    photoChatForm.addEventListener("submit", async event => {
      event.preventDefault();
      const message = photoChatInput.value.trim();
      const contexto = lastAnalysis && lastAnalysis.contexto_pintura;
      if (message.length < 2 || !["interior", "exterior", "piscina", "no_determinado"].includes(contexto)) return;
      const historyForRequest = photoHistory.slice(-6);
      addPhotoChatMessage("user", message);
      photoHistory.push({role: "user", content: message});
      photoChatInput.value = "";
      photoChatSend.disabled = true;
      photoChatError.hidden = true;
      try {
        const response = await fetch(root.dataset.photoChatApiUrl, {
          method: "POST",
          credentials: "same-origin",
          headers: {"Content-Type": "application/json", Accept: "application/json", "X-CSRFToken": getCookie("csrftoken")},
          body: JSON.stringify({mensaje: message, contexto, historial: historyForRequest, ...(selectedProductId ? {producto_id: selectedProductId} : {})}),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(firstError(data) || "No fue posible configurar la fotografía.");
        const answer = data.mensaje || "Revisa las pinturas disponibles para este color.";
        addPhotoChatMessage("assistant", answer);
        photoHistory.push({role: "assistant", content: answer.slice(0, 700)});
        photoHistory = photoHistory.slice(-6);
        const recommendations = Array.isArray(data.productos) ? data.productos : [];
        renderRecommendations(recommendations);
        renderPhotoProducts(recommendations);
        lastChatProducts = recommendations;
        saveState();
      } catch (error) {
        photoChatError.textContent = error.message || "No fue posible configurar la fotografía.";
        photoChatError.hidden = false;
      } finally {
        photoChatSend.disabled = false;
        photoChatInput.focus();
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
        const restoredShowMask = Boolean(stored.showMask);
        selectedColor = stored.selectedColor || "";
        selectedProductId = Number(stored.selectedProductId) || null;
        selectedPaintName = stored.selectedPaintName || "";
        marks = Array.isArray(stored.marks) ? stored.marks : [];
        lastAnalysis = stored.analysis || null;
        photoHistory = Array.isArray(stored.photoHistory) ? stored.photoHistory.slice(-6) : [];
        const storedRecommendations = Array.isArray(stored.recommendedPaints) ? stored.recommendedPaints : [];
        recommendedPaints = new Map(storedRecommendations.map(paint => [Number(paint.id), paint]));
        lastChatProducts = Array.isArray(stored.lastChatProducts) ? stored.lastChatProducts : [];
        tolerance.value = Number(stored.tolerance) || 55;
        toleranceValue.textContent = tolerance.value;
        brushSize.value = Number(stored.brushSize) || 24;
        brushSizeValue.textContent = brushSize.value;
        await loadPhoto(restoredFile, false);
        if (lastAnalysis) renderAnalysis(lastAnalysis, false);
        renderRecommendations(storedRecommendations);
        photoChatMessages.replaceChildren();
        photoHistory.forEach(entry => addPhotoChatMessage(entry.role, entry.content));
        renderPhotoProducts(lastChatProducts);
        const restoredPaint = recommendedPaints.get(selectedProductId) || null;
        if (restoredPaint) selectPaint(restoredPaint);
        else if (selectedPaintName) selectedProduct.textContent = selectedPaintName;
        const savedMarks = [...marks];
        marks = [];
        savedMarks.forEach(mark => {
          if (mark.mode === "auto") {
            autoDetectSurface(false);
            return;
          }
          const x = Math.min(canvas.width - 1, Math.round(mark.x * canvas.width));
          const y = Math.min(canvas.height - 1, Math.round(mark.y * canvas.height));
          if (mark.mode === "brush" || mark.mode === "erase") paintMaskCircle(x, y, mark.mode, mark.radius, false);
          else markConnectedRegion(x, y, false, mark.sensitivity);
        });
        marks = savedMarks;
        showMask = restoredShowMask;
        maskPreview.classList.toggle("active", showMask);
        maskPreview.setAttribute("aria-pressed", String(showMask));
        maskPreview.innerHTML = showMask
          ? '<i class="fa-solid fa-eye-slash"></i> Ocultar selección'
          : '<i class="fa-solid fa-highlighter"></i> Ver selección';
        renderPreview();
        setPhotoMode(true);
      } catch (_error) {
        clearState();
        setPhotoMode(false);
      }
    }

    document.getElementById("clear-chat").addEventListener("click", () => { clearState(); setPhotoMode(false); });
    selectMaskTool("smart");
    setPhotoMode(false);
    restoreState();
  });
})();
