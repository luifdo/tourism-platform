# Frontend Web (PWA)

Responsable: Juan Francisco Gonzalez Pacheco (@JuanFranG)

Aplicación web progresiva en **Vue.js 3 + Workbox**: responsiva, bilingüe (ES/EN, RF-10), accesible (WCAG 2.1 AA, RNF-07) y con operación sin conexión (RNF-13, ADR-004). Consume únicamente la API del Gateway, nunca los servicios directamente.

* **Catálogo sin conexión:** caché del catálogo ya consultado (*stale-while-revalidate*) con la fecha de la última actualización; solo las teselas del mapa ya visualizadas.
* **Formularios diferidos:** perfil, reseña, oferta y cupos se guardan en IndexedDB como "Pendiente de envío" y se envían al recuperar la conexión, con `Idempotency-Key`.
* **Requieren conexión:** solicitar y confirmar reservas.

Detalle en el [Plan de Implementación](../Documents/Pages/Plan_de_Implementacion.md) §6.8.

## Ejecución

```bash
npm install
npm run dev        # desarrollo (el Service Worker solo corre en el build)
npm run build && npm run preview   # prueba de la PWA y del modo sin conexión (puerto 4173)
```

## Operación sin conexión (RNF-13)

* `vite.config.js`: Workbox precarga la aplicación (sin el video del hero) y guarda el catálogo (`/api/catalog/`, *stale-while-revalidate*) y solo las teselas OSM ya vistas.
* `src/lib/offlineQueue.js`: cola en IndexedDB para formularios diferidos. Cada envío lleva `Idempotency-Key`, las ediciones llevan `If-Match`; un 409 queda como conflicto y un 401 pide iniciar sesión. `clearLocalData()` debe llamarse al cerrar sesión.
* `src/lib/useCatalog.js`: estado del explorador. La lógica está en `application/catalog`: catálogo en vivo o, si no hay red o el catálogo no responde, la última portada guardada con su fecha.
* Solicitar y confirmar reservas requieren conexión y se deshabilitan sin ella.

## Reservas (UC10–UC13)

* Rutas: `/servicios/:id` (ficha + reserva en 4 pasos) y `/mis-reservas`.
* `src/lib/api.js` implementa el cliente de `contracts/openapi/booking.yaml` (`Idempotency-Key` al solicitar, `If-Match` al modificar, errores con el formato `Error`).
* Mientras no exista el Gateway, `VITE_API_MOCK=true` (archivo `.env`, copiado de `.env.example`; si falta, por defecto es simulado) usa `src/lib/mockBookings.js`, un servicio simulado en el navegador que respeta las reglas del contrato y de la Guía Técnica del Módulo 3. Para usar el Gateway real: `VITE_API_MOCK=false`.
* Con `VITE_API_MOCK=false` el catálogo sale de `catalog-service` (`/api/catalog/buscar`, `/servicios/{id}`, `/servicios/nombres`, `/mapa/servicios` y `/servicios/{id}/intencion-visita`): explorador con búsqueda por texto y por categoría y paginación, ficha con alertas y aviso de pagos, mapa con los servicios de la vista, nombres en *Mis reservas* y "Cómo llegar". **El catálogo real no publica el aforo en vivo** (la saturación es de analítica, solo para Admin): la barra de aforo solo aparece con el simulador. Un servicio sin fotos usa un degradado por categoría; el listado no trae imágenes.

## Instalación como app (PWA)

* `vite.config.js` define el manifest: `standalone`, `scope`/`start_url`/`id` bajo la ruta de despliegue, íconos `any` (192 y 512) y `maskable` (512), y accesos directos a *Mis reservas* y *Explorar*.
* `index.html`: `viewport-fit=cover`, `theme-color`, metadatos de iOS (`apple-mobile-web-app-*`) y `apple-touch-icon` (180 px, opaco).
* Android/Chrome/Edge: aparece el botón **Instalar app** en la barra (`InstallButton.vue`). iOS Safari: *Compartir → Añadir a pantalla de inicio*.
* El video del hero no se guarda sin conexión; en su lugar se precarga `hero-poster.jpg` (primer cuadro exacto).
* Los íconos se generaron a partir de `public/brand/logo-dark.png`.

