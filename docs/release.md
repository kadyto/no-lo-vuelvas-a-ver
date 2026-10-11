# Preparar la primera publicación

No se debe anunciar una imagen pública ni una arquitectura validada antes de comprobarlas. Esta preparación no crea tags de release ni publica imágenes en GHCR.

1. Revisa `docs/verificacion.md`, ejecuta todos los controles y examina el resultado de Actions en ambas arquitecturas. Las pruebas de imagen usan runners amd64 y arm64, no solo una construcción cruzada.
2. Verifica README, versiones, CHANGELOG y migraciones. Prueba una copia y restauración, y una instalación vacía.
3. Cuando exista una versión verificada, actualiza CHANGELOG y `pyproject.toml`, regenera el lock y crea intencionadamente la etiqueta estable `vX.Y.Z` en el commit revisado. No reutilices una etiqueta ya publicada.
4. El workflow `publish.yml` ejecuta primero `checks.yml`. Solo si pasa construye el manifiesto `linux/amd64,linux/arm64` y publica el tag de versión y `latest`. Rechaza nombres que no sean estables `v` más tres componentes numéricos.

Publica con el `GITHUB_TOKEN` del workflow y permiso `packages: write`, sin PAT personal. Los controles de pull requests tienen únicamente `contents: read`, no reciben secretos, no hacen login a GHCR y no publican. El nombre de imagen se deriva de `GITHUB_REPOSITORY` en minúsculas. Incluye etiquetas OCI de título, versión, origen, revisión y licencia. La licencia OCI MIT describe el código, no derechos sobre datos externos.

## Hacer público el paquete

Un repositorio público no garantiza un paquete público. Después de la primera publicación, abre el paquete Container en GitHub, entra en sus ajustes y cambia su visibilidad a **Public**; comprueba la vinculación con el repositorio y el acceso de Actions. Consulta [la documentación oficial de GHCR](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry) y [visibilidad y permisos](https://docs.github.com/en/packages/learn-github-packages/about-permissions-for-github-packages).

Comprueba la descarga desde un cliente sin credenciales. Este ejemplo usa configuración temporal vacía y no altera tus credenciales habituales; sustituye namespace y versión por valores reales del paquete:

```sh
anon_config_dir="$(mktemp -d)"
docker --config "$anon_config_dir" pull ghcr.io/<namespace>/no-lo-vuelvas-a-ver:vX.Y.Z
```

Comprueba después el manifiesto con `docker buildx imagetools inspect` y haz un smoke en equipos o runners de ambas arquitecturas. No hay soporte anunciado para ARM de 32 bits. Si falla el acceso anónimo, revisa la visibilidad y el tag antes de compartir instrucciones de instalación por imagen.

Para despliegue inicial sin GHCR sigue el build local del README. La instalación con Compose usa `image:` siempre; la alternativa de construcción local es un comando independiente.
