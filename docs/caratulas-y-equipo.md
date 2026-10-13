# Carátulas, dirección y reparto

Al obtener los datos de una ficha de FilmAffinity, la vista previa incluye la dirección y el reparto disponibles y, si se identifica una imagen admitida, su carátula. Revisa los nombres y guarda para confirmar. Puedes desmarcar **Conservar carátula** y completar los nombres a mano, uno por línea.

Para una obra ya registrada: **Editar ficha → Obtener carátula y equipo → Guardar cambios**. Se conserva la nota, reseña, fecha de visionado, Recomendable y categorías que contiene el formulario. La consulta y la vista previa no cambian la ficha. No se actualiza toda la biblioteca en segundo plano.

Activa `FILMAFFINITY_ENABLED=true` para permitir estas consultas. Si falla la ficha, sigue disponible el formulario manual. Si se obtiene la ficha pero falla la carátula, se pueden guardar los nombres y demás metadatos; una imagen ya guardada se conserva salvo que la desmarques. No se resuelven captchas ni se evaden bloqueos.

## Navegar por una persona

Pulsa un nombre en **Dirección** o **Reparto** para ver las obras de tu biblioteca en las que participa. El filtro se combina con búsqueda, tipo, categorías y valoración y conserva la paginación y el regreso desde una ficha. **Quitar filtro de persona** elimina solo esa dimensión.

Esto consulta la biblioteca local, no la filmografía completa de FilmAffinity. Una obra antigua sin dirección/reparto aún no participa en esas coincidencias: obtén sus datos explícitamente o añade los nombres a mano. Se importa el reparto incluido en la ficha; no se sigue «ver todos los créditos» ni se rastrean páginas de personas.

Los IDs de personas presentes en la información obtenida se conservan. Nombres iguales con IDs distintos siguen siendo personas distintas. Los nombres introducidos a mano se comparan sin espacios repetidos, mayúsculas ni tildes; reutilizan una identidad conocida solo cuando es inequívoca. Cuando hay varios homónimos no se decide automáticamente cuál de ellos es.

## Guardado y seguridad

El backend descarga únicamente imágenes HTTPS de `pics.filmaffinity.com` identificadas en la ficha. Rechaza credenciales, puertos, otros destinos, rutas no admitidas, resolución privada y redirecciones fuera del dominio. Máximo tres redirecciones y 3 MiB descargados. La verificación TLS sigue activa.

Solo se decodifican JPEG, PNG y WebP estáticos; se rechazan HTML, SVG, animaciones e imágenes de más de 12 millones de píxeles. Se guarda una copia JPEG sin metadatos, de hasta 400 × 600 píxeles y 180.000 bytes. Se conserva URL de origen y fecha de obtención. La copia se sirve desde la aplicación y requiere iniciar sesión; el navegador no contacta a FilmAffinity al consultar las fichas.

Las imágenes se deduplican por contenido y se almacenan en SQLite. Las no utilizadas por ninguna ficha ni caché activa se eliminan al obtener nuevos metadatos o borrar fichas; borrar una carátula de una obra no elimina una imagen compartida por otra. La caché de ficha y carátula dura siete días. Las consultas nuevas mantienen los límites globales del autocompletado; una actualización explícita de una ficha puede renovar esa caché.

No se copian críticas, sinopsis extensas ni puntuaciones ajenas. Las carátulas y metadatos mantienen sus derechos de terceros y no quedan cubiertos por MIT.

## Exportación y actualización

JSON v2 incluye dirección, reparto con sus IDs y cada carátula en base64 con origen y fecha. La importación admite v1 y v2, valida también las imágenes y sigue omitiendo los conflictos por defecto. Límite de 50 MiB; una biblioteca mayor puede conservarse mediante la copia SQLite consistente. CSV incluye nombres/IDs y el origen de la carátula, pero no el binario de la imagen.

La copia SQLite y su restauración incluyen las carátulas y las relaciones entre personas y obras; no hay carpetas de imágenes que copiar por separado. La migración 0003 añade tablas/columna sin recrear las fichas, hace caducar la caché antigua y mantiene las valoraciones. El arranque crea una copia consistente antes de aplicarla. Para volver a una versión con esquema anterior, detén la aplicación y restaura esa copia, siguiendo [mantenimiento](mantenimiento.md).
