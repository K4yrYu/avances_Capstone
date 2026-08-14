function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
const csrftoken = getCookie('csrftoken');


document.addEventListener("DOMContentLoaded", function () {
    const escapeHtml = window.FerremasSecurity?.escapeHtml || (value =>
        String(value ?? "").replace(/[&<>"']/g, character => ({
            "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
        })[character])
    );
    const safeUrl = window.FerremasSecurity?.safeUrl || (value => {
        try {
            const url = new URL(String(value ?? ""), window.location.origin);
            return ['http:', 'https:'].includes(url.protocol) ? escapeHtml(url.href) : "";
        } catch (_error) {
            return "";
        }
    });
    const apiUrl = "/productos/api/";

    // === CARGAR PRODUCTOS EN CRUD (TABLA) ===
    fetch(apiUrl)
        .then(response => {
            if (!response.ok) {
                throw new Error("Error al obtener los productos");
            }
            return response.json();
        })
        .then(productos => {
            const tabla = document.getElementById("tabla-productos");
            if (tabla) {
                tabla.innerHTML = ""; // Limpiar contenido anterior

                productos.forEach(producto => {
                    const fila = `
                        <tr>
                            <td>${escapeHtml(producto.nombre)}</td>
                            <td>$${producto.precio}</td>
                            <td>${escapeHtml(producto.descripcion)}</td>
                            <td>
                                <img src="${safeUrl(producto.imagen)}" alt="${escapeHtml(producto.nombre)}" class="product-photo" 
                                     style="width: 80px; height: 80px; object-fit: cover; border-radius: 5px;">
                            </td>
                            <td>
                                <button onclick="eliminarProducto(${producto.id})" class="btn btn-danger btn-sm">
                                    <i class="fas fa-trash"></i> Eliminar
                                </button>
                                <a href="/productos/editar/${producto.id}/" class="btn btn-warning btn-sm">
                                    <i class="fas fa-pencil-alt"></i> Editar
                                </a>
                            </td>
                        </tr>
                    `;
                    tabla.insertAdjacentHTML("beforeend", fila);
                });
            }
        })
        .catch(error => {
            console.error("Error al cargar los productos:", error);
        });

});