## Arquitectura del frontend de reservas (puertos y adaptadores)

El backend usa arquitectura hexagonal (ADR-006); el módulo de reservas del frontend sigue el mismo criterio para que las reglas de negocio no dependan de Vue ni de la red.

```
src/
├── domain/booking/          Reglas puras (fechas de Bogotá, plazos, cancelación, cupos, estados). Sin Vue, sin fetch.
├── application/booking/     Casos de uso (UC10–UC13) y PUERTOS: BookingGateway, Session, BookingCache, Clock.
├── infrastructure/          ADAPTADORES que implementan los puertos:
│   ├── booking/             httpBookingGateway (Gateway real), mockBookingGateway (simulado), idbBookingCache
│   ├── catalog/             httpCatalogGateway (Gateway real), mockCatalogGateway + demoCatalogo (simulado), idbCatalogCache
│   ├── auth/                tokenSession (JWT en localStorage)
│   └── storage/             idb (IndexedDB)
├── composition.js           Raíz de composición: único lugar que elige qué adaptador implementa cada puerto
└── components/ views/ ui/   UI (Vue): solo llama a los casos de uso y muestra el resultado
```

```
UI ──► application ──► domain          infrastructure ──► (implementa los puertos de application)
```

* El dominio y la aplicación no importan librerías ni usan `fetch`, `localStorage` ni `indexedDB`; la UI no importa `infrastructure`. Lo comprueba `tests/architecture.test.js`.
* Para conectar el backend real basta `VITE_API_MOCK=false`: cambia el adaptador en `composition.js`, sin tocar casos de uso ni pantallas.
* El adaptador simulado reutiliza las reglas del dominio y responde con los códigos del contrato (`CUPOS_INSUFICIENTES`, `VERSION_DISTINTA`, `FUERA_DE_PLAZO`…).

## Autenticación (UC1, UC2, UC3, UC6) e integración con iam-service

Pantallas: `/ingresar`, `/registro` (18+ y aceptación de datos, Ley 1581), `/recuperar` y `/restablecer-contrasena`. `/mis-reservas` exige sesión y solicitar una reserva también. Misma estructura de puertos y adaptadores:

* `domain/auth`: reglas puras (política de contraseña 8–128 con letra y número, correo normalizado, nombre 2–150, redirección segura, vigencia de la sesión).
* `application/auth`: casos de uso `iniciarSesion`, `registrar` (registra e inicia sesión), `cerrarSesion`, recuperación; puertos `AuthGateway`, `SessionStore`, `LocalData`, `Clock`.
* `infrastructure/auth`: `httpAuthGateway` (iam-service), `mockAuthGateway` (simulado), `sessionStore` y `tokenSession` (JWT que usan reservas y la cola sin conexión).
* Al cerrar sesión se borran los formularios pendientes y la copia de reservas del dispositivo (SRS §3.6.6); el catálogo público se conserva.

**Contrato que se consume** (`services/iam-service`, rama `feature/iam-core`):

| Operación | Ruta | Éxito | Errores (`{ detail, code, errores? }`) |
|---|---|---|---|
| Registro | `POST /api/iam/register` | 201 usuario público | 409 `EMAIL_EN_USO` · 422 `VALIDACION` (con `errores[]`), `HABEAS_DATA_REQUERIDO`, `MAYORIA_DE_EDAD_REQUERIDA`, `PASSWORD_INVALIDA`, `NOMBRE_INVALIDO`, `ROL_NO_PERMITIDO` |
| Login | `POST /api/iam/login` | 200 `{ access_token, token_type, expires_in, usuario }` | 401 `CREDENCIALES_INVALIDAS` · 403 `CUENTA_INACTIVA` |
| Logout | `POST /api/iam/logout` (Bearer) | 204 | 401 `TOKEN_INVALIDO` · 503 `SERVICIO_NO_DISPONIBLE` |

