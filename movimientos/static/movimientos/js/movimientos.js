(() => {
  const canvas = document.getElementById("flowChart");
  if (!canvas || typeof Chart === "undefined") return;
  const read = id => JSON.parse(document.getElementById(id).textContent);
  new Chart(canvas, {
    type: "line",
    data: { labels: read("grafico-fechas"), datasets: [
      { label: "Entradas", data: read("grafico-entradas"), borderColor: "#079267", backgroundColor: "rgba(7,146,103,.12)", fill: true, tension: .3 },
      { label: "Salidas", data: read("grafico-salidas"), borderColor: "#ffb800", backgroundColor: "rgba(255,184,0,.10)", fill: true, tension: .3 }
    ]},
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "bottom" } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } }
  });
})();
