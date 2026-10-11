// Navigation and search use server GETs: a late async response cannot replace a newer query.
document.querySelectorAll('form[data-busy]').forEach(form => {
  form.addEventListener('submit', event => {
    const button = event.submitter;
    if (button) {
      button.textContent = button.formAction.includes('/metadata') ? 'Comprobando…' : 'Procesando…';
      button.setAttribute('aria-busy', 'true');
    }
  });
});

// Only the local server contacts GitHub; checking never blocks library navigation.
document.querySelectorAll('[data-update-notice]').forEach(async notice => {
  const status = notice.querySelector('[data-update-status]');
  const link = notice.querySelector('[data-update-link]');
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 7000);
  try {
    const response = await fetch('/updates', {credentials: 'same-origin', cache: 'no-store', signal: controller.signal});
    if (!response.ok) throw new Error('Unavailable');
    const result = await response.json();
    if (result.status === 'available') {
      link.href = result.url;
      link.textContent = result.message;
      link.hidden = false;
      status.textContent = '';
    } else {
      status.textContent = result.message;
      link.hidden = true;
    }
  } catch {
    status.textContent = 'No se pudieron comprobar las actualizaciones';
    link.hidden = true;
  } finally {
    clearTimeout(timer);
  }
});
