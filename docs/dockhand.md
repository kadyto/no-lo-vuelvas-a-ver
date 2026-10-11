# Instalar desde el móvil con Dockhand

Usa [Dockhand de Finsys](https://dockhand.pro/). Este método sigue el mismo flujo que el stack de Listasdelacompra: pegas el Compose, defines variables y despliegas. **Docker descarga el archivo público de GitHub y construye automáticamente la imagen.** No necesitas terminal, Git en Dockhand ni una imagen publicada en GHCR.

## Preparar la carpeta desde el NAS

Crea una carpeta local para los datos con el administrador de archivos de tu NAS. Obtén su ruta absoluta real y asigna permisos de lectura/escritura a una cuenta sin privilegios. Configura `APP_UID` y `APP_GID` con sus identificadores numéricos. No uses UID 0 ni permisos 777. Consulta las opciones de cuentas/permisos del NAS si no conoces esos números.

Ejemplo genérico de Synology: `/volume1/docker/no-lo-vuelvas-a-ver/data`. En UGREEN y otros NAS usa la ruta que muestre tu sistema. La carpeta debe existir en el host Docker al que despliega Dockhand, estar en disco local y no alojarse en SMB/NFS.

## Pegar y desplegar

1. En Dockhand selecciona tu entorno Docker, abre **Stacks → New Stack** y asigna un nombre al stack.
2. Pega el contenido íntegro de [compose.dockhand.yaml](../compose.dockhand.yaml) en el editor.
3. Introduce las variables siguientes en el panel del stack. No necesitas `.env` ni `APP_IMAGE`.

| Variable | Qué introducir |
| --- | --- |
| `DATA_DIR` | Ruta absoluta a la carpeta ya creada |
| `INITIAL_ADMIN_USER` | Tu usuario elegido |
| `INITIAL_ADMIN_PASSWORD` | Tu contraseña propia de 12–256 caracteres |
| `APP_UID` y `APP_GID` | UID/GID propietario de la carpeta; por defecto ambos 10001 |
| `APP_PORT` | Puerto libre del host; por defecto 8000 |
| `COOKIE_SECURE` | `false` para HTTP privado; `true` si solo entrarás por HTTPS |
| `UPDATE_CHECK_ENABLED` | `true` para avisar de cambios disponibles; `false` para desactivar las consultas a GitHub |

4. Despliega con la opción de **construir/build** habilitada. La primera construcción necesita Internet para GitHub, Python y las dependencias; espera a que termine. No hace falta descargar una imagen de esta aplicación desde GHCR.
5. Comprueba que `library` está en ejecución y pasa a `healthy`. Abre el host en el puerto elegido e inicia sesión con tu cuenta.

Si utilizas el origen Git del administrador en vez del editor, selecciona este repositorio, referencia `main` y archivo `compose.dockhand.yaml`; conserva las mismas variables.

## Cómo actualizar

Conserva exactamente `DATA_DIR`, UID/GID y las variables de acceso. Haz primero una copia consistente siguiendo [mantenimiento](mantenimiento.md). Solicita en Dockhand **reconstruir la imagen y recrear/desplegar** el stack: descargará el código actual de `main`. Reiniciar el contenedor por sí solo no actualiza el código. El [avisador](actualizaciones.md) muestra el commit del archivo instalado y avisa si `main` ha cambiado. Las migraciones pendientes crean una copia consistente antes de modificar el esquema; cambiar de código no deshace cambios en SQLite.

Para fijar un commit revisado, sustituye el contexto por `https://github.com/<namespace>/no-lo-vuelvas-a-ver/archive/<SHA completo>.tar.gz`, y sustituye conjuntamente la carpeta de `dockerfile` y `SOURCE_DIR` por `no-lo-vuelvas-a-ver-<SHA completo>`. En un fork, adapta también el namespace y el origen OCI. Mantén los tres valores coherentes.

## Errores de construcción

- **Git no está en PATH:** usa este contexto `.tar.gz`, no una URL `.git#main`; el archivo no requiere Git en el constructor.
- **Dockerfile o requirements no encontrado:** conserva `dockerfile: no-lo-vuelvas-a-ver-main/Dockerfile` y `SOURCE_DIR: no-lo-vuelvas-a-ver-main`; GitHub coloca los archivos dentro de esa carpeta.
- **No se ha construido ninguna imagen:** habilita build/rebuild en Dockhand. Este stack no usa `APP_IMAGE` ni una imagen local previa.
- **Sin Internet durante la instalación:** la construcción inicial requiere descargar el código y dependencias. Una vez construida, la biblioteca funciona sin Internet.
- **Sin permisos en `/data`:** revisa el propietario y las ACL de la carpeta en el NAS, incluyendo permiso para crear archivos; no uses 777.

El stack `compose.yaml` sigue disponible para instalar una imagen ya construida o una futura versión pública de GHCR. `compose.dockhand.yaml` es la alternativa explícita para construcción automática desde el administrador.
