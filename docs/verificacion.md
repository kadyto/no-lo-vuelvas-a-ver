# Verificación de la primera versión

Comprobaciones ejecutadas el 11 de octubre de 2026 en un entorno Linux amd64 con Python 3.12.14, Docker Engine y Compose v2. No representan una prueba en un NAS concreto ni una publicación en GHCR.

## Ejecutado

| Comprobación | Comando | Resultado |
| --- | --- | --- |
| Dependencias fijadas | `uv sync --frozen` | Instalación correcta, lock completo y exportación con hashes |
| Comportamiento y conservación | `uv run --frozen pytest -q` | **59 pruebas pasan**, 10,27 s en la última batería completa |
| Calidad y formato | `uv run --frozen ruff check app migrations tests scripts`; `ruff format --check` | Correcto |
| Lock de Docker | Exportación `uv export --frozen --no-dev --format requirements-txt --no-header` y comparación | Coincide con `requirements.lock` |
| Imagen amd64 | `docker build -t no-lo-vuelvas-a-ver:test .` | Construcción correcta; en el entorno gestionado se añadió la CA del proxy como secreto efímero de BuildKit |
| Compose | `uv run --frozen python scripts/check_compose.py` | Correcto; un servicio, imagen, bind explícito, variables exigidas, healthcheck |
| Contenedor | `uv run --frozen python tests/smoke_image.py no-lo-vuelvas-a-ver:test` | Acceso, alta, reinicio, recreación, datos persistentes, copia SQLite y UID/GID personalizados correctos |
| Navegador | `uv run --frozen python tests/browser_smoke.py` con Chromium | Escritorio 1440 px y móvil 390 px: acceso, alta, búsqueda, regreso conservando búsqueda, edición, Recomendable, borrado, fallback manual y ausencia de desplazamiento horizontal |
| Capturas | Script de navegador con biblioteca temporal sintética | Generadas e inspeccionadas; disponibles en README y `docs/ejemplo-*.png` |

La suite usa directorios temporales y obras sintéticas, no carga datos reales en el producto ni consulta FilmAffinity. Cubre notas nulas y decimales, rechazo de notas inválidas, URLs de distintos idiomas, altas simultáneas, homónimos, búsquedas por títulos/alias/tildes/ID/URL, categorías y borrado de asociaciones, independencia de Recomendable, importación/exportación y conflictos, copia/restauración, migraciones, acceso, CSRF, escape y destinos externos rechazados.

Con **10.000 obras y 10.000 alias sintéticos**, cinco consultas de varias palabras y tildes en la segunda página midieron **13,8 ms mínimo, 17,4 ms mediana y 26,8 ms máximo**, con 24 fichas por página. Incluye recuento, consulta y carga de relaciones de esa página. Es una medición de este entorno, no una garantía para otro hardware. El navegador nunca descarga toda la base para buscar. La suite tiene un límite amplio de regresión de 5 s por consulta.

Advertencia de herramientas: el cliente de pruebas actual de Starlette avisa de la futura preferencia por httpx2. Las 59 pruebas pasan con el httpx fijado y usado también por el adaptador; no se afirma que no exista ningún aviso de dependencias.

## Preparado y pendiente de ejecución remota

- `checks.yml`: controles para pull requests y `main`, pruebas e imagen en runners nativos amd64 y arm64, sin publicación ni secretos. [Los nombres de runners se verificaron en documentación oficial](https://docs.github.com/en/actions/reference/runners/github-hosted-runners).
- `publish.yml`: controles previos y publicación multiarch en GHCR únicamente al crear una etiqueta estable `vX.Y.Z`, usando GITHUB_TOKEN. No se ha creado ninguna etiqueta ni release.
- La ejecución de Actions debe revisarse en GitHub tras la subida. La prueba local de imagen es amd64; **arm64 no se anuncia como validada localmente**.
- GHCR: primera publicación, cambio de visibilidad a pública, manifiesto y descarga anónima. No existe una imagen pública verificada por esta entrega.
- No se ha desplegado en un NAS real, Dockhand ni Portainer. Sus instrucciones y variables se contrastaron con documentación oficial y el Compose real se validó con Docker Compose.
- Autocompletado real de FilmAffinity: desactivado por defecto. Condiciones revisadas; robots no verificable en la consulta de documentación. Parser y respuestas HTTP probados con muestras/simulaciones, sin afirmar permiso ni compatibilidad permanente con el HTML real.

## Repetir la revisión visual

```sh
uv sync --frozen
uv run --frozen playwright install chromium
uv run --frozen python tests/browser_smoke.py
```

El script arranca su propio servidor, crea datos ficticios solo en una carpeta temporal y genera capturas en `test-results/`, que Git ignora. También puedes iniciar una instalación vacía y revisar a 390 px y escritorio: teclado/foco, alta manual, nota vacía, filtros combinados, edición, confirmación de borrado de ficha/categoría e importación con vista previa.
