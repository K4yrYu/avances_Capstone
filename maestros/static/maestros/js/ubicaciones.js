(() => {
  const configurarVistaPrevia = () => {
    const input = document.getElementById("id_foto");
    if (!input) return;

    const fieldContainer = input.closest(".master-field");
    if (!fieldContainer) return;

    fieldContainer.classList.add("master-photo-field");
    const layout = document.createElement("div");
    layout.className = "master-photo-layout";

    const preview = document.createElement("div");
    preview.className = "master-photo-preview";
    preview.innerHTML = `
      <div class="master-photo-preview-frame">
        <img alt="Vista previa de la foto profesional">
        <span><i class="fa-solid fa-user"></i></span>
      </div>
      <div><strong>Vista previa</strong><small>Así se mostrará tu foto en el perfil.</small></div>
    `;
    const upload = document.createElement("div");
    upload.className = "master-photo-upload";
    upload.innerHTML = `
      <span class="master-photo-upload-icon"><i class="fa-solid fa-camera"></i></span>
      <div><strong>Selecciona tu fotografía</strong><small>Utiliza una imagen clara y reciente donde se vea bien tu rostro.</small></div>
      <div class="master-photo-input"></div>
    `;

    fieldContainer.insertBefore(layout, input);
    layout.append(preview, upload);
    upload.querySelector(".master-photo-input").appendChild(input);

    const image = preview.querySelector("img");
    const placeholder = preview.querySelector("span");
    let objectUrl = null;

    const mostrar = (url) => {
      if (url) {
        image.src = url;
        image.dataset.fallbackApplied = String(url === input.dataset.fallbackUrl);
        image.hidden = false;
        placeholder.hidden = true;
      } else {
        image.removeAttribute("src");
        image.hidden = true;
        placeholder.hidden = false;
      }
    };

    image.addEventListener("error", () => {
      if (image.dataset.fallbackApplied === "true") {
        image.hidden = true;
        placeholder.hidden = false;
        return;
      }
      mostrar(input.dataset.fallbackUrl || "");
    });

    mostrar(input.dataset.currentUrl || input.dataset.fallbackUrl || "");
    input.addEventListener("change", () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      const file = input.files?.[0];
      objectUrl = file ? URL.createObjectURL(file) : null;
      mostrar(objectUrl || input.dataset.currentUrl || input.dataset.fallbackUrl || "");
    });

    const clear = document.getElementById("foto-clear_id");
    clear?.addEventListener("change", () =>
      mostrar(
        clear.checked
          ? input.dataset.fallbackUrl || ""
          : input.dataset.currentUrl || input.dataset.fallbackUrl || ""
      )
    );
  };

  const configurarComunasMultiples = () => {
    const region = document.getElementById("id_region");
    const comunas = document.getElementById("id_comunas_trabajo");
    if (!region || !comunas) return;

    const picker = document.createElement("div");
    picker.className = "master-commune-picker";
    picker.innerHTML = `
      <div class="master-commune-toolbar">
        <label><i class="fa-solid fa-magnifying-glass"></i><input type="search" placeholder="Buscar comuna" aria-label="Buscar comuna"></label>
        <strong><span>0</span> seleccionadas</strong>
      </div>
      <div class="master-commune-options" role="group" aria-label="Comunas donde trabajas"></div>
      <p class="master-commune-empty" hidden>No hay comunas que coincidan con la búsqueda.</p>
    `;
    comunas.insertAdjacentElement("afterend", picker);
    comunas.classList.add("master-native-multiselect");
    const search = picker.querySelector("input");
    const optionsContainer = picker.querySelector(".master-commune-options");
    const counter = picker.querySelector("strong span");
    const empty = picker.querySelector(".master-commune-empty");

    const actualizarContador = () => {
      counter.textContent = Array.from(comunas.selectedOptions).length;
    };

    const renderizar = () => {
      const term = search.value.trim().toLocaleLowerCase("es");
      optionsContainer.innerHTML = "";
      const disponibles = Array.from(comunas.options).filter(
        (option) => !option.disabled && option.text.toLocaleLowerCase("es").includes(term)
      );
      disponibles.forEach((option, index) => {
        const label = document.createElement("label");
        label.className = "master-commune-option";
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = option.selected;
        checkbox.value = option.value;
        checkbox.id = `comuna-visual-${index}`;
        checkbox.addEventListener("change", () => {
          option.selected = checkbox.checked;
          actualizarContador();
        });
        const span = document.createElement("span");
        span.textContent = option.text;
        label.append(checkbox, span);
        optionsContainer.appendChild(label);
      });
      empty.hidden = disponibles.length > 0;
      actualizarContador();
    };

    const actualizar = (limpiarSeleccion = false) => {
      const codigo = region.value;
      Array.from(comunas.options).forEach((option) => {
        const pertenece = option.dataset.region === codigo;
        option.hidden = !pertenece;
        option.disabled = !pertenece;
        if (limpiarSeleccion && !pertenece) option.selected = false;
      });
      search.value = "";
      renderizar();
    };

    region.addEventListener("change", () => actualizar(true));
    search.addEventListener("input", renderizar);
    actualizar(false);
  };

  const configurarFiltroPublico = () => {
    const region = document.getElementById("id_region_filtro");
    const comuna = document.getElementById("id_comuna_filtro");
    const especialidad = document.getElementById("id_especialidad_filtro");
    if (!region || !comuna) return;
    const form = region.closest("form");

    const enviar = () => {
      form?.classList.add("is-filtering");
      form?.requestSubmit();
    };

    const actualizar = (limpiarSeleccion = false) => {
      const codigo = region.value;
      Array.from(comuna.options).forEach((option) => {
        if (!option.value) return;
        const pertenece = !codigo || option.dataset.region === codigo;
        option.hidden = !pertenece;
        option.disabled = !pertenece;
        if (limpiarSeleccion && !pertenece) option.selected = false;
      });
    };

    region.addEventListener("change", () => {
      actualizar(true);
      enviar();
    });
    comuna.addEventListener("change", enviar);
    especialidad?.addEventListener("change", enviar);
    actualizar(false);
  };

  configurarVistaPrevia();
  configurarComunasMultiples();
  configurarFiltroPublico();
})();
