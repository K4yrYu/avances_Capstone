(() => {
  'use strict';

  const detail = document.getElementById('dashboard-sales-detail');
  const columns = document.querySelectorAll('.dashboard-sales-column');
  if (!detail || !columns.length) return;

  const labels = [
    ['Producto', 'producto'],
    ['Categoría', 'categoria'],
    ['Vendidas', 'vendidas'],
    ['Stock actual', 'stock'],
    ['Rotación', 'rotacion'],
    ['Compra sugerida', 'sugerida'],
  ];

  const showDetail = (column) => {
    detail.replaceChildren();
    const list = document.createElement('dl');

    labels.forEach(([label, key]) => {
      const wrapper = document.createElement('div');
      const term = document.createElement('dt');
      const description = document.createElement('dd');
      term.textContent = label;
      description.textContent = column.dataset[key] || '—';
      wrapper.append(term, description);
      list.appendChild(wrapper);
    });

    detail.appendChild(list);
    columns.forEach((item) => item.classList.toggle('is-selected', item === column));
  };

  columns.forEach((column) => {
    column.addEventListener('click', () => showDetail(column));
  });
})();
