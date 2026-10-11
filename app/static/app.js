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