**Diferencias con la documentación, por resolver entre el equipo** (el cliente sigue lo implementado; las rutas están en `RUTAS` de `httpAuthGateway.js`):

1. El Plan §4.1 y `gateway/README` nombran `/api/iam/auth/{login,registro,recuperar,verificar,refresh}`; el servicio expone `/api/iam/{register,login,logout}`.
2. **Refresh token** (`POST /api/iam/auth/refresh`, ya en `iam.yaml`): el access token dura 15 min y el refresh, 7 días; cada renovación entrega **los dos nuevos** y el refresh anterior muere. **Reutilizar un refresh se toma como robo y el servicio cierra la sesión**, por eso hay una sola renovación a la vez, también entre pestañas:
   * La sesión guarda `refreshToken` y su vencimiento. Se renueva sola 30 s antes de vencer (`useSession`), al volver la red o la pestaña, y ante un 401 (renueva una vez y repite la petición: `infrastructure/auth/authorizedFetch`, que usan reservas, chat y la cola sin conexión).
   * Candado `navigator.locks` (`webLocksRenovacion`; sin él, solo dentro de la pestaña) y, **dentro del candado, se relee la sesión**: si otra pestaña ya renovó, se usa lo suyo. El caso de uso está en `application/auth` (`renovarSesion`, `obtenerToken`).
   * 401 `TOKEN_INVALIDO` (vencido, revocado o reutilizado): la sesión se invalida y se pide ingresar. Un fallo pasajero (sin red, 503) **no** cierra la sesión: se reintenta cada 30 s.
   * Riesgo que el cliente no puede quitar: si el servicio rota el refresh y la respuesta se pierde por la red, el refresh guardado ya no sirve y la sesión se cierra al reintentar.
   * El refresh se guarda en `localStorage` junto al access token: un XSS lo podría leer (por eso la PWA muestra los textos del servidor como texto, nunca como HTML).
3. **La recuperación de contraseña no existe en el servicio** (UC3) ni tiene contrato. Se implementó el cliente con rutas propuestas (`POST /api/iam/auth/recuperar { email }` y `POST /api/iam/auth/restablecer { token, password }`); mientras el servicio responda 404 la interfaz informa que aún no está disponible.
4. Falta `contracts/openapi/iam.yaml` (lo cita el README del servicio) y el ForwardAuth `GET /api/iam/auth/verificar`; el servicio ya publica las llaves en `GET /api/iam/.well-known/jwks.json`.

En modo simulado (`VITE_API_MOCK=true`) hay una cuenta de ejemplo (`maria.perez@example.com`, la del README del servicio) y, como no se envía correo, la pantalla de recuperación muestra el enlace.

### Pruebas

```bash
npm test          # dominio, casos de uso (con adaptadores falsos), adaptadores y regla de dependencias
npm run test:watch
```

## Producción (contenedor)

`frontend/Dockerfile` compila la PWA con Node y la sirve con Nginx (sin privilegios, puerto 8080). En el compose de `infra/` es el servicio `frontend`, al que Traefik manda todo lo que no es de un servicio.

```bash
cd infra && docker compose up -d --build frontend
```

