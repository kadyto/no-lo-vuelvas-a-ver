# Enlace al proyecto y aviso de actualizaciones

El pie de página enlaza al proyecto público en GitHub, muestra la versión instalada y, después de iniciar sesión, avisa si hay una actualización. La consulta se hace en el servidor y de forma asíncrona respecto a la biblioteca; no retrasa la búsqueda ni la edición. No instala cambios ni modifica SQLite.

`UPDATE_CHECK_ENABLED=true` es el valor predeterminado. La aplicación consulta únicamente metadatos públicos del repositorio, sin claves, cuentas externas, cookies de GitHub ni datos de tu biblioteca. La conexión requiere Internet; la biblioteca sigue funcionando sin él. Puedes desactivar las consultas con `UPDATE_CHECK_ENABLED=false` en las variables del stack. Ambos Compose incluyen esa variable y no necesitan un archivo `.env` en Dockhand o Portainer.

La caché es compartida por todos los accesos de una instancia: como máximo una comprobación cada seis horas mientras se usa la aplicación. No hay un proceso de sondeo en segundo plano cuando nadie la utiliza. Si falla la conexión, GitHub limita las peticiones o devuelve datos inválidos, se muestra que no se pudo comprobar y se espera quince minutos antes de otro intento. Reiniciar la aplicación vacía esta caché. Los timeouts y el tamaño de respuesta están limitados; no se siguen redirecciones del API.

## Imágenes de versiones estables

El workflow de publicación incorpora `VERSION=vX.Y.Z` y `REVISION=<commit>` a la imagen, tanto en etiquetas OCI como en las variables internas `APP_VERSION` y `APP_REVISION`. El avisador compara numéricamente con la [última release estable publicada en GitHub](https://docs.github.com/en/rest/releases/releases#get-the-latest-release), excluyendo borradores y prereleases. El enlace lleva a esa release. Si aún no existen releases, lo indica; no inventa una versión disponible.

Crear solo un tag o publicar una imagen en GHCR no crea automáticamente una GitHub Release. El mantenimiento del proyecto debe publicar también la release después de verificar la imagen. Esta tarea no crea ningún tag, release ni imagen pública.

## Construcción desde main en Dockhand

El archivo de código contiene el commit exacto mediante [git archive y export-subst](https://git-scm.com/docs/gitattributes#_export_subst), configurado en `.gitattributes` para `app/_archive_revision.txt`. El código leído de ese archivo identifica el snapshot descargado; no se consulta `main` durante el build para atribuirle una revisión que podría corresponder a otro código. No hace falta Git dentro del contenedor.

El aviso compara ese commit con la referencia pública `main` del mismo proyecto. Si difiere muestra **Actualización disponible en main** y un enlace a la comparación de cambios. Esto indica cambios del repositorio, que pueden incluir documentación; no los presenta como una release estable.

Para aplicar el cambio, haz una copia consistente y solicita **reconstruir la imagen y recrear/desplegar el stack** en Dockhand. Conserva `DATA_DIR`, UID/GID y las variables de acceso. Reiniciar solamente mantiene el código de la imagen anterior. Consulta [mantenimiento](mantenimiento.md) para migraciones y restauración.

## Desarrollo y forks

Un build local sin revisión declarada y sin un archivo exportado válido se muestra como **Desarrollo** y **Versión instalada sin identificador**. No afirma estar al día. Para construir desde un checkout limpio, proporciona `--build-arg REVISION=<SHA completo>`; para una versión estable añade también `--build-arg VERSION=vX.Y.Z`.

`SOURCE` en el Dockerfile configura `APP_SOURCE`: el enlace al proyecto y el repositorio a consultar. En un fork, utiliza su URL HTTPS de GitHub. Solo se aceptan URLs de repositorio de `github.com` con dos componentes y sin credenciales, puertos, query o fragmento; la conexión backend sigue limitada a `api.github.com`. Si el origen no es válido se utiliza el proyecto original. No configures `APP_VERSION` o `APP_REVISION` en el stack para fingir una versión distinta del código instalado.
