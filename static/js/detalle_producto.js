(() => {
  "use strict";

  const root = document.getElementById("detalle-producto");
  if (!root) return;

  const SUPPORTED_CURRENCIES = new Set(["CLP", "USD", "EUR", "BRL"]);

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

  async function readJson(response) {
    try {
      return await response.json();
    } catch {
      return {};
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    const productId = parseNumber(root.dataset.productId);
    const productPrice = parseNumber(root.dataset.productPrice);
    const productStock = parseNumber(root.dataset.productStock);
    const priceElement = document.getElementById("product-price");
    const currencySelector = document.getElementById("moneda-selector");
    const currencyStatus = document.getElementById("currency-status");
    const quantityOutput = document.getElementById("product-quantity");
    const minusButton = document.getElementById("quantity-minus");
    const plusButton = document.getElementById("quantity-plus");
    const addButton = document.getElementById("add-to-cart");
    const cartLink = document.getElementById("go-to-cart");
    const errorBox = document.getElementById("detail-error");
    const image = document.getElementById("product-main-image");
    const toastElement = document.getElementById("detail-toast");
    const toastMessage = document.getElementById("detail-toast-message");
    const toast = toastElement && window.bootstrap
      ? window.bootstrap.Toast.getOrCreateInstance(toastElement, { delay: 3200 })
      : null;

    let quantity = 1;
    let currency = localStorage.getItem("moneda") || "CLP";
    let exchangeRate = 1;
    const rateCache = new Map([["CLP", 1]]);

    if (!SUPPORTED_CURRENCIES.has(currency)) currency = "CLP";

    function formatMoney(value) {
      const decimals = currency === "CLP" ? 0 : 2;
      return new Intl.NumberFormat("es-CL", {
        style: "currency",
        currency,
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      }).format(value * exchangeRate);
    }

    function renderPrice() {
      if (priceElement) priceElement.textContent = formatMoney(productPrice);
    }

    async function getExchangeRate(targetCurrency) {
      if (rateCache.has(targetCurrency)) return rateCache.get(targetCurrency);
      const response = await fetch("https://open.er-api.com/v6/latest/CLP", {
        headers: { Accept: "application/json" },
      });
      if (!response.ok) throw new Error("No fue posible consultar el tipo de cambio.");
      const data = await response.json();
      const rate = parseNumber(data?.rates?.[targetCurrency]);
      if (rate <= 0) throw new Error("Tipo de cambio no disponible.");
      rateCache.set(targetCurrency, rate);
      return rate;
    }

    async function changeCurrency(targetCurrency) {
      currency = SUPPORTED_CURRENCIES.has(targetCurrency) ? targetCurrency : "CLP";
      if (currencySelector) currencySelector.disabled = true;
      try {
        exchangeRate = await getExchangeRate(currency);
        localStorage.setItem("moneda", currency);
        if (currencyStatus) {
          currencyStatus.textContent = currency === "CLP"
            ? ""
            : `Precio referencial en ${currency}. El cobro final se realiza en CLP.`;
        }
      } catch {
        currency = "CLP";
        exchangeRate = 1;
        localStorage.setItem("moneda", "CLP");
        if (currencySelector) currencySelector.value = "CLP";
        if (currencyStatus) currencyStatus.textContent = "No pudimos obtener el tipo de cambio. Mostramos el precio en CLP.";
      } finally {
        if (currencySelector) currencySelector.disabled = false;
        renderPrice();
      }
    }

    if (currencySelector) {
      currencySelector.value = currency;
      currencySelector.addEventListener("change", () => changeCurrency(currencySelector.value));
      changeCurrency(currency);
    } else {
      renderPrice();
    }

    function renderQuantity() {
      if (quantityOutput) quantityOutput.textContent = String(quantity);
      if (minusButton) minusButton.disabled = quantity <= 1;
      if (plusButton) plusButton.disabled = quantity >= productStock;
    }

    minusButton?.addEventListener("click", () => {
      quantity = Math.max(1, quantity - 1);
      renderQuantity();
    });

    plusButton?.addEventListener("click", () => {
      quantity = Math.min(productStock, quantity + 1);
      renderQuantity();
    });
    renderQuantity();

    function showError(message) {
      if (!errorBox) return;
      errorBox.textContent = message;
      errorBox.hidden = !message;
    }

    addButton?.addEventListener("click", async () => {
      showError("");
      addButton.disabled = true;
      const text = addButton.querySelector("span");
      if (text) text.textContent = "Agregando…";

      try {
        const response = await fetch(root.dataset.addUrl, {
          method: "POST",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie("csrftoken") || "",
          },
          body: JSON.stringify({ producto: productId, cantidad_producto: quantity }),
        });
        const data = await readJson(response);
        if (!response.ok) throw new Error(data.detail || "No fue posible agregar el producto.");

        addButton.classList.add("added");
        addButton.innerHTML = '<i class="fa-solid fa-circle-check" aria-hidden="true"></i> <span>Producto agregado</span>';
        if (minusButton) minusButton.disabled = true;
        if (plusButton) plusButton.disabled = true;
        if (cartLink) cartLink.hidden = false;
        if (toast && toastMessage) {
          toastMessage.textContent = "Producto agregado correctamente al carrito.";
          toast.show();
        }
      } catch (error) {
        showError(error.message || "No fue posible agregar el producto al carrito.");
        addButton.disabled = false;
        if (text) text.textContent = "Agregar al carrito";
      }
    });

    image?.addEventListener("error", () => {
      image.src = root.dataset.placeholderUrl;
      image.classList.add("image-fallback");
    }, { once: true });
  });
})();
