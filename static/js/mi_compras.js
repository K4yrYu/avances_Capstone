(() => {
  "use strict";

  document.addEventListener("DOMContentLoaded", () => {
    const root = document.getElementById("mis-compras");
    if (!root) return;

    const formatter = new Intl.NumberFormat("es-CL", {
      style: "currency",
      currency: "CLP",
      maximumFractionDigits: 0,
    });

    document.querySelectorAll(".money-value[data-clp]").forEach((element) => {
      const value = Number(element.dataset.clp);
      if (Number.isFinite(value)) element.textContent = formatter.format(value);
    });

    document.querySelectorAll(".purchased-product-image img").forEach((image) => {
      image.addEventListener("error", () => {
        image.src = root.dataset.placeholderUrl;
        image.alt = "Imagen no disponible";
      }, { once: true });
    });
  });
})();
