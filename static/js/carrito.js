(() => {
  "use strict";

  const PAYMENT_PENDING_KEY = "ferremas_pago_pendiente";
  const SUPPORTED_CURRENCIES = new Set(["CLP", "USD", "EUR", "BRL"]);
  const root = document.getElementById("contenido-carrito");

  if (!root) return;

  function getCookie(name) {
    const prefix = `${name}=`;
    const cookie = document.cookie
      .split(";")
      .map((value) => value.trim())
      .find((value) => value.startsWith(prefix));
    return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : null;
  }

  function parseNumber(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number : 0;
  }

  function readError(data, fallback) {
    if (!data || typeof data !== "object") return fallback;
    if (typeof data.detail === "string") return data.detail;
    if (typeof data.error === "string") return data.error;
    return fallback;
  }

  async function readJson(response) {
    try {
      return await response.json();
    } catch {
      return {};
    }
  }

  window.addEventListener("pageshow", async (event) => {
    if (sessionStorage.getItem(PAYMENT_PENDING_KEY) !== "1") return;

    const navigation = performance.getEntriesByType("navigation")[0];
    const returnedWithBackButton = event.persisted || navigation?.type === "back_forward";
    if (!returnedWithBackButton) return;

    try {
      await fetch(root.dataset.cancelPaymentUrl, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "X-CSRFToken": getCookie("csrftoken") || "",
        },
      });
    } finally {
      sessionStorage.removeItem(PAYMENT_PENDING_KEY);
      window.location.reload();
    }
  });

  document.addEventListener("DOMContentLoaded", () => {
    const currencySelector = document.getElementById("moneda-selector");
    const currencyMessage = document.getElementById("currency-message");
    const cartItems = document.getElementById("cart-items");
    const paymentForm = document.getElementById("form-pago");
    const toastElement = document.getElementById("cart-toast");
    const toastMessage = document.getElementById("cart-toast-message");
    const toast = toastElement && window.bootstrap
      ? window.bootstrap.Toast.getOrCreateInstance(toastElement, { delay: 3200 })
      : null;

    let selectedCurrency = localStorage.getItem("moneda") || "CLP";
    let exchangeRate = 1;
    const exchangeRateCache = new Map([["CLP", 1]]);

    if (!SUPPORTED_CURRENCIES.has(selectedCurrency)) selectedCurrency = "CLP";

    function showToast(message, type = "info") {
      if (!toastElement || !toastMessage || !toast) return;
      toastMessage.textContent = message;
      toastElement.classList.toggle("is-error", type === "error");
      toast.show();
    }

    function formatMoney(clpValue) {
      const converted = parseNumber(clpValue) * exchangeRate;
      const fractionDigits = selectedCurrency === "CLP" ? 0 : 2;
      return new Intl.NumberFormat("es-CL", {
        style: "currency",
        currency: selectedCurrency,
        minimumFractionDigits: fractionDigits,
        maximumFractionDigits: fractionDigits,
      }).format(converted);
    }

    function renderMoney() {
      document.querySelectorAll(".money-value[data-clp]").forEach((element) => {
        element.textContent = formatMoney(element.dataset.clp);
      });
    }

    async function loadExchangeRate(currency) {
      if (exchangeRateCache.has(currency)) return exchangeRateCache.get(currency);

      const response = await fetch("https://open.er-api.com/v6/latest/CLP", {
        headers: { Accept: "application/json" },
      });
      if (!response.ok) throw new Error("No se pudo consultar el tipo de cambio.");

      const data = await response.json();
      const rate = parseNumber(data?.rates?.[currency]);
      if (rate <= 0) throw new Error("El tipo de cambio no está disponible.");

      exchangeRateCache.set(currency, rate);
      return rate;
    }

    async function changeCurrency(currency) {
      selectedCurrency = SUPPORTED_CURRENCIES.has(currency) ? currency : "CLP";
      if (currencySelector) currencySelector.disabled = true;

      try {
        exchangeRate = await loadExchangeRate(selectedCurrency);
        localStorage.setItem("moneda", selectedCurrency);
        if (currencyMessage) {
          currencyMessage.textContent = selectedCurrency === "CLP"
            ? ""
            : `Valores referenciales en ${selectedCurrency}. El pago final se realiza en CLP.`;
        }
      } catch {
        selectedCurrency = "CLP";
        exchangeRate = 1;
        localStorage.setItem("moneda", "CLP");
        if (currencySelector) currencySelector.value = "CLP";
        if (currencyMessage) {
          currencyMessage.textContent = "No pudimos obtener el tipo de cambio. Mostramos los valores en CLP.";
        }
        showToast("No fue posible actualizar la moneda.", "error");
      } finally {
        if (currencySelector) currencySelector.disabled = false;
        renderMoney();
      }
    }

    if (currencySelector) {
      currencySelector.value = selectedCurrency;
      currencySelector.addEventListener("change", () => changeCurrency(currencySelector.value));
      changeCurrency(selectedCurrency);
    } else {
      renderMoney();
    }

    function updateQuantityButton(item) {
      const quantity = parseNumber(item.dataset.quantity);
      const stock = parseNumber(item.dataset.stock);
      const decreaseIcon = item.querySelector('[data-cart-action="decrease"] i');
      const increaseButton = item.querySelector('[data-cart-action="increase"]');

      if (decreaseIcon) {
        decreaseIcon.classList.toggle("fa-trash-can", quantity === 1);
        decreaseIcon.classList.toggle("fa-minus", quantity !== 1);
      }
      if (increaseButton) increaseButton.disabled = quantity >= stock;
    }

    function updateCartCount() {
      const count = cartItems?.querySelectorAll(".cart-item").length || 0;
      const countElement = document.getElementById("cart-items-count");
      if (countElement) countElement.textContent = `${count} producto${count === 1 ? "" : "s"}`;
    }

    function applyCartResponse(item, data, nextQuantity) {
      const total = parseNumber(data.total_carrito);
      const totalElements = document.querySelectorAll('[data-clp][id="total-carrito"], .summary-line .money-value');

      totalElements.forEach((element) => {
        element.dataset.clp = String(total);
      });

      if (nextQuantity === 0) {
        item.remove();
        updateCartCount();
      } else {
        item.dataset.quantity = String(nextQuantity);
        const quantityOutput = item.querySelector(".quantity-value");
        const subtotal = item.querySelector(".item-subtotal-value");
        if (quantityOutput) quantityOutput.textContent = String(nextQuantity);
        if (subtotal) subtotal.dataset.clp = String(parseNumber(data.subtotal_venta));
        updateQuantityButton(item);
      }

      renderMoney();
      if (total === 0) window.location.reload();
    }

    async function changeQuantity(item, action) {
      const quantity = parseNumber(item.dataset.quantity);
      const stock = parseNumber(item.dataset.stock);
      const isIncrease = action === "increase";
      const nextQuantity = isIncrease ? quantity + 1 : Math.max(0, quantity - 1);

      if (isIncrease && nextQuantity > stock) {
        showToast(`Solo hay ${stock} unidades disponibles.`, "error");
        return;
      }

      const url = isIncrease ? item.dataset.updateUrl : item.dataset.decreaseUrl;
      item.classList.add("is-updating");

      try {
        const options = {
          method: "PUT",
          headers: {
            Accept: "application/json",
            "X-CSRFToken": getCookie("csrftoken") || "",
          },
        };

        if (isIncrease) {
          options.headers["Content-Type"] = "application/json";
          options.body = JSON.stringify({ cantidad_producto: nextQuantity });
        }

        const response = await fetch(url, options);
        const data = await readJson(response);
        if (!response.ok) throw new Error(readError(data, "No fue posible actualizar el carrito."));

        applyCartResponse(item, data, nextQuantity);
        showToast(nextQuantity === 0 ? "Producto eliminado del carrito." : "Cantidad actualizada.");
      } catch (error) {
        showToast(error.message || "No fue posible actualizar el carrito.", "error");
      } finally {
        item.classList.remove("is-updating");
      }
    }

    if (cartItems) {
      cartItems.querySelectorAll(".cart-item").forEach(updateQuantityButton);
      cartItems.addEventListener("click", (event) => {
        const button = event.target.closest("[data-cart-action]");
        if (!button || button.disabled) return;
        const item = button.closest(".cart-item");
        if (item) changeQuantity(item, button.dataset.cartAction);
      });

      cartItems.querySelectorAll("img").forEach((image) => {
        image.addEventListener("error", () => {
          image.src = root.dataset.placeholderUrl;
          image.classList.add("image-fallback");
        }, { once: true });
      });
    }

    if (paymentForm) {
      const addressWrapper = document.getElementById("direccion-despacho-wrapper");
      const addressInput = document.getElementById("direccion-despacho");
      const paymentError = document.getElementById("payment-error");
      const paymentButton = document.getElementById("pay-button");

      function showPaymentError(message) {
        if (!paymentError) return;
        paymentError.textContent = message;
        paymentError.hidden = !message;
      }

      function updateDelivery() {
        const deliveryType = paymentForm.elements.tipo_entrega.value;
        const needsAddress = deliveryType === "despacho";
        if (addressWrapper) addressWrapper.hidden = !needsAddress;
        if (addressInput) addressInput.required = needsAddress;
        showPaymentError("");
      }

      paymentForm.querySelectorAll('[name="tipo_entrega"]').forEach((radio) => {
        radio.addEventListener("change", updateDelivery);
      });
      updateDelivery();

      paymentForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        showPaymentError("");

        const deliveryType = paymentForm.elements.tipo_entrega.value;
        const address = addressInput?.value.trim() || "";
        if (deliveryType === "despacho" && address.length < 10) {
          showPaymentError("Ingresa una dirección completa de al menos 10 caracteres.");
          addressInput?.focus();
          return;
        }

        if (paymentButton) {
          paymentButton.disabled = true;
          paymentButton.querySelector("span").textContent = "Conectando con Webpay…";
        }

        try {
          const response = await fetch(paymentForm.action, {
            method: "POST",
            headers: {
              Accept: "application/json",
              "X-Requested-With": "XMLHttpRequest",
              "X-CSRFToken": getCookie("csrftoken") || "",
            },
            body: new FormData(paymentForm),
          });
          const data = await readJson(response);
          if (!response.ok || !data.redirect_url) {
            throw new Error(readError(data, "No fue posible iniciar el pago."));
          }

          sessionStorage.setItem(PAYMENT_PENDING_KEY, "1");
          window.location.assign(data.redirect_url);
        } catch (error) {
          showPaymentError(error.message || "No fue posible iniciar el pago. Intenta nuevamente.");
          if (paymentButton) {
            paymentButton.disabled = false;
            paymentButton.querySelector("span").textContent = "Continuar a Webpay";
          }
        }
      });
    }
  });
})();