- **`VITE_API_MOCK` y `VITE_BASE` se fijan al compilar** (argumentos del build; por defecto `false` y `/`). Todo lo que empieza con `VITE_` queda dentro de los archivos públicos: nunca pongas claves ahí.
- `nginx.conf`: fallback a `index.html` para las rutas de Vue Router; **404** en `/internal`, `/health` y `/metrics`; **404 en JSON** para cualquier `/api/...` que ningún servicio tenga; `index.html`, `sw.js` y el manifiesto sin caché (para que se actualice la PWA) y `/assets/` con hash por un año.
- Para desarrollar con recarga en caliente: `VITE_API_MOCK=false` en `frontend/.env` y `npm run dev`; el proxy de Vite manda `/api` a `localhost:80` (el gateway, o un túnel SSH a la VM).
- **Content-Security-Policy** (`nginx.conf`): solo código propio (sin scripts en línea ni `eval`); fuentes **autoalojadas** (`@fontsource`, sin terceros), teselas de OpenStreetMap y fotos por https. Además `Permissions-Policy` y `Cross-Origin-Opener-Policy`. `nginx.conf` es una **plantilla**: la imagen sustituye `${CSP_ALMACENAMIENTO}` al arrancar (solo las variables `CSP_*`; las de nginx como `$uri` quedan intactas). En el compose vale `S3_ENDPOINT_PUBLICO`, el mismo origen de las URL firmadas con que el prestador sube fotos; sin esa variable, `http://localhost:8333`. Si cambias el dominio del almacenamiento y no la variable, la subida de fotos queda bloqueada por la política (el navegador lo dice en la consola).
- Pendiente: los manifiestos de k8s del frontend.

## Panel del prestador (UC19, UC20)

Ruta `/prestador`, solo para el rol **Prestador** (`router.js`; quien tiene otro rol vuelve al inicio, y "Mis reservas" pasa a ser solo del Turista, porque el servicio respondería 403). Dos pestañas:

* **Solicitudes** (`GET /api/bookings/prestador/solicitudes`): por defecto las pendientes, de la más urgente a la menos, con cuenta regresiva hasta `expira_en` y marca de "urgente" (≤ 6 h). **Confirmar** y **Rechazar** (el motivo de 3 a 500 caracteres es obligatorio; libera los cupos). Si la solicitud cambió (la cancelaron, venció el plazo) se muestra el motivo y se recarga la lista. Filtro por estado y por servicio.
* **Calendario** (`GET/PUT /prestador/calendario/...`): los días del servicio con totales, reservados, libres y tarifa. **Editar un día** envía la versión que se vio (`If-Match`); si cambió en el servidor se muestra **tu cambio frente a lo que hay ahora** (`version_actual` y `actual` del 409) y se elige entre reenviar con la versión nueva o dejar lo que hay. **Abrir un rango** (`POST .../rango`): días de la semana, cupos y tarifa, con la cuenta de días que se abrirían; los que ya existen se omiten. 0 cupos = día cerrado; no se baja de lo ya reservado ni se pasa del aforo oficial (`CUPOS_COMPROMETIDOS`, `SUPERA_AFORO`).
* Cada intento lleva una `Idempotency-Key` nueva (no una por reintento); `PETICION_EN_PROCESO` e `IDEMPOTENCIA_NO_DISPONIBLE` se reintentan **con la misma clave** hasta 3 veces (INTEGRACION.md §2.3). Los servicios del selector salen de `GET /api/catalog/prestador/servicios`.
* **Sin conexión**, confirmar, rechazar y editar el calendario se deshabilitan. La Guía §2 prevé editar el calendario sin conexión con la cola de envíos pendientes: **no está hecho**.
* En modo simulado un prestador atiende todos los servicios de demostración; ve solicitudes de ejemplo y lo que piden los turistas. Lo que hace se refleja en lo que ve el turista (estado de su reserva y cupos y tarifas del día).

## Perfil, oferta, reseñas, administración y Entidad

Toda la API ya existía (`contracts/openapi/`); estas pantallas la usan. Cada área tiene su **puerto** (`application/gestion/ports.js`), sus **casos de uso** (`application/gestion/useCases.js`, que validan lo que se sabe sin red), un **adaptador HTTP** (`infrastructure/gestion/httpGestionGateways.js`, sobre un cliente JSON común en `infrastructure/http/apiClient.js` que traduce los errores de iam, catalog y review a `GestionError`) y un **adaptador simulado** (`infrastructure/gestion/mockGestion.js`) para GitHub Pages. Las reglas puras (formulario de una oferta, reseñas, rangos) están en `domain/gestion/`.

