# Copias, restauración y mantenimiento

## Copia consistente

```sh
docker compose exec library python -m app.cli backup /data/backups/copia-con-nombre-unico.sqlite3
```

La API `sqlite3.Connection.backup` incluye una vista consistente aunque haya escrituras en WAL. El comando comprueba integridad y rechaza un destino ya existente. Para más copias cambia el nombre. Guarda una segunda copia fuera de `/data` usando las herramientas de archivos del NAS; el archivo producido por backup ya es independiente y no necesita WAL/SHM. Contiene la biblioteca y el hash de la cuenta: protege su acceso.

No copies solamente `library.sqlite3` mientras la aplicación escribe. Una exportación JSON es un respaldo portable de datos funcionales, sin acceso ni sesiones; la copia SQLite conserva la instalación completa. Comprueba periódicamente una restauración en una carpeta e instancia separadas, con puerto distinto.

## Restaurar con la aplicación detenida

1. Detén el servicio con `docker compose stop library` o la opción correspondiente del administrador. Confirma que ninguna otra instancia usa esa carpeta.
2. Conserva la carpeta actual completa como respaldo aparte, incluidos `library.sqlite3`, `library.sqlite3-wal` y `library.sqlite3-shm` si existen.
3. Prepara una **carpeta nueva y vacía**, con el UID/GID y permisos documentados. Copia la copia consistente a esa carpeta con nombre `library.sqlite3`. No mezcles una copia nueva con WAL/SHM antiguos.
4. Cambia `DATA_DIR` a esa carpeta. Usa una imagen compatible con el esquema de la copia. Recrea el servicio con `docker compose up -d`.
5. Comprueba salud, acceso, notas, alias, categorías y reseñas. La cuenta de la copia se conserva; los valores `INITIAL_ADMIN_*` no la reemplazan.

Este procedimiento evita comandos destructivos sobre los datos existentes. Si solo dispones de JSON, inicia una instalación nueva con una cuenta propia e importa desde Ajustes; las fichas, notas y fechas se conservarán, las credenciales no forman parte del JSON.

## Actualizar

1. Revisa CHANGELOG y cambios de esquema. Anota el tag actual.
2. Ejecuta y guarda una copia consistente con nombre nuevo antes de actualizar.
3. Cambia `APP_IMAGE` a un tag concreto publicado y verificado. En CLI: `docker compose pull` seguido de `docker compose up -d`. En los administradores actualiza las variables y recrea el stack conservando `DATA_DIR`.
4. Comprueba logs y salud. Ante migraciones pendientes, el arranque crea automáticamente una copia verificada en `/data/backups/before-<revision>-<fecha>.sqlite3` antes de `alembic upgrade head`; si la copia falla, el arranque falla antes de migrar. Sin cambios de esquema no crea copias repetidas.
5. Comprueba tus datos y exporta JSON si lo deseas.

La actualización normal no borra datos ni ejecuta `down -v`. No se recrean tablas en cada arranque. Las migraciones están versionadas y sus definiciones no importan modelos que puedan cambiar en el futuro.

Para volver a una versión anterior comprueba su esquema esperado. Si no es compatible, restaura la copia previa con la aplicación detenida y usa la imagen anterior. Cambiar solo el tag **no revierte la base de datos**. No se promete un downgrade destructivo ni se borran tablas para facilitarlo.

## Exportación e importación

En Ajustes descarga JSON de formato `no-lo-vuelvas-a-ver`, versión 1. Incluye UUID, identidad FilmAffinity, títulos, alias/idiomas, categorías globales y asociaciones, fechas internas, visionado, nota nullable, anotaciones, Recomendable y procedencia de metadatos. CSV conserva UTF-8, saltos de línea y campos entrecomillados; añade un apóstrofo si un campo puede interpretarse como fórmula.

La importación admite hasta 10 MiB, valida todos los campos y rechaza IDs/UUID duplicados dentro del archivo. La vista previa dura 15 minutos, pertenece a la sesión que la creó y se consume al confirmar. Muestra como máximo 100 filas, pero el recuento y validación incluyen todo el archivo. Al confirmar se vuelve a comprobar la identidad en una transacción de escritura. Opciones: omitir fichas existentes (por defecto) o cancelar toda la importación si hay conflictos. Nunca se sobrescriben datos silenciosamente. Coincidencias solo por título no se fusionan. Un archivo inválido no añade ni categorías ni fichas.

## Problemas habituales

| Síntoma | Comprobación y solución |
| --- | --- |
| Puerto ocupado | Cambia `APP_PORT` por uno libre y recrea el servicio |
| Carpeta inexistente | Crea la ruta absoluta en el host de destino; Compose no la crea |
| `Permission denied` o SQLite readonly | Comprueba UID/GID, propietario, permisos y ACL de esa carpeta, también permisos para WAL/SHM y backups; no uses 777 |
| Contenedor no saludable | Mira `docker compose ps` y `docker compose logs --tail=80 library`; comprueba inicialización, permisos y espacio libre |
| Solicita contraseña inicial | Primera cuenta requiere variables propias; mínimo 12 caracteres. No hay credenciales predeterminadas |
| Cambiar la variable no cambia la clave | Es intencional: solo inicializa una cuenta ausente. Usa Ajustes para cambiarla |
| Cookies no permiten entrar por HTTP | Para HTTP privado usa `COOKIE_SECURE=false`; para HTTPS usa `true` y accede por HTTPS |
| Demasiados intentos de acceso | Límite global de 10 intentos cada 5 minutos por instalación; espera a que expire |
| No puede autocompletar | Desactivado por defecto; URL e ID siguen funcionando. Completa la ficha manualmente |
| 403, 429, captcha o HTML cambiado | No se eluden bloqueos; usa el formulario manual y revisa las reglas oficiales antes de habilitar consultas |
| Imagen no encontrada o acceso denegado | Antes de primera release usa build local. Después comprueba tag real y visibilidad pública del paquete GHCR |
| Se agotó el espacio en `/data` | Libera espacio fuera de la base activa y conserva copias verificadas; no borres WAL/SHM con la app en marcha |

Los límites de acceso son globales para una instalación de una cuenta. Reiniciar conserva los contadores y sesiones en SQLite. No hay recuperación pública de contraseña ni correo saliente en V1: conserva tu contraseña y una copia segura; la restauración preserva el hash, no recupera una contraseña olvidada.
