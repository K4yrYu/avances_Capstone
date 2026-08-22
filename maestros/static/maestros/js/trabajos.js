(() => {
  const input = document.getElementById("id_imagenes");
  if (!input) return;

  const container = document.createElement("div");
  container.className = "master-new-images-preview";
  container.innerHTML = `
    <div class="master-new-images-heading">
      <div><strong>Vista previa</strong><small>Imágenes nuevas que se agregarán al trabajo.</small></div>
      <span>0 imágenes</span>
    </div>
    <div class="master-new-images-grid"></div>
  `;
  input.insertAdjacentElement("afterend", container);

  const grid = container.querySelector(".master-new-images-grid");
  const counter = container.querySelector(".master-new-images-heading span");
  let objectUrls = [];

  const limpiarUrls = () => {
    objectUrls.forEach((url) => URL.revokeObjectURL(url));
    objectUrls = [];
  };

  const renderizar = () => {
    limpiarUrls();
    grid.innerHTML = "";
    const files = Array.from(input.files || []);
    counter.textContent = `${files.length} ${files.length === 1 ? "imagen" : "imágenes"}`;
    container.classList.toggle("has-images", files.length > 0);

    files.forEach((file) => {
      const url = URL.createObjectURL(file);
      objectUrls.push(url);
      const figure = document.createElement("figure");
      const image = document.createElement("img");
      image.src = url;
      image.alt = `Vista previa de ${file.name}`;
      const caption = document.createElement("figcaption");
      caption.textContent = file.name;
      figure.append(image, caption);
      grid.appendChild(figure);
    });
  };

  input.addEventListener("change", renderizar);
  window.addEventListener("beforeunload", limpiarUrls);
})();
