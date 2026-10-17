(() => {
  const canvas = document.getElementById("flowChart");
  if (canvas && typeof Chart !== "undefined") {
    const read = id => JSON.parse(document.getElementById(id).textContent);
    new Chart(canvas, {
      type: "line",
      data: { labels: read("grafico-fechas"), datasets: [
        { label: "Entradas", data: read("grafico-entradas"), borderColor: "#079267", backgroundColor: "rgba(7,146,103,.12)", fill: true, tension: .3 },
        { label: "Salidas", data: read("grafico-salidas"), borderColor: "#ffb800", backgroundColor: "rgba(255,184,0,.10)", fill: true, tension: .3 }
      ]},
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } }
    });
  }

  const buscador = document.getElementById("buscador-merma");
  const resultados = document.getElementById("resultados-merma");
  const selector = document.getElementById("producto-merma");
  const cantidad = document.getElementById("cantidad-merma");
  const seleccionado = document.getElementById("producto-seleccionado-merma");
  if (!buscador || !resultados || !selector || !cantidad || !seleccionado) return;

  const opciones = [...resultados.querySelectorAll(".merma-product-option")];
  const etiquetaBusqueda = buscador.closest("label");
  const botonCambiar = seleccionado.querySelector("button");
  const normalizar = value => String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();

  function limpiarSeleccion() {
    selector.value = "";
    cantidad.value = "";
    cantidad.max = "";
    cantidad.disabled = true;
    seleccionado.hidden = true;
    resultados.hidden = false;
    etiquetaBusqueda.hidden = false;
    buscador.value = "";
    opciones.forEach(opcion => { opcion.hidden = false; opcion.classList.remove("is-selected"); });
    buscador.focus();
  }

  function seleccionarProducto(opcion) {
    const stock = Number(opcion.dataset.stock) || 0;
    selector.value = opcion.dataset.productId;
    cantidad.disabled = false;
    cantidad.max = String(stock);
    cantidad.placeholder = `Máximo ${stock}`;
    seleccionado.querySelector("img").src = opcion.dataset.image;
    seleccionado.querySelector("img").alt = opcion.dataset.name;
    seleccionado.querySelector("strong").textContent = opcion.dataset.name;
    seleccionado.querySelector("small").textContent = `${opcion.dataset.sku} · ${stock} disponibles`;
    seleccionado.hidden = false;
    resultados.hidden = true;
    etiquetaBusqueda.hidden = true;
    opciones.forEach(item => { item.hidden = false; item.classList.toggle("is-selected", item === opcion); });
    botonCambiar.innerHTML = '<i class="fa-solid fa-pen" aria-hidden="true"></i> Cambiar';
    cantidad.focus();
  }

  buscador.addEventListener("input", () => {
    const consulta = normalizar(buscador.value);
    opciones.forEach(opcion => { opcion.hidden = Boolean(consulta) && !normalizar(opcion.dataset.search).includes(consulta); });
  });
  resultados.addEventListener("click", event => {
    const opcion = event.target.closest(".merma-product-option");
    if (opcion) seleccionarProducto(opcion);
  });
  botonCambiar.addEventListener("click", limpiarSeleccion);
  cantidad.addEventListener("input", () => {
    const maximo = Number(cantidad.max) || 0;
    if (Number(cantidad.value) > maximo) cantidad.value = String(maximo);
  });
})();
