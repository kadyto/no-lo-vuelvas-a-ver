# Instalación práctica

## 1. Comprobar el host

Docker Engine y Compose v2 deben funcionar en el host al que despliega el administrador. Comprueba `docker info`, `docker compose version` y `uname -m`: x86_64 corresponde a amd64; aarch64 a arm64. Una máquina que ejecuta Dockhand o Portainer puede gestionar otro host: la imagen local y `DATA_DIR` tienen que existir en el **host de destino**.

Usa una sola instancia por biblioteca. Para instalaciones independientes elige distintas carpetas y puertos; el Compose no fuerza un `container_name`.

## Carpeta de datos y permisos

Elige una carpeta local del NAS. Ejemplo **genérico de Synology**: `/volume1/docker/no-lo-vuelvas-a-ver/data`. No representa una instalación real. En UGREEN y otros NAS usa la ruta real que muestra tu sistema; no existe una ruta universal que esta guía pueda inventar.

Obtén el UID/GID de la cuenta que gestionará los archivos con `id` o `id nombre-de-cuenta` en el host. La imagen usa `10001:10001` por defecto, pero el stack permite `APP_UID` y `APP_GID` numéricos mediante `user:`. No implementa PUID/PGID. La cuenta debe poder leer y escribir SQLite y crear los ficheros WAL/SHM y las copias.

Estos comandos son un ejemplo adaptable; sustituye la ruta y los números antes de ejecutarlos. No los apuntes a una carpeta que contenga otros proyectos:

```sh
sudo mkdir -p /ruta/absoluta/elegida/data
sudo chown 10001:10001 /ruta/absoluta/elegida/data
sudo chmod 700 /ruta/absoluta/elegida/data
```

En NAS con ACL administra también los permisos de esa carpeta desde su interfaz. Nunca resuelvas errores con `chmod 777`. Compose exige que la carpeta exista y no la crea como root. La aplicación crea archivos con umask 077. Los datos persistentes están exclusivamente bajo `/data`; las descargas van al navegador. No se monta `docker.sock`, no hay privilegios ni modo host.

La base debe residir en almacenamiento local del host Docker. No montes el archivo SQLite desde SMB/NFS, no lo compartas entre varios hosts y no ejecutes varios workers sobre una misma carpeta.

## 2. Elegir imagen

**Desde Dockhand sin terminal:** usa [compose.dockhand.yaml](../compose.dockhand.yaml) y [la guía móvil](dockhand.md). Docker construye automáticamente desde un archivo HTTPS de GitHub; no necesita Git en el constructor ni una imagen pública en GHCR. Las alternativas siguientes son para `compose.yaml`, el stack de instalación por imagen.

**Aún sin publicación:** descarga o clona este repositorio en el host Docker de destino, entra en su carpeta y ejecuta:

```sh
docker build -t no-lo-vuelvas-a-ver:local .
```

En el stack elige `APP_IMAGE=no-lo-vuelvas-a-ver:local`. Esta alternativa es independiente de GHCR; el Compose sigue usando `image:`, no `build:`. Desactiva opciones del administrador como forzar pull o comprobar una imagen remota al desplegar. Si el administrador no permite usar imágenes locales, completa primero la publicación pública descrita en [release.md](release.md).

**Con GHCR público:** copia el nombre del paquete real y fija un tag verificado: `ghcr.io/<namespace>/no-lo-vuelvas-a-ver:vX.Y.Z`. No sustituyas automáticamente por `latest` al actualizar. Un repositorio público no garantiza un paquete público; comprueba la descarga anónima.

## 3. Dockhand (Finsys)

Estas instrucciones corresponden al producto [dockhand.pro](https://dockhand.pro/) y su [manual oficial](https://dockhand.pro/manual/), no a otro producto con nombre parecido.

1. Selecciona el entorno Docker de destino y abre **Stacks → New Stack**.
2. Asigna un nombre libre, por ejemplo el slug `no-lo-vuelvas-a-ver`, y pega `compose.dockhand.yaml` para construir automáticamente desde HTTPS; usa `compose.yaml` si ya dispones de una imagen.
3. Añade `DATA_DIR`, `INITIAL_ADMIN_USER`, `INITIAL_ADMIN_PASSWORD`, `APP_UID`, `APP_GID` y `APP_PORT` en las variables. Las tres primeras son obligatorias. `APP_IMAGE` solo es necesario para `compose.yaml`.
4. Con `compose.dockhand.yaml` habilita construir/build. Para una imagen local ya construida evita forzar su descarga. Despliega y revisa estado y logs.
5. Abre el host en el puerto elegido e inicia sesión. Crea una obra ficticia, reinicia el contenedor y confirma que sigue ahí; después elimínala desde la aplicación.

Como alternativa crea el stack con origen **Git**, la URL de este repositorio, referencia `main` y archivo `compose.dockhand.yaml` para construcción automática o `compose.yaml` para imagen. Define sus variables en Dockhand, incluidas las opciones del entorno que despliega. No necesitas añadir un `.env` privado al repositorio. Según la versión, el administrador puede guardar overrides internamente; conserva sus variables cuando actualices.

## 4. Portainer

Sigue la [documentación oficial de creación de stacks](https://docs.portainer.io/user/docker/stacks/add) para un entorno **Docker Standalone**:

1. **Stacks → Add stack → Web editor**. Asigna nombre y pega `compose.yaml`.
2. Añade las variables del README en **Environment variables**. No uses `stack.env`: la interpolación ya está en el Compose.
3. Si elegiste una imagen local, evita forzar pull. Pulsa **Deploy the stack** y comprueba salud y logs.
4. Abre el puerto elegido e inicia sesión.

La alternativa **Git repository** usa la URL del repositorio, referencia `refs/heads/main` y ruta `compose.yaml`; configura las mismas variables en Portainer. La guía no cubre Swarm. Portainer y Dockhand son alternativas: no hace falta instalar ambos ni incluir ninguno como servicio de esta app.

## 5. Docker Compose por CLI

Copia `.env.example` como `.env`, limita sus permisos con `chmod 600 .env` y completa los valores. Para contraseñas con `$` u otros caracteres especiales en `.env`, usa comillas simples según la [interpolación oficial de Compose](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/). En los editores de administradores, introduce el valor literal en su panel de variables.

```sh
docker compose config --quiet
docker compose up -d
docker compose ps
docker compose logs --tail=80 library
```

No compartas una configuración renderizada que contenga secretos. La aplicación no escribe contraseñas en sus logs. El primer arranque exige un usuario y una contraseña propios, crea las ocho categorías iniciales y aplica migraciones sin borrar tablas.

## HTTP privado y HTTPS opcional

Para HTTP en una red privada usa `COOKIE_SECURE=false`. Las cookies siguen siendo HttpOnly y SameSite=Lax; CSRF se verifica en cada operación POST. El puerto del host es configurable y el proceso escucha en `0.0.0.0:8000` dentro del contenedor.

Tras un proxy que termina HTTPS usa `COOKIE_SECURE=true` y entra siempre por HTTPS. El proxy debe enviar las peticiones al puerto del contenedor y admitir cargas de al menos 11 MiB para importación. No hace falta confiar en cabeceras reenviadas: la aplicación no genera redirecciones absolutas ni usa esas cabeceras para límites de acceso. Uvicorn arranca con `--no-proxy-headers`. Mantén el acceso directo al puerto limitado a la red apropiada y no añadas dominios o topología ajenos a tu instalación a este repositorio.

Los enlaces a FilmAffinity son externos y explícitos. La interfaz y toda la edición local funcionan aunque no haya conexión.
