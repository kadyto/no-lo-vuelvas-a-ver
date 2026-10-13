# Verificación de la primera versión

Comprobaciones ejecutadas del 11 al 13 de octubre de 2026 en un entorno Linux amd64 con Python 3.12.14, Docker Engine y Compose v2. No representan una prueba en un NAS concreto ni una publicación en GHCR.

## Carátulas locales, dirección y reparto

El 13 de octubre se añadieron imágenes guardadas en SQLite, personas con identidad externa y créditos de dirección/reparto. La migración 0003 conserva las fichas y valoraciones y expira la caché anterior. JSON v2 incluye las imágenes y personas y admite archivos v1.

Las comprobaciones aisladas locales pasaron **79 pruebas en 1,55 s** (cuatro pruebas HTTP excluidas): parser, descarga simulada, destinos/direcciones/redirecciones no admitidos, formatos y tamaños inválidos, imágenes animadas, homónimos, filtros por persona, independencia de la valoración, exportación/importación, copia y restauración de carátulas y créditos, limpieza de caché y migración desde un esquema congelado. Lint, formato, diff y exportación reproducible del lock pasan.

La [ejecución completa previa a main](https://github.com/kadyto/no-lo-vuelvas-a-ver/actions/runs/38450941451) del commit `a374b49e2da51ceff62795deabec10bb974574fd` terminó correctamente: **148 pruebas pasan en amd64 (14,37 s) y arm64 (12,86 s)**. Ambos Compose, imágenes normales y de archivo, smoke de acceso/persistencia/backup/UID-GID y revisión del archivo público pasan. Con 10.000 obras/alias la búsqueda midió 15,4/15,4/26,5 ms (mínimo/mediana/máximo) en amd64 y 16,6/16,8/27,6 ms en arm64, con 24 fichas por página.

La [ejecución en main](https://github.com/kadyto/no-lo-vuelvas-a-ver/actions/runs/38452756733), commit `db1d121f5f9b0f1fd08b6a905a0d86822d8b259b`, también terminó correctamente: 148 pruebas en amd64 (10,50 s) y arm64 (11,49 s), Compose, imágenes, persistencia, backup, archivo y flujos de navegador. Las búsquedas de 10.000 obras/alias midieron 8,7/8,8/17,0 ms en amd64 y 16,3/16,3/26,9 ms en arm64.

El navegador de amd64 pasó los flujos de escritorio y móvil, incluida actualización con vista previa de una ficha existente, imagen local, dirección/reparto, filtro por persona combinado con tipo y regreso conservando filtros. Se inspeccionaron las capturas ficticias del nuevo diseño. Usa `tests.preview_server` exclusivamente para el script explícito de navegador: su proveedor sintético no se incluye en la imagen de producción y nunca consulta FilmAffinity. El HTTP de producción, bloqueos de un NAS concreto y la disponibilidad futura del HTML/carátulas no quedan garantizados por estas pruebas.

## Icono y paleta cinematográfica

El 12 de octubre se sustituyó la marca de letra por un icono original generado para la aplicación: ojo, bobina y cinta de cine en azul y amarillo. Cabecera y favicon utilizan PNG locales con transparencia, de 256 × 256 (72.869 bytes) y 64 × 64 (7.405 bytes). Se eliminó «Hay historias que se quedan» y se simplificó el acceso.

Lint y comprobación del diff pasan. Se midió el contraste de las combinaciones principales: blanco/azul de botones **6,82:1**, azul oscuro/amarillo **10,51:1**, texto secundario/fondo **5,78:1** y blanco/azul de cabecera **10,43:1**. Todas superan 4,5:1 para texto normal. Estas mediciones no sustituyen la revisión de teclado y foco del navegador.

La [ejecución completa de Controles](https://github.com/kadyto/no-lo-vuelvas-a-ver/actions/runs/38307250060) del commit `2193ee82031c22318c1b96f27a52494fa2af4e51` terminó correctamente: **125 pruebas pasan en amd64 (11,77 s) y arm64 (9,22 s)**; lint, lock, ambos Compose, imágenes normales y desde archivo, smoke de acceso/persistencia/backup/UID-GID y revisión del archivo público pasan. El navegador de amd64 pasó acceso, carga del icono/favicon local y todos los flujos de escritorio y móvil, sin desplazamiento horizontal. Las capturas del README y del acceso corresponden a esa ejecución con datos ficticios.

## Aviso de actualizaciones e inicio compacto

Se retiró el bloque introductorio y se añadió enlace a GitHub, identificación de la versión instalada y aviso opcional de actualizaciones. Las pruebas aisladas del avisador pasaron **23 casos en 0,10 s**: releases estables comparadas numéricamente, cambios de main, caché de seis horas, reintento tras fallo, ausencia de identificador, desactivación, datos inválidos, respuestas grandes, redirecciones rechazadas, concurrencia y metadatos de git archive. No consultan GitHub real. Lint, formato y comprobación de diff pasan.

La [ejecución completa de Controles](https://github.com/kadyto/no-lo-vuelvas-a-ver/actions/runs/38164759703) del commit `83a8f5ef5d1f53b0aac9d062ac19b6f292e4fd0b` terminó correctamente: **125 pruebas pasan en amd64 (12,19 s) y arm64 (10,11 s)**. Lint, lock, ambos Compose, imágenes normales y desde archivo, smoke de acceso/persistencia/backup/UID-GID y lectura de revisión en la imagen pasan en ambas arquitecturas. La búsqueda con 10.000 obras y alias midió 14,1/14,4/23,1 ms (mínimo/mediana/máximo) en amd64 y 14,4/14,7/22,8 ms en arm64, con 24 fichas por página.

El flujo de navegador de escritorio y móvil pasó en amd64, incluyendo una actualización ficticia y un fallo de conexión interceptados sin consultar GitHub. Las capturas del README se descargaron de esa ejecución y se inspeccionaron. La [comprobación del archivo público real](https://github.com/kadyto/no-lo-vuelvas-a-ver/actions/runs/38167869285) verifica que el tar descargado de GitHub para el commit `db8b1f8ee3e7795f85941fa8613fa6ec8cdcac0d` contiene exactamente ese SHA: `export-subst` funciona en el archivo que utiliza el stack. Es un control de integración explícito de CI tras publicar; las pruebas habituales siguen usando respuestas simuladas. No se ha publicado una release ni una imagen en GHCR.

## Revisión del cliente Requests

El adaptador usa Requests Session y mantiene el dominio solicitado. Las pruebas normales usan un transporte Requests sintético y nunca consultan FilmAffinity. La batería aislada del adaptador pasó **56 pruebas en 0,46 s**, incluyendo cabeceras predeterminadas, dominio móvil, identidad canónica, rechazo de destinos/IDs incorrectos, cookies de redirección, cuerpos de redirección sin descargar y diagnóstico sin atribuir el bloqueo a JavaScript.

La [ejecución completa de Controles](https://github.com/kadyto/no-lo-vuelvas-a-ver/actions/runs/38158132083) del commit `60172873d56233f61ea3dc870ddf20abe29ce6bd` terminó correctamente: **101 pruebas pasan en amd64 (10,25 s) y arm64 (8,75 s)**; lint, lock, ambos Compose, imágenes, smoke de acceso/persistencia/backup/UID-GID y construcción desde archivo pasan en ambas arquitecturas. El flujo visual de escritorio y móvil también pasó en amd64. La búsqueda de 10.000 obras y alias midió 11,2/12,6/20,9 ms (mínimo/mediana/máximo) en amd64 y 15,3/15,4/23,5 ms en arm64, con 24 fichas por página. Las pruebas completas locales quedaron interrumpidas y se completaron en Actions; no se presentan como ejecutadas localmente.

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

Advertencia de herramientas: el cliente de pruebas actual de Starlette avisa de la futura preferencia por httpx2. Las pruebas pasan con el httpx fijado para el cliente de pruebas; el adaptador FilmAffinity usa ahora Requests. No se afirma que no exista ningún aviso de dependencias.

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
