# Desarrollo

- Interfaz y documentos principales en español. Respeta el trabajo y la rama solicitada por el usuario.
- Un contenedor, una instancia, un worker, SQLite local en `/data`; ningún servicio externo obligatorio.
- No incluir datos personales, secretos, bibliotecas reales ni detalles de instalaciones del propietario.
- Modelos en `app/models.py`, negocio/búsqueda en `app/library.py`, adaptador externo en `app/filmaffinity.py`, transferencias en `app/transfers.py`.
- No usar `create_all` en el arranque ni borrar tablas para migrar. Añadir revisiones Alembic congeladas y probar conservación y copia previa.
- Mantener UNIQUE para FilmAffinity, notas nullable y separadas de Recomendable. Nunca borrar valoraciones al importar metadatos.
- Sin red real a FilmAffinity en pruebas: usar HTML sintético y MockTransport.
- Verificar: `uv sync --frozen`, `uv run --frozen ruff check app migrations tests scripts`, `uv run --frozen pytest -q`.
- Con Docker: validar Compose con `scripts/check_compose.py`, construir y ejecutar `tests/smoke_image.py`; navegador con `tests/browser_smoke.py`.
- Tras cambiar dependencias: `uv lock`, `uv export --frozen --no-dev --format requirements-txt --no-header --output-file requirements.lock --quiet` y repetir controles afectados.
- Actualizar guías y `docs/verificacion.md` con resultados reales. No crear tags ni publicar releases sin una versión verificada y autorización.
