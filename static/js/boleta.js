(() => {
  "use strict";

  document.addEventListener("DOMContentLoaded", () => {
    const formatter = new Intl.NumberFormat("es-CL", {
      style: "currency",
      currency: "CLP",
      maximumFractionDigits: 0,
    });

    document.querySelectorAll(".money-value[data-clp]").forEach((element) => {
      const value = Number(element.dataset.clp);
      if (Number.isFinite(value)) element.textContent = formatter.format(value);
    });

    document.getElementById("print-receipt")?.addEventListener("click", () => window.print());
  });
})();
