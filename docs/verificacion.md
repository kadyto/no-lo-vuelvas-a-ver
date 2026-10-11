# Verificación de la primera versión

Comprobaciones ejecutadas el 11 de octubre de 2026 en un entorno Linux amd64 con Python 3.12.14, Docker Engine y Compose v2. No representan una prueba en un NAS concreto ni una publicación en GHCR.

## Revisión del cliente Requests

El adaptador usa Requests Session y mantiene el dominio solicitado. Las pruebas normales usan un transporte Requests sintético y nunca consultan FilmAffinity. La batería aislada del adaptador pasó **56 pruebas en 0,46 s**, incluyendo cabeceras predeterminadas, dominio móvil, identidad canónica, rechazo de destinos/IDs incorrectos, cookies de redirección, cuerpos de redirección sin descargar y diagnóstico sin atribuir el bloqueo a JavaScript. La batería completa y las imágenes de esta revisión se verifican mediante el workflow Controles.

En una comprobación manual puntual desde el entorno de desarrollo, HTTPX y Requests obtuvieron HTTP 200 y HTML de ficha en la URL española de `www`; Requests recibió HTTP 302 de `m` hacia esa misma ficha de `www`. Se mantuvo la verificación TLS, no se guardó el HTML remoto ni se cargó ninguna obra real en la biblioteca. Esta comprobación no reproduce el 403 de otro equipo ni demuestra su causa. No forma parte de la suite automática ni garantiza disponibilidad futura.

## Corrección anterior de compatibilidad HTTP

Tras comparar el código de changedetection.io, se ejecutó `pytest -q tests/test_security_metadata.py -k 'not auth_csrf_escape_cookie and not login_limits_logout_change_password and not password_change'`: **48 pruebas pasan en 0,86 s**, usando exclusivamente HTML sintético y MockTransport. Cubren cabeceras, redirecciones de la misma ficha, rechazo de otros destinos/IDs/puertos/credenciales, resolución privada en una redirección, bucles limitados, bloqueo sin reintentos y comprobación humana indicada por cabecera. `ruff check`, `ruff format --check` y `git diff --check` pasan.

