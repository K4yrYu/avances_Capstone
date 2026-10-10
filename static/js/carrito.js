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
      const splitItem = document.querySelector(
        `[name="detalle_${item.dataset.detailId}_despacho_1"]`
      )?.closest("[data-split-item]");

      totalElements.forEach((element) => {
        element.dataset.clp = String(total);
      });

      if (nextQuantity === 0) {
        item.remove();
        splitItem?.remove();
        updateCartCount();
      } else {
        item.dataset.quantity = String(nextQuantity);
        const quantityOutput = item.querySelector(".quantity-value");
        const subtotal = item.querySelector(".item-subtotal-value");
        if (quantityOutput) quantityOutput.textContent = String(nextQuantity);
        if (subtotal) subtotal.dataset.clp = String(parseNumber(data.subtotal_venta));
        if (splitItem) {
          splitItem.dataset.total = String(nextQuantity);
          const hiddenInput = splitItem.querySelector('input[type="hidden"]');
          const checkbox = splitItem.querySelector("[data-dispatch-product]");
          const quantityCopy = splitItem.querySelector(".dispatch-product-copy small");
          if (hiddenInput) hiddenInput.value = checkbox?.checked ? String(nextQuantity) : "0";
          if (quantityCopy) quantityCopy.firstChild.textContent = `${nextQuantity} unidad${nextQuantity === 1 ? "" : "es"} · `;
        }
        updateQuantityButton(item);
      }

      renderMoney();
      paymentForm?.dispatchEvent(new CustomEvent("cart:total-updated"));
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
      const regionInput = document.getElementById("region-despacho");
      const communeInput = document.getElementById("comuna-despacho");
      const streetInput = document.getElementById("calle-despacho");
      const streetNumberInput = document.getElementById("numero-despacho");
      const paymentError = document.getElementById("payment-error");
      const paymentButton = document.getElementById("pay-button");
      const scheduler = document.getElementById("programacion-despacho");
      const firstDate = document.getElementById("fecha-despacho-1");
      const secondDate = document.getElementById("fecha-despacho-2");
      const secondDateWrapper = document.getElementById("fecha-despacho-2-wrapper");
      const splitWrapper = document.getElementById("distribucion-despachos");
      const splitModal = document.getElementById("modal-distribucion-despachos");
      const editSplitButton = document.getElementById("editar-distribucion-despachos");
      const saveSplitButton = document.getElementById("guardar-distribucion-despachos");
      const splitModalError = document.getElementById("error-modal-despachos");
      const availabilityMessage = document.getElementById("mensaje-disponibilidad-despacho");
      const secondFeeLine = document.getElementById("cargo-segundo-despacho-line");
      const secondFeeValue = document.getElementById("cargo-segundo-despacho");
      const deliverySummary = document.getElementById("resumen-entrega");
      const totalElement = document.getElementById("total-carrito");
      const subtotalElement = paymentForm.querySelector(".summary-line .money-value[data-clp]");
      let dispatchDatesLoaded = false;
      let distributionConfirmed = false;

      function showPaymentError(message) {
        if (!paymentError) return;
        paymentError.textContent = message;
        paymentError.hidden = !message;
      }

      function dispatchCount() {
        return Number(paymentForm.elements.cantidad_despachos?.value || 1);
      }

      function updateTwoDispatchAvailability() {
        const twoOption = paymentForm.querySelector('[name="cantidad_despachos"][value="2"]');
        if (!twoOption) return;
        const productCount = Array.from(cartItems?.querySelectorAll(".cart-item") || []).length;
        twoOption.disabled = productCount < 2;
        twoOption.closest("label")?.classList.toggle("is-disabled", productCount < 2);
        if (twoOption.disabled && twoOption.checked) {
          const oneOption = paymentForm.querySelector('[name="cantidad_despachos"][value="1"]');
          if (oneOption) oneOption.checked = true;
        }
      }

      function updateDispatchTotal() {
        const isDispatch = paymentForm.elements.tipo_entrega.value === "despacho";
        const twoDispatches = isDispatch && dispatchCount() === 2;
        const fee = twoDispatches ? parseNumber(root.dataset.secondDispatchFee) : 0;
        const subtotal = parseNumber(subtotalElement?.dataset.clp);
        if (totalElement) totalElement.dataset.clp = String(subtotal + fee);
        if (secondFeeLine) secondFeeLine.hidden = !twoDispatches;
        if (secondFeeValue) secondFeeValue.textContent = formatMoney(fee);
        if (deliverySummary) {
          deliverySummary.textContent = isDispatch
            ? (twoDispatches ? "Dos fechas programadas" : "Una fecha programada")
            : "Retiro coordinado";
        }
        renderMoney();
      }

      function formatDispatchDate(value) {
        if (!value) return "Selecciona una fecha";
        const parsed = new Date(`${value}T12:00:00`);
        return new Intl.DateTimeFormat("es-CL", {
          weekday: "short", day: "2-digit", month: "short", year: "numeric",
        }).format(parsed);
      }

      function populateDispatchDates(dates) {
        const available = dates.filter((item) => item.disponible);
        const options = ['<option value="">Selecciona una fecha</option>'].concat(
          available.map((item) => `<option value="${item.fecha}">${formatDispatchDate(item.fecha)} · ${item.disponibles} cupo${item.disponibles === 1 ? "" : "s"}</option>`)
        ).join("");
        if (firstDate) firstDate.innerHTML = options;
        if (secondDate) secondDate.innerHTML = options;
        if (availabilityMessage) {
          availabilityMessage.textContent = available.length
            ? `${available.length} fechas con cupos disponibles.`
            : "No hay fechas disponibles para despacho en este momento.";
          availabilityMessage.classList.toggle("is-error", !available.length);
        }
        dispatchDatesLoaded = true;
      }

      async function loadDispatchDates() {
        if (dispatchDatesLoaded || !root.dataset.dispatchAvailabilityUrl) return;
        try {
          const response = await fetch(root.dataset.dispatchAvailabilityUrl, {
            credentials: "same-origin",
            headers: {Accept: "application/json"},
          });
          const data = await readJson(response);
          if (!response.ok) throw new Error(readError(data, "No fue posible cargar las fechas."));
          root.dataset.secondDispatchFee = String(parseNumber(data.cargo_segundo_despacho));
          populateDispatchDates(Array.isArray(data.fechas) ? data.fechas : []);
          if (!data.despachos_activos && availabilityMessage) {
            availabilityMessage.textContent = "Los despachos están temporalmente deshabilitados.";
            availabilityMessage.classList.add("is-error");
          }
        } catch (error) {
          if (availabilityMessage) {
            availabilityMessage.textContent = error.message;
            availabilityMessage.classList.add("is-error");
          }
        }
      }

      function splitItems() {
        return Array.from(splitModal?.querySelectorAll("[data-split-item]") || []);
      }

      function updateDispatchSummary() {
        const groups = {1: [], 2: []};
        splitItems().forEach((item) => {
          const total = parseNumber(item.dataset.total);
          const checked = Boolean(item.querySelector("[data-dispatch-product]")?.checked);
          const hidden = item.querySelector('input[type="hidden"]');
          const label = item.querySelector("[data-dispatch-label]");
          if (hidden) hidden.value = checked ? String(total) : "0";
          if (label) label.textContent = checked ? "Despacho 1" : "Despacho 2";
          groups[checked ? 1 : 2].push(`${item.dataset.productName} (${total})`);
        });
        [1, 2].forEach((number) => {
          const list = splitWrapper?.querySelector(`[data-summary-products="${number}"]`);
          const date = splitWrapper?.querySelector(`[data-summary-date="${number}"]`);
          if (list) {
            list.replaceChildren(...groups[number].map((name) => {
              const item = document.createElement("li");
              item.textContent = name;
              return item;
            }));
          }
          if (date) date.textContent = formatDispatchDate(number === 1 ? firstDate?.value : secondDate?.value);
        });
      }

      function openSplitModal() {
        if (!splitModal || dispatchCount() !== 2 || !firstDate?.value) return;
        splitModal.querySelector('[data-modal-date="1"]').textContent = formatDispatchDate(firstDate.value);
        splitModal.querySelector('[data-modal-date="2"]').textContent = secondDate?.value
          ? formatDispatchDate(secondDate.value)
          : "Fecha pendiente de selección";
        splitModalError.hidden = true;
        splitModal.hidden = false;
        document.body.classList.add("dispatch-modal-open");
        splitModal.querySelector("[data-dispatch-product]")?.focus();
      }

      function closeSplitModal() {
        if (!splitModal) return;
        splitModal.hidden = true;
        document.body.classList.remove("dispatch-modal-open");
      }

      function distributionIsValid() {
        const marked = splitItems().filter((item) => item.querySelector("[data-dispatch-product]")?.checked).length;
        return marked > 0 && marked < splitItems().length;
      }

      function updateDispatchCount() {
        updateTwoDispatchAvailability();
        const twoDispatches = dispatchCount() === 2;
        if (secondDateWrapper) secondDateWrapper.hidden = !twoDispatches;
        if (secondDate) secondDate.required = twoDispatches;
        if (secondDate) secondDate.disabled = twoDispatches && !distributionConfirmed;
        if (splitWrapper) splitWrapper.hidden = !twoDispatches;
        if (twoDispatches) updateDispatchSummary();
        updateDispatchTotal();
        showPaymentError("");
      }

      function updateDelivery() {
        const deliveryType = paymentForm.elements.tipo_entrega.value;
        const needsAddress = deliveryType === "despacho";
        if (addressWrapper) addressWrapper.hidden = !needsAddress;
        [regionInput, communeInput, streetInput, streetNumberInput].forEach((field) => {
          if (field) field.required = needsAddress;
        });
        if (scheduler) scheduler.hidden = !needsAddress;
        if (firstDate) firstDate.required = needsAddress;
        if (needsAddress) loadDispatchDates();
        updateDispatchCount();
        showPaymentError("");
      }

      paymentForm.querySelectorAll('[name="tipo_entrega"]').forEach((radio) => {
        radio.addEventListener("change", updateDelivery);
      });
      regionInput?.addEventListener("change", () => {
        const selectedRegion = regionInput.value;
        let availableCommunes = 0;
        Array.from(communeInput?.options || []).forEach((option, index) => {
          if (index === 0) return;
          const belongsToRegion = option.dataset.region === selectedRegion;
          option.hidden = !belongsToRegion;
          option.disabled = !belongsToRegion;
          if (belongsToRegion) availableCommunes += 1;
        });
        if (communeInput) {
          communeInput.value = "";
          communeInput.disabled = !selectedRegion || availableCommunes === 0;
          communeInput.options[0].textContent = selectedRegion
            ? "Selecciona una comuna"
            : "Primero selecciona una región";
        }
        showPaymentError("");
      });
      paymentForm.querySelectorAll('[name="cantidad_despachos"]').forEach((radio) => {
        radio.addEventListener("change", () => {
          updateDispatchCount();
          if (dispatchCount() === 2 && firstDate?.value) openSplitModal();
        });
      });
      editSplitButton?.addEventListener("click", openSplitModal);
      saveSplitButton?.addEventListener("click", () => {
        if (!distributionIsValid()) {
          splitModalError.textContent = "Debes dejar al menos un producto en cada despacho.";
          splitModalError.hidden = false;
          return;
        }
        updateDispatchSummary();
        distributionConfirmed = true;
        if (secondDate) {
          secondDate.disabled = false;
          secondDate.focus();
        }
        closeSplitModal();
      });
      splitModal?.querySelectorAll("[data-close-dispatch-modal]").forEach((button) => {
        button.addEventListener("click", closeSplitModal);
      });
      splitModal?.addEventListener("change", (event) => {
        if (event.target.matches("[data-dispatch-product]")) {
          const item = event.target.closest("[data-split-item]");
          item?.classList.toggle("is-first", event.target.checked);
          updateDispatchSummary();
          splitModalError.hidden = true;
        }
      });
      paymentForm.addEventListener("cart:total-updated", () => {
        updateDispatchCount();
        updateDispatchSummary();
      });
      firstDate?.addEventListener("change", () => {
        showPaymentError("");
        distributionConfirmed = false;
        if (secondDate) secondDate.disabled = true;
        updateDispatchSummary();
        if (dispatchCount() === 2 && firstDate.value) openSplitModal();
      });
      secondDate?.addEventListener("change", () => {
        showPaymentError("");
        updateDispatchSummary();
      });
      updateDelivery();

      paymentForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        showPaymentError("");

        const deliveryType = paymentForm.elements.tipo_entrega.value;
        if (deliveryType === "despacho") {
          if (!regionInput?.value || !communeInput?.value) {
            showPaymentError("Selecciona la región y comuna donde recibirás el despacho.");
            (!regionInput?.value ? regionInput : communeInput)?.focus();
            return;
          }
          if (!streetInput?.value.trim() || streetInput.value.trim().length < 3) {
            showPaymentError("Ingresa un nombre de calle o avenida válido.");
            streetInput?.focus();
            return;
          }
          if (!/^\d{1,6}[A-Za-z]?(?:-\d{1,4})?$/.test(streetNumberInput?.value.trim() || "")) {
            showPaymentError("Ingresa una numeración válida, por ejemplo 1234.");
            streetNumberInput?.focus();
            return;
          }
          if (!firstDate?.value) {
            showPaymentError("Selecciona la fecha del despacho.");
            firstDate?.focus();
            return;
          }
          if (dispatchCount() === 2) {
            if (!secondDate?.value) {
              showPaymentError("Selecciona la fecha del segundo despacho.");
              secondDate?.focus();
              return;
            }
            if (firstDate.value === secondDate.value) {
              showPaymentError("Los dos despachos deben tener fechas diferentes.");
              secondDate.focus();
              return;
            }
            if (!distributionIsValid()) {
              showPaymentError("Debes asignar al menos un producto a cada despacho.");
              openSplitModal();
              return;
            }
          }
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
