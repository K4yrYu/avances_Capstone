(() => {
  "use strict";

  document.addEventListener("DOMContentLoaded", () => {
    const root = document.getElementById("chat-sfi");
    const form = document.getElementById("assistant-form");
    const input = document.getElementById("assistant-message");
    const messages = document.getElementById("chat-messages");
    const suggestions = document.getElementById("chat-suggestions");
    const errorBox = document.getElementById("chat-error");
    const submit = document.getElementById("send-assistant-message");
    const clear = document.getElementById("clear-chat");
    const readConversation = document.getElementById("read-conversation");
    const security = window.FerremasSecurity;
    if (!root || !form || !input || !messages || !security) return;

    const {escapeHtml, safeUrl} = security;
    const fallbackImage = safeUrl(root.dataset.placeholderUrl);
    const fallbackMasterImage = safeUrl(root.dataset.masterPlaceholderUrl) || fallbackImage;
    const authenticated = root.dataset.authenticated === "true";
    const userKey = root.dataset.userKey || "guest";
    const sessionOwnerKey = "sfi_assistant_session_owner_v1";
    const conversationStorageKey = `sfi_assistant_conversation_v2:${userKey}`;
    const previousOwner = sessionStorage.getItem(sessionOwnerKey);
    if (previousOwner && previousOwner !== userKey) {
      Object.keys(sessionStorage).forEach(key => {
        if (key.startsWith("sfi_assistant_conversation_") || key.startsWith("sfi_paint_assistant_")) {
          sessionStorage.removeItem(key);
        }
      });
    }
    sessionStorage.setItem(sessionOwnerKey, userKey);
    let history = [];
    let conversationEntries = [];
    let calculations = new Map();
    let cartItems = new Map();
    const speechSupported = "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
    let speechGeneration = 0;
    let activeSpeechButton = null;

    function saveConversation() {
      try {
        sessionStorage.setItem(
          conversationStorageKey,
          JSON.stringify({entries: conversationEntries.slice(-24)}),
        );
      } catch (_error) {
        // El asistente sigue funcionando aunque el navegador bloquee el almacenamiento.
      }
    }

    function rememberMessage(role, text, products = [], masters = []) {
      conversationEntries.push({
        role,
        text: String(text || "").slice(0, 1400),
        products: Array.isArray(products) ? products.slice(0, 8) : [],
        masters: Array.isArray(masters) ? masters.slice(0, 5) : [],
      });
      conversationEntries = conversationEntries.slice(-24);
      saveConversation();
    }

    function contextProductIds() {
      const lastResult = [...conversationEntries].reverse().find(entry =>
        entry.role === "assistant" && Array.isArray(entry.products) && entry.products.length
      );
      if (!lastResult) return [];
      return [...new Set(lastResult.products.map(product => Number(product.id)).filter(id => Number.isInteger(id) && id > 0))].slice(0, 8);
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

    function formatClp(value) {
      return new Intl.NumberFormat("es-CL", {style: "currency", currency: "CLP", maximumFractionDigits: 0}).format(Number(value) || 0);
    }

    function scrollToLatest() {
      messages.scrollTo({top: messages.scrollHeight, behavior: "smooth"});
    }

    function setSpeechButtonState(button, active) {
      if (!button) return;
      const icon = button.querySelector("i");
      const label = button.querySelector("span");
      button.classList.toggle("speaking", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
      const description = active
        ? "Detener lectura"
        : button.id === "read-conversation"
          ? "Leer conversación completa"
          : "Leer mensaje de SFI";
      button.setAttribute("aria-label", description);
      button.title = description;
      if (icon) {
        icon.className = active ? "fa-solid fa-stop" : "fa-solid fa-volume-high";
      }
      if (label && button.id === "read-conversation") {
        label.textContent = active ? "Detener lectura" : "Leer conversación";
      }
    }

    function stopSpeech() {
      speechGeneration += 1;
      window.speechSynthesis?.cancel();
      setSpeechButtonState(activeSpeechButton, false);
      activeSpeechButton = null;
    }

    function speechChunks(text) {
      const clean = String(text || "").replace(/\s+/g, " ").trim();
      if (!clean) return [];
      const sentences = clean.match(/[^.!?]+[.!?]?/g) || [clean];
      const chunks = [];
      let current = "";
      sentences.forEach(sentence => {
        const next = `${current} ${sentence.trim()}`.trim();
        if (current && next.length > 700) {
          chunks.push(current);
          current = sentence.trim();
        } else {
          current = next;
        }
      });
      if (current) chunks.push(current);
      return chunks;
    }

    function preferredSpanishVoice() {
      const voices = window.speechSynthesis?.getVoices?.() || [];
      return voices.find(voice => voice.lang.toLowerCase() === "es-cl")
        || voices.find(voice => voice.lang.toLowerCase().startsWith("es"))
        || null;
    }

    function startSpeech(texts, button) {
      if (!speechSupported) return;
      if (activeSpeechButton === button) {
        stopSpeech();
        return;
      }
      stopSpeech();
      const queue = texts.flatMap(speechChunks);
      if (!queue.length) return;

      const generation = speechGeneration;
      activeSpeechButton = button;
      setSpeechButtonState(button, true);
      let index = 0;

      const speakNext = () => {
        if (generation !== speechGeneration) return;
        if (index >= queue.length) {
          setSpeechButtonState(activeSpeechButton, false);
          activeSpeechButton = null;
          return;
        }
        const utterance = new SpeechSynthesisUtterance(queue[index]);
        index += 1;
        utterance.lang = "es-CL";
        utterance.rate = 1;
        const voice = preferredSpanishVoice();
        if (voice) utterance.voice = voice;
        utterance.addEventListener("end", speakNext, {once: true});
        utterance.addEventListener("error", () => {
          if (generation !== speechGeneration) return;
          setSpeechButtonState(activeSpeechButton, false);
          activeSpeechButton = null;
        }, {once: true});
        window.speechSynthesis.speak(utterance);
      };
      speakNext();
    }

    function attachMessageSpeechButton(article, paragraph) {
      if (!speechSupported || !paragraph?.textContent.trim()) return;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "message-speech-button";
      button.setAttribute("aria-label", "Leer mensaje de SFI");
      button.setAttribute("aria-pressed", "false");
      button.title = "Leer mensaje de SFI";
      button.innerHTML = '<i class="fa-solid fa-volume-high" aria-hidden="true"></i>';
      button.addEventListener("click", () => startSpeech([paragraph.textContent], button));
      article.querySelector(".message-content")?.appendChild(button);
    }

    function addMessage(role, text) {
      const article = document.createElement("article");
      article.className = `chat-message ${role === "user" ? "user-message" : "assistant-message"}`;
      const avatar = document.createElement("span");
      avatar.className = "message-avatar";
      const icon = document.createElement("i");
      icon.className = role === "user" ? "fa-solid fa-user" : "fa-solid fa-robot";
      avatar.appendChild(icon);
      const content = document.createElement("div");
      content.className = "message-content";
      const paragraph = document.createElement("p");
      paragraph.textContent = text;
      content.appendChild(paragraph);
      article.append(avatar, content);
      if (role === "assistant") attachMessageSpeechButton(article, paragraph);
      messages.appendChild(article);
      scrollToLatest();
      return article;
    }

    function addTyping() {
      const article = addMessage("assistant", "");
      article.dataset.typing = "true";
      article.querySelector(".message-content").innerHTML = '<span class="typing-dots" aria-label="SFI está respondiendo"><i></i><i></i><i></i></span>';
      return article;
    }

    function renderProducts(products) {
      if (!Array.isArray(products) || !products.length) return;
      const container = document.createElement("div");
      container.className = "assistant-products";
      container.innerHTML = products.map(product => {
        const id = Math.max(0, Math.trunc(Number(product.id) || 0));
        const image = safeUrl(product.imagen) || fallbackImage;
        const url = safeUrl(product.url) || `/productos/${id}/`;
        const calculation = product.calculo_carrito;
        if (calculation) calculations.set(id, calculation);
        if (product.carrito_cantidad) cartItems.set(id, Number(product.carrito_cantidad));
        const calculationText = product.cantidad_envases
          ? `<p class="assistant-product-calc">${escapeHtml(product.litros_necesarios)} L · ${escapeHtml(product.cantidad_envases)} envase(s) · Total ${formatClp(product.presupuesto_total)}</p>`
          : product.cantidad_requerida
            ? `<p class="assistant-product-calc">${escapeHtml(product.rol || "Material")} · ${escapeHtml(product.cantidad_requerida)} unidad(es) · Subtotal ${formatClp(product.subtotal)}</p><p class="assistant-product-calc">${escapeHtml(product.detalle_material || "")}</p>`
            : "";
        const optionalText = product.es_opcional
          ? '<p class="assistant-product-optional"><i class="fa-solid fa-circle-info"></i> Opcional · no incluido en el total seleccionado</p>'
          : "";
        const addButton = calculation && product.stock_suficiente
          ? `<button type="button" data-chat-add="${id}"><i class="fa-solid fa-cart-plus"></i> Agregar cálculo</button>`
          : product.carrito_cantidad
            ? `<button type="button" data-chat-product="${id}"><i class="fa-solid fa-cart-plus"></i> Agregar ${escapeHtml(product.carrito_cantidad)}</button>`
            : "";
        return `<article class="assistant-product"><div class="assistant-product-image"><img src="${image}" alt="${escapeHtml(product.nombre || "Producto SFI")}" loading="lazy"></div><div class="assistant-product-body"><small>${escapeHtml(product.rol || product.marca || product.categoria || "SFI")}</small><h3>${escapeHtml(product.nombre || "Producto")}</h3><div class="assistant-product-meta"><span>${escapeHtml(product.presentacion || "")}</span><span>${escapeHtml(product.terminacion || "")}</span><span>${escapeHtml(product.stock)} disponibles</span></div>${calculationText}${optionalText}<strong class="assistant-product-price">${formatClp(product.precio)} c/u</strong><div class="assistant-product-actions"><a href="${url}">Ver producto</a>${addButton}</div></div></article>`;
      }).join("");
      messages.appendChild(container);
      container.querySelectorAll("img").forEach(image => image.addEventListener("error", function replaceImage() {
        image.removeEventListener("error", replaceImage);
        if (fallbackImage) image.src = fallbackImage;
      }));
      scrollToLatest();
    }

    function renderMasters(masters) {
      if (!Array.isArray(masters) || !masters.length) return;
      const container = document.createElement("div");
      container.className = "assistant-masters";
      container.innerHTML = masters.map(master => {
        const id = Math.max(0, Math.trunc(Number(master.id) || 0));
        const image = safeUrl(master.foto) || fallbackMasterImage;
        const url = safeUrl(master.url) || `/maestros/${id}/`;
        const specialties = Array.isArray(master.especialidades) ? master.especialidades : [];
        const communes = Array.isArray(master.comunas) ? master.comunas : [];
        const years = Math.max(0, Math.trunc(Number(master.anos_experiencia) || 0));
        return `<article class="assistant-master"><div class="assistant-master-image"><img src="${image}" alt="Foto profesional de ${escapeHtml(master.nombre || "Maestro SFI")}" loading="lazy"><span><i class="fa-solid fa-circle-check"></i> Verificado por SFI</span></div><div class="assistant-master-body"><small>Maestro disponible</small><h3>${escapeHtml(master.nombre || "Profesional SFI")}</h3><p class="assistant-master-specialties">${escapeHtml(specialties.join(" · "))}</p><ul><li><i class="fa-solid fa-briefcase"></i> ${escapeHtml(years)} ${years === 1 ? "año" : "años"} de experiencia</li><li><i class="fa-solid fa-location-dot"></i> ${escapeHtml(communes.join(" · "))}</li></ul><a href="${url}"><i class="fa-regular fa-address-card"></i> Ver perfil</a></div></article>`;
      }).join("");
      messages.appendChild(container);
      container.querySelectorAll("img").forEach(image => image.addEventListener("error", function replaceMasterImage() {
        image.removeEventListener("error", replaceMasterImage);
        if (fallbackMasterImage) image.src = fallbackMasterImage;
      }));
      scrollToLatest();
    }

    function renderSuggestions(items) {
      if (!Array.isArray(items) || !items.length) return;
      suggestions.innerHTML = items.slice(0, 3).map(item => `<button type="button" data-suggestion="${escapeHtml(item)}"><i class="fa-regular fa-message"></i> ${escapeHtml(item)}</button>`).join("");
    }

    async function askAssistant(message) {
      errorBox.hidden = true;
      addMessage("user", message);
      rememberMessage("user", message);
      const historyForRequest = history.slice(-6);
      history.push({role: "user", content: message});
      const typing = addTyping();
      submit.disabled = true;
      submit.querySelector("span").textContent = "Pensando...";
      try {
        const response = await fetch(root.dataset.apiUrl, {
          method: "POST",
          credentials: "same-origin",
          headers: {"Content-Type": "application/json", Accept: "application/json", "X-CSRFToken": getCookie("csrftoken")},
          body: JSON.stringify({mensaje: message, historial: historyForRequest, productos_contexto: contextProductIds()}),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(firstError(data) || "No fue posible consultar al asistente.");
        typing.remove();
        const answer = String(data.mensaje || "Cuéntame un poco más sobre tu proyecto.");
        addMessage("assistant", answer);
        rememberMessage("assistant", answer, data.productos, data.maestros);
        history.push({role: "assistant", content: answer});
        history = history.slice(-6);
        renderProducts(data.productos);
        renderMasters(data.maestros);
        renderSuggestions(data.sugerencias);
      } catch (error) {
        typing.remove();
        const messageText = error.message || "No fue posible consultar al asistente.";
        addMessage("assistant", messageText);
        rememberMessage("assistant", messageText);
        errorBox.textContent = messageText;
        errorBox.hidden = false;
      } finally {
        submit.disabled = false;
        submit.querySelector("span").textContent = "Enviar";
        input.focus();
      }
    }

    form.addEventListener("submit", event => {
      event.preventDefault();
      const message = input.value.trim();
      if (message.length < 2) return;
      input.value = "";
      askAssistant(message);
    });

    suggestions.addEventListener("click", event => {
      const visualizerButton = event.target.closest("[data-open-visualizer]");
      if (visualizerButton) {
        document.getElementById("visualizador-pintura")?.scrollIntoView({behavior: "smooth", block: "start"});
        return;
      }
      const button = event.target.closest("[data-suggestion]");
      if (!button || submit.disabled) return;
      input.value = button.dataset.suggestion || "";
      form.requestSubmit();
    });

    function showCartToast(message) {
      const toastElement = document.getElementById("cart-toast");
      const messageElement = document.getElementById("cart-toast-message");
      if (messageElement && message) {
        messageElement.textContent = message;
      }
      if (toastElement) {
        if (window.bootstrap && window.bootstrap.Toast) {
          const toast = window.bootstrap.Toast.getOrCreateInstance(toastElement, { delay: 4000 });
          toast.show();
        } else {
          toastElement.classList.add("show");
          setTimeout(() => toastElement.classList.remove("show"), 4000);
        }
      }
    }

    messages.addEventListener("click", async event => {
      const button = event.target.closest("[data-chat-add], [data-chat-product]");
      if (!button || button.disabled) return;
      if (!authenticated) {
        window.location.assign(root.dataset.loginUrl);
        return;
      }
      const isCalculation = Boolean(button.dataset.chatAdd);
      const productId = Number(isCalculation ? button.dataset.chatAdd : button.dataset.chatProduct);
      const payload = isCalculation
        ? calculations.get(productId)
        : {producto: productId, cantidad_producto: cartItems.get(productId)};
      if (!payload || !payload.producto) return;
      button.disabled = true;
      const original = button.innerHTML;
      button.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Agregando…';
      try {
        const response = await fetch(
          isCalculation ? root.dataset.addCartUrl : root.dataset.addProductUrl,
          {
            method: "POST",
            credentials: "same-origin",
            headers: {"Content-Type": "application/json", Accept: "application/json", "X-CSRFToken": getCookie("csrftoken")},
            body: JSON.stringify(payload),
          },
        );
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(firstError(data) || "No fue posible agregar el producto.");

        button.innerHTML = '<i class="fa-solid fa-circle-check"></i> Agregado';
        button.classList.add("added");

        showCartToast(data.message || "Producto agregado al carrito exitosamente.");
      } catch (error) {
        errorBox.textContent = error.message || "No fue posible agregar el producto.";
        errorBox.hidden = false;
        button.disabled = false;
        button.innerHTML = original;
      }
    });

    if (!speechSupported && readConversation) readConversation.hidden = true;
    messages.querySelectorAll(".assistant-message").forEach(article => {
      attachMessageSpeechButton(article, article.querySelector(".message-content p"));
    });
    readConversation?.addEventListener("click", () => {
      const conversation = [...messages.querySelectorAll(".chat-message")]
        .map(article => {
          const text = article.querySelector(".message-content p")?.textContent.trim();
          if (!text) return "";
          const speaker = article.classList.contains("user-message") ? "Tú" : "Asistente SFI";
          return `${speaker}: ${text}`;
        })
        .filter(Boolean);
      startSpeech(conversation, readConversation);
    });

    clear.addEventListener("click", () => {
      stopSpeech();
      history = [];
      conversationEntries = [];
      sessionStorage.removeItem(conversationStorageKey);
      calculations = new Map();
      cartItems = new Map();
      messages.innerHTML = "";
      addMessage("assistant", "Empecemos de nuevo. Cuéntame qué necesitas para tu proyecto.");
      errorBox.hidden = true;
      input.focus();
    });

    input.addEventListener("keydown", event => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        form.requestSubmit();
      }
    });

    function restoreConversation() {
      let stored;
      try {
        stored = JSON.parse(sessionStorage.getItem(conversationStorageKey) || "null");
      } catch (_error) {
        return;
      }
      if (!stored || !Array.isArray(stored.entries) || !stored.entries.length) return;
      conversationEntries = stored.entries.filter(entry => (
        entry
        && ["user", "assistant"].includes(entry.role)
        && typeof entry.text === "string"
      )).slice(-24);
      if (!conversationEntries.length) return;
      messages.innerHTML = "";
      conversationEntries.forEach(entry => {
        addMessage(entry.role, entry.text);
        if (entry.role === "assistant") {
          renderProducts(entry.products);
          renderMasters(entry.masters);
        }
      });
      history = conversationEntries.slice(-6).map(entry => ({
        role: entry.role,
        content: entry.text.slice(0, 700),
      }));
      scrollToLatest();
    }

    restoreConversation();
    window.addEventListener("pagehide", stopSpeech);
  });
})();
