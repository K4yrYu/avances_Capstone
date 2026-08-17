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
    const security = window.FerremasSecurity;
    if (!root || !form || !input || !messages || !security) return;

    const {escapeHtml, safeUrl} = security;
    const fallbackImage = safeUrl(root.dataset.placeholderUrl);
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

    function rememberMessage(role, text, products = []) {
      conversationEntries.push({
        role,
        text: String(text || "").slice(0, 1400),
        products: Array.isArray(products) ? products.slice(0, 8) : [],
      });
      conversationEntries = conversationEntries.slice(-24);
      saveConversation();
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
        const addButton = calculation && product.stock_suficiente
          ? `<button type="button" data-chat-add="${id}"><i class="fa-solid fa-cart-plus"></i> Agregar cálculo</button>`
          : product.carrito_cantidad
            ? `<button type="button" data-chat-product="${id}"><i class="fa-solid fa-cart-plus"></i> Agregar ${escapeHtml(product.carrito_cantidad)}</button>`
            : "";
        return `<article class="assistant-product"><div class="assistant-product-image"><img src="${image}" alt="${escapeHtml(product.nombre || "Producto SFI")}" loading="lazy"></div><div class="assistant-product-body"><small>${escapeHtml(product.rol || product.marca || product.categoria || "SFI")}</small><h3>${escapeHtml(product.nombre || "Producto")}</h3><div class="assistant-product-meta"><span>${escapeHtml(product.presentacion || "")}</span><span>${escapeHtml(product.terminacion || "")}</span><span>${escapeHtml(product.stock)} disponibles</span></div>${calculationText}<strong class="assistant-product-price">${formatClp(product.precio)} c/u</strong><div class="assistant-product-actions"><a href="${url}">Ver producto</a>${addButton}</div></div></article>`;
      }).join("");
      messages.appendChild(container);
      container.querySelectorAll("img").forEach(image => image.addEventListener("error", function replaceImage() {
        image.removeEventListener("error", replaceImage);
        if (fallbackImage) image.src = fallbackImage;
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
          body: JSON.stringify({mensaje: message, historial: historyForRequest}),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(firstError(data) || "No fue posible consultar al asistente.");
        typing.remove();
        const answer = String(data.mensaje || "Cuéntame un poco más sobre tu proyecto.");
        addMessage("assistant", answer);
        rememberMessage("assistant", answer, data.productos);
        history.push({role: "assistant", content: answer});
        history = history.slice(-6);
        renderProducts(data.productos);
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
      button.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Verificando';
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
        if (!response.ok) throw new Error(firstError(data) || "No fue posible agregar el cálculo.");
        window.location.assign(safeUrl(data.redirect_url) || "/carrito/");
      } catch (error) {
        errorBox.textContent = error.message || "No fue posible agregar el cálculo.";
        errorBox.hidden = false;
        button.disabled = false;
        button.innerHTML = original;
      }
    });

    clear.addEventListener("click", () => {
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
        if (entry.role === "assistant") renderProducts(entry.products);
      });
      history = conversationEntries.slice(-6).map(entry => ({
        role: entry.role,
        content: entry.text.slice(0, 700),
      }));
      scrollToLatest();
    }

    restoreConversation();
  });
})();
