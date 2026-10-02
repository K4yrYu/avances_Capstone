(() => {
  "use strict";

  function normalizar(valor) {
    const compacto = String(valor || "").replace(/[.\s-]/g, "").toUpperCase();
    if (!/^\d{7,8}[0-9K]$/.test(compacto)) return "";
    return `${compacto.slice(0, -1)}-${compacto.slice(-1)}`;
  }

  function calcularDigito(cuerpo) {
    if (!/^\d{7,8}$/.test(String(cuerpo || ""))) return "";
    let suma = 0;
    let factor = 2;
    for (let indice = cuerpo.length - 1; indice >= 0; indice -= 1) {
      suma += Number(cuerpo[indice]) * factor;
      factor = factor === 7 ? 2 : factor + 1;
    }
    const resultado = 11 - (suma % 11);
    if (resultado === 11) return "0";
    if (resultado === 10) return "K";
    return String(resultado);
  }

  function esValido(valor) {
    const rut = normalizar(valor);
    if (!rut) return false;
    const [cuerpo, digito] = rut.split("-");
    return calcularDigito(cuerpo) === digito;
  }

  window.SFIRut = Object.freeze({ normalizar, calcularDigito, esValido });
})();