La [ejecución completa de Controles](https://github.com/kadyto/no-lo-vuelvas-a-ver/actions/runs/38156404189), correspondiente al commit `53845a8fa595e640aa56974d6dcb344270f40ae0`, terminó correctamente: **92 pruebas pasan en amd64 (11,24 s) y arm64 (8,48 s)**, lint, lock y ambos Compose válidos, imágenes construidas, smoke de acceso/persistencia/backup/UID-GID, construcción desde archivo y smoke correctos en ambas arquitecturas. El navegador de amd64 también pasó los flujos de escritorio y móvil. La búsqueda de 10.000 obras y alias midió 14,5/14,7/23,4 ms (mínimo/mediana/máximo) en amd64 y 15,2/15,4/23,8 ms en arm64, con 24 fichas por página.

El cliente ASGI se bloqueó bajo las restricciones de sockets de este entorno y se detuvo esa ejecución local; la batería completa se verificó en Actions. Las comprobaciones locales completas e imágenes de la tabla siguiente corresponden a la revisión anterior. La prueba HTTP real de FilmAffinity quedó interrumpida sin un resultado HTTP verificable; no se afirma que la corrección resuelva un bloqueo real ni que se haya probado el modo de una instalación concreta de changedetection. Estas construcciones de CI no publican imágenes en GHCR.

## Ejecutado

| Comprobación | Comando | Resultado |
| --- | --- | --- |
| Dependencias fijadas | `uv sync --frozen` | Instalación correcta, lock completo y exportación con hashes |
| Comportamiento y conservación | `uv run --frozen pytest -q` | **74 pruebas pasan**, 11,21 s en la última batería completa |
| URL móvil y diagnóstico FilmAffinity | Incluidas en la batería anterior, con MockTransport | Identidad `m`/`www`/sin subdominio, duplicados y búsqueda; consulta directa sin robots, códigos HTTP, captcha simulado y prefijo de diagnóstico limitado |
| Calidad y formato | `uv run --frozen ruff check app migrations tests scripts`; `ruff format --check` | Correcto |
| Lock de Docker | Exportación `uv export --frozen --no-dev --format requirements-txt --no-header` y comparación | Coincide con `requirements.lock` |
| Imagen amd64 | `docker build -t no-lo-vuelvas-a-ver:test .` | Construcción correcta; en el entorno gestionado se añadió la CA del proxy como secreto efímero de BuildKit |
| Compose | `uv run --frozen python scripts/check_compose.py` | Correcto; un servicio, imagen, bind explícito, variables exigidas, healthcheck |
| Compose de Dockhand | `uv run --frozen python scripts/check_compose.py compose.dockhand.yaml` | Correcto; construcción desde archivo HTTPS, un servicio, ruta de datos y credenciales exigidas |
| Archivo con carpeta raíz de GitHub | `uv run --frozen python tests/smoke_archive.py` | Construcción amd64 y smoke correctos; rutas COPY, acceso, reinicio, recreación, persistencia, backup y UID/GID |
| Contexto HTTPS público real | `docker build --build-arg SOURCE_DIR=no-lo-vuelvas-a-ver-main -f no-lo-vuelvas-a-ver-main/Dockerfile https://github.com/kadyto/no-lo-vuelvas-a-ver/archive/refs/heads/main.tar.gz` | Construcción amd64 correcta desde la URL exacta del stack; smoke de acceso, persistencia y backup correcto sobre esa imagen |
| Contenedor | `uv run --frozen python tests/smoke_image.py no-lo-vuelvas-a-ver:test` | Acceso, alta, reinicio, recreación, datos persistentes, copia SQLite y UID/GID personalizados correctos |
| Navegador | `uv run --frozen python tests/browser_smoke.py` con Chromium | Escritorio 1440 px y móvil 390 px: acceso, alta, búsqueda, regreso conservando búsqueda, edición, Recomendable, borrado, fallback manual y ausencia de desplazamiento horizontal |
| Capturas | Script de navegador con biblioteca temporal sintética | Generadas e inspeccionadas; disponibles en README y `docs/ejemplo-*.png` |

La suite usa directorios temporales y obras sintéticas, no carga datos reales en el producto ni consulta FilmAffinity. Cubre notas nulas y decimales, rechazo de notas inválidas, URLs de distintos idiomas, altas simultáneas, homónimos, búsquedas por títulos/alias/tildes/ID/URL, categorías y borrado de asociaciones, independencia de Recomendable, importación/exportación y conflictos, copia/restauración, migraciones, acceso, CSRF, escape y destinos externos rechazados.

Con **10.000 obras y 10.000 alias sintéticos**, cinco consultas de varias palabras y tildes en la segunda página midieron **13,5 ms mínimo, 15,2 ms mediana y 23,5 ms máximo**, con 24 fichas por página. Incluye recuento, consulta y carga de relaciones de esa página. Es una medición de este entorno, no una garantía para otro hardware. El navegador nunca descarga toda la base para buscar. La suite tiene un límite amplio de regresión de 5 s por consulta.

Advertencia de herramientas: el cliente de pruebas actual de Starlette avisa de la futura preferencia por httpx2. Las 74 pruebas pasan con el httpx fijado y usado también por el adaptador; no se afirma que no exista ningún aviso de dependencias.

## CI ejecutada y publicación pendiente

- `checks.yml`: controles para pull requests y `main`, pruebas e imagen en runners nativos amd64 y arm64, sin publicación ni secretos. [Los nombres de runners se verificaron en documentación oficial](https://docs.github.com/en/actions/reference/runners/github-hosted-runners). [La ejecución de Actions](https://github.com/kadyto/no-lo-vuelvas-a-ver/actions/runs/38148342140) del commit `bf28aa5d23d298645787d87ce951d18b58be96c0` terminó correctamente en ambas arquitecturas: dependencias, tests, lint, lock, ambos Compose, construcción normal y desde archivo, smoke y persistencia. El flujo de navegador también pasó en el runner amd64.
- `publish.yml`: controles previos y publicación multiarch en GHCR únicamente al crear una etiqueta estable `vX.Y.Z`, usando GITHUB_TOKEN. No se ha creado ninguna etiqueta ni release.
- La prueba local de imagen es amd64; arm64 se verificó en el runner nativo de Actions. Esto no equivale a una prueba en todos los modelos de NAS.
- GHCR: primera publicación, cambio de visibilidad a pública, manifiesto y descarga anónima. No existe una imagen pública verificada por esta entrega.
- Las comprobaciones de este informe no incluyen una instalación en un NAS real, Dockhand ni Portainer. Sus instrucciones y variables se contrastaron con documentación oficial y el Compose real se validó con Docker Compose.
- La alternativa de Dockhand se probó con un tar de carpeta anidada y también descargando el archivo público real de `main` tras subir el commit `bf28aa5d23d298645787d87ce951d18b58be96c0`. Se construyó la imagen y pasó el smoke de persistencia. No requiere Git ni una imagen GHCR; requiere Internet durante la construcción. La ejecución dentro del administrador sigue pendiente de una instalación real.
- Autocompletado real de FilmAffinity: desactivado por defecto y consulta directa a la ficha cuando se habilita, sin peticiones a robots. Parser y respuestas HTTP probados con muestras/simulaciones, sin afirmar permiso ni compatibilidad permanente con el HTML real.

## Repetir la revisión visual

```sh
uv sync --frozen
uv run --frozen playwright install chromium
uv run --frozen python tests/browser_smoke.py
```

El script arranca su propio servidor, crea datos ficticios solo en una carpeta temporal y genera capturas en `test-results/`, que Git ignora. También puedes iniciar una instalación vacía y revisar a 390 px y escritorio: teclado/foco, alta manual, nota vacía, filtros combinados, edición, confirmación de borrado de ficha/categoría e importación con vista previa.