| Rol | Ruta | Qué hace |
|---|---|---|
| Todos | `/perfil` | **UC4**: nombre e idioma; cambiar la contraseña (el servicio cierra todas las sesiones: se vuelve a ingresar); borrar la cuenta y los datos (Ley 1581, pide la contraseña). |
| Turista | `/mis-resenas` y la ficha | **UC15**: servicios que ya disfrutó y puede reseñar, escribir y editar su reseña. **UC39**: reportar una reseña ajena. La lectura (resumen, distribución, aspectos) es pública. |
| Prestador | `/prestador#servicios` | **UC17/UC18**: crear, editar, desactivar y reactivar ofertas. El formulario cambia con el tipo de oferta (`domain/gestion/servicio.js`), sugiere coordenadas desde una dirección y sube las fotos directo al almacenamiento con una URL firmada. Crear y editar llevan `Idempotency-Key`; editar, `If-Match`. |
| Prestador | `#resenas`, `#metricas`, `#negocio` | **UC21** responder reseñas (y reportar); **UC22** métricas por servicio; **UC37** subir RNT y RUT (PDF, JPG o PNG de hasta 5 MB) y ver el motivo si se rechazan; perfil comercial (teléfono, dirección, política de cancelación). |
| Admin | `/admin` | **UC28** cola de prestadores: abrir los documentos (enlace de 5 minutos), aprobar o rechazar con motivo por documento. **UC27** usuarios y roles. **UC29** moderar reseñas reportadas. **UC33** bitácora de auditoría con filtros. |
| Entidad y Admin | `/entidad` | **UC25** tablero y mapa de calor; **UC23** demanda (barras por estado, día/semana/mes) e intenciones de visita; **UC26** alertas oficiales por zona o servicio; **UC38** reporte CSV (siempre en español, para Excel). |

* Los accesos del menú dependen del rol (`AppNavbar.vue`); las rutas piden el rol y quien tiene otro vuelve al inicio.
* **Prestador sin aprobar:** el catálogo responde **403 `PERFIL_INACTIVO`** en todo lo suyo mientras el Admin no apruebe el RNT y el RUT. No es una falla: el panel abre directamente «Mi negocio» (la pestaña activa se desplaza a la vista en pantallas angostas), muestra un aviso con el paso a seguir y cada sección dice «Disponible cuando el Admin apruebe tu cuenta» en neutro, sin reintento (`EstadoCarga` con `aviso`). El simulador lo reproduce (salvo las cuentas `@samaland.demo`, que cuentan como aprobadas).
* **Pantalla de otro rol:** quien abre `/admin` siendo prestador vuelve al inicio con el aviso «No tienes permiso para ver esa página» (`?sinpermiso=1`, `App.vue`).
* **Usuarios → Bitácora:** cada usuario trae «Ver en la bitácora», que abre la bitácora ya filtrada por su `usuario_id` (la bitácora filtra por quien hizo el hecho).
* **`authorizedFetch` solo renueva con un 401 de token** (`TOKEN_INVALIDO` o `NO_AUTENTICADO`, o sin cuerpo legible). Un 401 con otro código —p. ej. `CREDENCIALES_INVALIDAS` al confirmar la contraseña para borrar la cuenta— se entrega tal cual: antes gastaba una rotación del refresh y repetía el `DELETE`. Pruebas en `tests/infrastructure/authorizedFetch.test.js`.
* Un **401 con código propio** (p. ej. `CREDENCIALES_INVALIDAS` al confirmar la contraseña) **no** es sesión vencida; solo `NO_AUTENTICADO` y `TOKEN_INVALIDO` mandan a ingresar.
* En modo simulado hay una cuenta de ejemplo por rol (misma contraseña, botones en `/ingresar`); el paquete de producción no las trae (`VITE_API_MOCK=false`). El simulador guarda su estado en el navegador; **no** está conectado al catálogo simulado: una oferta nueva no aparece en el explorador de ejemplo.
* `tests/i18n.test.js` comprueba que español e inglés tengan las mismas claves y que toda clave fija que usa el código exista.

