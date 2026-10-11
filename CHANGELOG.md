# Cambios

## Sin publicar — preparación de V1 (0.1.0)

- Inicio más compacto, sin el bloque introductorio; enlace al proyecto, versión instalada y aviso de nuevas releases o cambios en main. Comprobación opcional, asíncrona y cacheada, sin datos de la biblioteca ni instalación automática.
- El adaptador FilmAffinity usa ahora Requests Session, como changedetection.io, con sus cabeceras predeterminadas y cookies efímeras; conserva el dominio móvil de la consulta, la identidad canónica y la verificación TLS. Diagnóstico de retos sin atribuirlos a la falta de JavaScript y sin falsos positivos por títulos que contengan «captcha».
- Compatibilidad HTTP de FilmAffinity tras revisar changedetection.io: User-Agent de su cliente básico, aceptación de HTML e idioma español, hasta tres redirecciones HTTPS validadas de la misma ficha y diagnóstico de `cf-mitigated: challenge`. Sin navegador adicional ni reintentos de bloqueos.
- Consulta puntual directa de FilmAffinity: se elimina la petición y evaluación de `robots.txt`; se mantienen caché, límites y diagnóstico de errores de la ficha.
- URLs móviles `m.filmaffinity.com` con la misma identidad canónica; diagnóstico de bloqueos por código HTTP, recurso y señales de comprobación humana, con enlace para completar a mano.
- Alternativa `compose.dockhand.yaml`: construcción automática desde un archivo HTTPS de GitHub, sin terminal ni Git en Dockhand; guía de instalación desde el móvil.
- Biblioteca compartida de películas y series con cuenta única, notas opcionales, reseñas, categorías, alias y Recomendable.
- Identidad FilmAffinity única, alta manual y adaptador opcional limitado con vista previa.
- Búsqueda normalizada paginada y filtros; prueba con 10.000 obras sintéticas.
- Sesiones persistentes con expiración, CSRF, contraseña scrypt y límite de acceso.
- Exportaciones JSON/CSV e importación transaccional con conflictos explícitos.
- Migraciones Alembic, copia consistente y protección antes de actualizar esquema.
- Imagen Docker, Compose para NAS, guías Dockhand/Portainer y workflows de controles/publicación GHCR.

No hay una release etiquetada ni una imagen GHCR anunciada por este documento.
