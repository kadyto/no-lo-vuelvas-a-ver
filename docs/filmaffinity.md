# FilmAffinity: identidad y consulta opcional

Proyecto independiente, sin relación oficial con FilmAffinity. No se presupone una API oficial ni se requiere una API no oficial.

Se revisaron las [condiciones públicas oficiales](https://www.filmaffinity.com/es/private.php) el 11 de octubre de 2026. No aportaron una autorización explícita para esta integración y no se pudo verificar [robots.txt](https://www.filmaffinity.com/robots.txt) mediante la herramienta de consulta disponible. Por eso `FILMAFFINITY_ENABLED=false` es el valor inicial. No afirmamos que robots permita el acceso, ni que la ausencia de una prohibición sea una autorización.

Antes de habilitar el adaptador, el administrador debe verificar las condiciones y, cuando corresponda, obtener permiso del proveedor. `FILMAFFINITY_ENABLED=true` expresa esa decisión de la instalación; no evita la comprobación de robots en tiempo de consulta. Si las condiciones cambian, vuelve a desactivarlo. No hay clave, pago ni cuenta externa obligatoria.

## Identidad offline

Solo se aceptan URLs `http` o `https` de los dominios exactos `www.filmaffinity.com` y `filmaffinity.com`, con ruta `/<idioma de dos letras>/film<ID numérico>.html`. Se rechazan credenciales, puertos explícitos, otros destinos, controles y rutas extra. Parámetros, fragmentos e idioma no alteran el ID. Se conserva una URL canónica `https://www.filmaffinity.com/es/film<ID>.html` y una restricción UNIQUE en SQLite. Distintos IDs pueden tener el mismo título.

Se busca una ficha existente antes de llamar al proveedor y antes de guardar. Un conflicto muestra «Ya está en tu biblioteca», nota, Recomendable y enlace a la ficha. La base evita también duplicados simultáneos. El formulario manual puede usar URL sin autocompletado, o excepcionalmente omitirla; entonces avisa de posibles coincidencias por títulos/alias, año y tipo, que el usuario decide.

## Autocompletado a petición

El botón explícito inicia una consulta backend. El destino se construye a partir del ID validado; nunca se obtiene la URL arbitraria enviada por el navegador. No se siguen redirecciones. Se rechazan resoluciones a direcciones no públicas, errores y respuestas distintas de 200.

Se comprueba robots con una caché de 24 horas; si no se puede obtener o impide la consulta, se pasa a manual. Los metadatos se cachean siete días en SQLite. Límite global: una consulta nueva cada 15 segundos y 30 por hora. Timeout de conexión de 4 segundos y de lectura de 8 segundos; límite descomprimido de 1,5 MB por ficha y 100 KB para robots. Los resultados cacheados pueden usarse sin otra consulta.

El parser intenta leer título español, título original, año, tipo y hasta doce géneros explícitos. Si no identifica el tipo, el usuario lo completa. No traduce títulos, no añade alias inventados y no promete obtener todas las versiones idiomáticas. V1 no extrae alias cuando no hay una fuente inequívoca. Los géneros son sugerencias; solo se asignan categorías elegidas por el usuario. La vista previa debe confirmarse para guardar. Se conserva proveedor, fecha de obtención y una instantánea mínima de metadatos; los campos editados pueden diferir de ella.

No se copian sinopsis, carteles, críticas, reseñas ajenas ni puntuaciones del proveedor. No hay rastreo del catálogo, enlaces relacionados, búsqueda externa por pulsación ni sincronización de fondo. No se evaden captcha ni bloqueos 403/429. La biblioteca sigue funcionando sin Internet.

El adaptador está en `app/filmaffinity.py`, separado de `app/library.py`. Las pruebas usan muestras mínimas sintéticas y `httpx.MockTransport`; las pruebas normales no acceden a FilmAffinity. Los metadatos de terceros mantienen sus derechos y no se presentan como contenidos licenciados bajo MIT.
