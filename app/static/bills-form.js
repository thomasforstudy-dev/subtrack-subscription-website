// Add/remove actual posted item controls. Row numbers may have gaps after removal.
(() => {
  const body = document.querySelector('[data-bill-lines]');
  const add = document.querySelector('[data-add-line]');
  const status = document.querySelector('[data-line-status]');
  if (!body || !add) return;
  const maximum = Number(body.dataset.maxLines);
  function sync() {
    const count = body.querySelectorAll('[data-bill-line]').length;
    add.disabled = count >= maximum;
    if (status) status.textContent = count + ' / ' + maximum + ' items';
  }
  add.addEventListener('click', () => {
    const used = new Set(Array.from(body.querySelectorAll('[data-bill-line]'), row => Number(row.dataset.billLine)));
    let number = 1;
    while (used.has(number) && number <= maximum) number++;
    if (number > maximum) return;
    const row = document.createElement('tr');
    row.dataset.billLine = String(number);
    [['name', 'Item'], ['qty', 'Quantity'], ['price', 'Unit price']].forEach(([field, label]) => {
      const cell = document.createElement('td');
      const input = document.createElement('input');
      input.name = 'item_' + field + '_' + number;
      input.setAttribute('aria-label', label + ' ' + number);
      if (field === 'name') input.maxLength = 300;
      else input.inputMode = 'decimal';
      cell.append(input);
      row.append(cell);
    });
    const cell = document.createElement('td');
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'button secondary btn-sm';
    remove.dataset.removeLine = '';
    remove.setAttribute('aria-label', 'Remove item ' + number);
    remove.textContent = 'Remove';
    cell.append(remove);
    row.append(cell);
    body.append(row);
    sync();
    row.querySelector('input').focus();
  });
  body.addEventListener('click', event => {
    const remove = event.target.closest('[data-remove-line]');
    if (!remove) return;
    remove.closest('[data-bill-line]').remove();
    sync();
    add.focus();
  });
  sync();
})();
