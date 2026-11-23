# PWA HU29

La PWA se monta desde `main.tsx`, fuera del enrutador de páginas y sin leer la sesión.
Nombre español, inicio `/dashboard`, scope `/`, modo `standalone` y PNG 192/512/maskable.
El icono de libro deja el dibujo dentro de la zona segura circular del icono maskable.
Los PNG se regeneran con `python src/pwa/generate-icons.py` (Pillow; solo herramienta de desarrollo).

## Política de privacidad

`public/sw.js` precarga exclusivamente `offline.html`, el manifest y los tres iconos.
Solo cachea además favicon/sprite conocidos y recursos con hash bajo `/assets/` de este
origen (JS, CSS, fuentes e imágenes), con MIME apropiado, respuesta 200, sin redirecciones
ni `Cache-Control: private/no-store`. Descarga los estáticos con `credentials: omit`.
Nunca guarda HTML de navegación, respuestas de API, autenticación, PDF, JSON de datos,
peticiones con Authorization/Cookie/Range, métodos distintos de GET o URLs con query.
El tráfico no permitido va a red con `cache: no-store`, sin fallback; terceros no son
interceptados. La aplicación y el backend deben mantener su política HTTP de no almacenar
información privada también fuera del service worker.

Al navegar sin conexión a `/` o rutas de `/dashboard` sin parámetros ni extensiones,
muestra una página pública genérica, sin datos, tokens, código de sesión ni nombres de
usuarios. No es una copia del portal. No hay almacenamiento de datos familiares, tokens,
preferencias de instalación o sesión en CacheStorage/localStorage/IndexedDB. Cerrar sesión
no requiere borrar el caché: contiene únicamente archivos públicos, compartidos entre cuentas.
El worker elimina solo versiones antiguas con prefijo `edugestion-hu29-static-`.

La UI ofrece instalación tras `beforeinstallprompt`, permite descartarla durante esta
visita y consume cada evento una sola vez. En iOS ofrece instrucciones de Safari.
El aviso offline explica que la información requiere red. Una nueva versión espera;
«Actualizar aplicación» solicita activación y recarga cuando cambia el controlador.
La UI recuerda guardar el trabajo antes de actualizar.

## Producción y comprobación manual

- Compilar con `npm run build`. `public/` se copia al build de Vite.
- Servir por HTTPS. `http://localhost`/loopback se admite para pruebas locales.
- Registro automático solo en build de producción. Para una prueba explícita en Vite
  local: `$env:VITE_PWA_DEV='true'; npm run dev`. No habilitar esa variable habitualmente;
  eliminar registros de prueba desde DevTools al terminar.
- `/sw.js` debe responder JavaScript con `Cache-Control: no-cache`; nunca redirigir a
  autenticación ni servirle `index.html`. `/manifest.webmanifest` debe responder JSON de
  manifest y `offline.html`/iconos deben ser estáticos públicos, sin encabezados private/no-store.
- Configurar SPA fallback para `/dashboard` a `index.html`, respetando `/api` como API.
- Incrementar `VERSION` en `sw.js` al cambiar el worker o el shell offline. El navegador
  comprueba actualizaciones al registrar y al volver online; no se activa una actualización
  sobre la sesión actual hasta que el usuario la solicita o cierra todas sus pestañas.
- Abrir el build, recargar para quedar controlado, revisar Manifest/Service Workers en
  DevTools y verificar los iconos e instalación. En iOS usar Safari y «Compartir».
- Con DevTools Offline, abrir `/dashboard`: debe aparecer «Sin conexión». Una petición
  a `/api/portal/familia/` o PDF debe fallar por red, jamás devolver HTML ni datos anteriores.
  CacheStorage solo debe mostrar el shell público y estáticos del propio origen, sin queries.
- Reconectar y entrar con otra cuenta: no debe aparecer información de la cuenta anterior.
  El estado de red del navegador es orientativo; los errores API se gestionan en cada página.

## Verificación automatizada

`npm run test:run -- src/pwa` ejecuta el archivo worker real en una VM Node con fetch y
CacheStorage controlados: instalación, activación, limpieza acotada, estáticos offline,
exclusiones y bypass de caché HTTP. También prueba UI de instalar/descartar/iOS/offline/
actualizar, el registro limitado a entornos autorizados y las dimensiones PNG del manifest.
No sustituye la instalación en dispositivos ni el smoke HTTPS del despliegue.

Referencias primarias consultadas:
[ciclo del worker](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API/Using_Service_Workers),
[instalación](https://developer.mozilla.org/en-US/docs/Web/API/BeforeInstallPromptEvent),
[actualización](https://developer.mozilla.org/en-US/docs/Web/API/ServiceWorkerRegistration/updatefound_event).