## Explorador y mapa públicos (UC8, UC9, UC16)

* **Buscador de la portada**: lleva al explorador con lo escrito (`/?q=texto#catalogo`); las rutas de «Rutas ancestrales» abren el explorador con una búsqueda real.
* **Más filtros** (`/api/catalog/buscar`): zona, precio desde/hasta, fecha, personas y orden (relevancia, precio, calificación). Un precio mínimo mayor que el máximo se intercambia; `personas` sin `fecha` no se manda (el servicio respondería 400). Una búsqueda con filtros nunca se guarda como «portada» para verla sin conexión.
* **Ficha**: atributos del servicio por bloques (`domain/catalog/atributos.js`: qué incluye, horario, punto de encuentro, qué llevar, habitaciones, requisitos…), galería de fotos y reseñas.
* **Mapa**: capas opcionales de **zonas** (con su nivel de saturación) y de **alertas oficiales**, de `/mapa/zonas` y `/mapa/alertas`.
* El selector de idioma está en la cinta, en la barra fija (desde tablet) y en el menú del móvil.

**No está hecho:** editar el calendario sin conexión (cola) y subir fotos sin conexión. Las reseñas se probaron contra el servicio real solo en lectura: escribirlas exige una reserva finalizada, que el stack local no genera sin esperar la fecha.

## Seguridad (revisión OWASP Top 10:2025)

* **Service Worker**: solo guarda las rutas **públicas** del catálogo (`servicios`, `buscar`, `zonas`, `alertas`, `mapa`) y solo peticiones **sin** `Authorization`, en la caché `catalogo-publico-v2`. Antes guardaba todo `/api/catalog/`, incluidas métricas, servicios del prestador y analítica de la Entidad, y las servía a quien entrara después; la caché vieja `catalogo` se borra al arrancar (`lib/limpiezaLocal.js`). `tests/lib.limpiezaLocal.test.js` fija qué rutas se cachean y cuáles no.
* Los tokens siguen en `localStorage` (limitación conocida: un XSS tomaría la sesión). Lo mitigan la CSP sin scripts en línea y que no haya `v-html`/`innerHTML`/`eval` (se vigila con grep en la revisión); el remedio de fondo es una cookie HttpOnly desde IAM.
* Errores sin atrapar: `app.config.errorHandler`, `unhandledrejection` y `error` muestran un aviso con una referencia (`lib/errorGlobal.js`); los errores de servicio muestran su `correlation_id` cuando no se saben explicar. Las `Idempotency-Key` usan `nuevaClave()`, que no depende de `crypto.randomUUID` (no existe en HTTP no seguro).
* Las GitHub Actions de `frontend-ci.yml` y `frontend-pages.yml` van fijadas por hash de commit (con la versión en un comentario); las de los demás servicios siguen por etiqueta.

## Portada con scroll (fotogramas, no video)

La portada se mueve con el scroll dibujando en un `canvas` el fotograma que toca (`src/components/HeroScroll.vue`, `src/lib/heroFrames.js`). Antes movía el `currentTime` de un `<video>`; en **iOS con el modo de bajo consumo** (y en cualquier navegador que no deje reproducir sin gesto) el video no se movía nunca. Las imágenes se cargan siempre, en Safari, Chrome y demás.

* 120 cuadros WebP en `public/hero/d/` (1280×720, 5,4 MB) y `public/hero/m/` (406×720, el centro del cuadro, 2,3 MB). Un teléfono en vertical baja solo `m/`; lo demás, `d/`.
* Se piden por capas (inicio y final, de a 16, de a 8, de a 4, de a 2 y el resto, de a cuatro a la vez): con pocos cuadros el scroll ya mueve la imagen y se afina solo. Mientras no llega ninguno se ve el póster. Con ahorro de datos (`saveData`) solo se piden uno de cada tres; con movimiento reducido, solo el primero.
* El video original queda en `media-src/hero.mp4` (no se sirve) con las instrucciones para regenerar los cuadros.
