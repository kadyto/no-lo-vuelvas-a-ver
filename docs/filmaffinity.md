# FilmAffinity: identidad y consulta opcional

Proyecto independiente, sin relación oficial con FilmAffinity. No se presupone una API oficial ni se requiere una API no oficial.

`FILMAFFINITY_ENABLED=false` es el valor inicial. Ponlo en `true` para habilitar la consulta puntual de la ficha solicitada. El adaptador consulta directamente esa ficha y no solicita ni evalúa `robots.txt`. No hay clave, pago ni cuenta externa obligatoria.

Las [condiciones públicas oficiales](https://www.filmaffinity.com/es/private.php) se revisaron el 11 de octubre de 2026. La integración es independiente y no presupone una API ni una autorización oficial de FilmAffinity.

## Identidad offline

Solo se aceptan URLs `http` o `https` de los dominios exactos `www.filmaffinity.com`, `m.filmaffinity.com` y `filmaffinity.com`, con ruta `/<idioma de dos letras>/film<ID numérico>.html`. Se rechazan credenciales, puertos explícitos, otros destinos, controles y rutas extra. Parámetros, fragmentos, subdominio móvil e idioma no alteran el ID. Se conserva una URL canónica `https://www.filmaffinity.com/es/film<ID>.html` y una restricción UNIQUE en SQLite. Distintos IDs pueden tener el mismo título. La consulta conserva el dominio exacto admitido de la URL pegada, construyendo una ficha española HTTPS a partir del ID; un enlace `m.` se consulta inicialmente en `m.`, aunque su identidad guardada siga siendo canónica. Las redirecciones posteriores se validan.

Se busca una ficha existente antes de llamar al proveedor y antes de guardar. Un conflicto muestra «Ya está en tu biblioteca», nota, Recomendable y enlace a la ficha. La base evita también duplicados simultáneos. El formulario manual puede usar URL sin autocompletado, o excepcionalmente omitirla; entonces avisa de posibles coincidencias por títulos/alias, año y tipo, que el usuario decide.

## Autocompletado a petición

El botón explícito inicia una consulta backend. El destino inicial se construye a partir del ID validado; nunca se obtiene la URL arbitraria enviada por el navegador. Se siguen como máximo tres redirecciones HTTPS a los dominios exactos admitidos y a una ficha con el mismo ID. Cada destino se valida y se comprueba su resolución pública antes de consultarlo. Se rechazan otros destinos, cambios de ID, bucles y respuestas finales distintas de 200.

Cada intento empieza por la ficha española del dominio solicitado, sin una petición previa a `robots.txt`. Solo puede continuar por las redirecciones de esa misma ficha; no sigue enlaces relacionados. Se usa **Requests Session**, como el cliente HTTP básico de changedetection.io, con su User-Agent inicial y las cabeceras HTTP predeterminadas de Requests. La sesión conserva cookies únicamente durante esa consulta y sus redirecciones; no se guardan en SQLite ni se reutilizan entre altas. Se mantiene la verificación TLS. Los metadatos se cachean siete días en SQLite. Límite global: una consulta nueva cada 15 segundos y 30 por hora. Timeout de conexión de 4 segundos y de lectura de 8 segundos por petición; límite descomprimido de 1,5 MB por ficha. Los resultados cacheados pueden usarse sin otra consulta. Los cuerpos de las redirecciones se cierran sin descargarlos.

El parser intenta leer título español, título original, año, tipo y hasta doce géneros explícitos. Si no identifica el tipo, el usuario lo completa. No traduce títulos, no añade alias inventados y no promete obtener todas las versiones idiomáticas. V1 no extrae alias cuando no hay una fuente inequívoca. Los géneros son sugerencias; solo se asignan categorías elegidas por el usuario. La vista previa debe confirmarse para guardar. Se conserva proveedor, fecha de obtención y una instantánea mínima de metadatos; los campos editados pueden diferir de ella.

No se copian sinopsis, carteles, críticas, reseñas ajenas ni puntuaciones del proveedor. No hay rastreo del catálogo, enlaces relacionados, búsqueda externa por pulsación ni sincronización de fondo. No se evaden captcha ni bloqueos 403/429. La biblioteca sigue funcionando sin Internet.

## Diagnóstico de un bloqueo y captcha

El aviso muestra el código HTTP, el cliente Requests y el dominio consultado. Un **403** significa acceso rechazado; por sí solo no demuestra que exista un captcha. Se inspecciona como máximo un prefijo de 32 KiB de una respuesta 403 para detectar señales explícitas de comprobación humana, sin mostrar ni guardar el HTML recibido. También se reconoce la cabecera explícita `cf-mitigated: challenge`, incluso con HTTP 200; una cabecera genérica `Server: cloudflare` o la palabra «captcha» en el título de una película no basta para afirmar que hay un reto. Detectar un reto no identifica la causa del bloqueo ni demuestra que ejecutar JavaScript vaya a resolverlo. Un **429** indica límite de consultas. Las redirecciones no permitidas se explican y no se consultan. No se reintentan automáticamente respuestas 403/429. Un fallo de `robots.txt` no afecta al autocompletado porque la aplicación no lo consulta.

Cuando hay un fallo, el formulario conserva la URL canónica, su identidad y tus campos, y ofrece **Abrir ficha en FilmAffinity**. Puedes consultar los datos en esa pestaña y completarlos a mano.

Una comprobación humana puede estar asociada a cookies, a la sesión del navegador o a la IP de salida. Resolverla al abrir FilmAffinity en tu navegador no garantiza que autorice también la petición del contenedor: son sesiones diferentes. Esta V1 no incrusta el captcha ni transfiere cookies o tokens del navegador al servidor. No se modifica la identidad ni se guarda automáticamente una obra por fallar el autocompletado.

## Comparación con changedetection.io

Se revisó su código público el 11 de octubre de 2026. No tiene un único mecanismo de extracción:

- El [cliente HTTP básico](https://github.com/dgtlmoon/changedetection.io/blob/master/changedetectionio/content_fetchers/requests.py) usa Requests, sesiones y redirecciones. Su [configuración inicial](https://github.com/dgtlmoon/changedetection.io/blob/master/changedetectionio/model/App.py) define un User-Agent de Chrome, aunque este modo no ejecuta JavaScript. Nuestro adaptador ahora usa también Requests Session, ese User-Agent y sus cabeceras predeterminadas, y acepta redirecciones limitadas de la misma ficha. Mantiene la verificación TLS.
- El [modo Playwright](https://github.com/dgtlmoon/changedetection.io/blob/master/changedetectionio/content_fetchers/playwright.py) conecta a un navegador Chrome, carga la página, ejecuta JavaScript y espera antes de extraer el HTML. Su [Compose](https://github.com/dgtlmoon/changedetection.io/blob/master/docker-compose.yml) muestra un servicio de navegador opcional. Esta aplicación sigue siendo un contenedor ligero y no incorpora Chrome en producción.

Un mismo User-Agent no hace idénticos dos clientes: la preparación HTTP y la negociación TLS de HTTPX y Requests pueden diferir. La corrección anterior solo había alineado parte de las cabeceras; esta revisión cambia el cliente real y evita sustituir `m.` por `www.` antes de hacer la petición. No se ha confirmado qué diferencia provoca el 403 de una instalación particular; no se promete superar un reto, captcha o bloqueo por IP.

Para comprobarlo en tu NAS, reconstruye y recrea el stack de Dockhand, conserva `FILMAFFINITY_ENABLED=true` y solicita explícitamente la misma ficha. Si falla, el aviso indica el código y si hay señales de comprobación humana. En changedetection, compara la misma URL y revisa si el método es **Basic fast Plaintext/HTTP Client** o un navegador **Chrome/Playwright**. Las pruebas automáticas de este proyecto siguen usando respuestas simuladas.

El adaptador está en `app/filmaffinity.py`, separado de `app/library.py`. Las pruebas usan muestras mínimas sintéticas y un transporte Requests simulado (`tests/requests_transport.py`); ejercitan la preparación real de peticiones, cabeceras, cookies y lectura en streaming sin acceder a FilmAffinity. Los metadatos de terceros mantienen sus derechos y no se presentan como contenidos licenciados bajo MIT.
