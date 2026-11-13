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
- Pendiente: Content-Security-Policy y los manifiestos de k8s del frontend.

## Panel del prestador (UC19, UC20)

Ruta `/prestador`, solo para el rol **Prestador** (`router.js`; quien tiene otro rol vuelve al inicio, y "Mis reservas" pasa a ser solo del Turista, porque el servicio respondería 403). Dos pestañas:

* **Solicitudes** (`GET /api/bookings/prestador/solicitudes`): por defecto las pendientes, de la más urgente a la menos, con cuenta regresiva hasta `expira_en` y marca de "urgente" (≤ 6 h). **Confirmar** y **Rechazar** (el motivo de 3 a 500 caracteres es obligatorio; libera los cupos). Si la solicitud cambió (la cancelaron, venció el plazo) se muestra el motivo y se recarga la lista. Filtro por estado y por servicio.
* **Calendario** (`GET/PUT /prestador/calendario/...`): los días del servicio con totales, reservados, libres y tarifa. **Editar un día** envía la versión que se vio (`If-Match`); si cambió en el servidor se muestra **tu cambio frente a lo que hay ahora** (`version_actual` y `actual` del 409) y se elige entre reenviar con la versión nueva o dejar lo que hay. **Abrir un rango** (`POST .../rango`): días de la semana, cupos y tarifa, con la cuenta de días que se abrirían; los que ya existen se omiten. 0 cupos = día cerrado; no se baja de lo ya reservado ni se pasa del aforo oficial (`CUPOS_COMPROMETIDOS`, `SUPERA_AFORO`).
* Cada intento lleva una `Idempotency-Key` nueva (no una por reintento); `PETICION_EN_PROCESO` e `IDEMPOTENCIA_NO_DISPONIBLE` se reintentan **con la misma clave** hasta 3 veces (INTEGRACION.md §2.3). Los servicios del selector salen de `GET /api/catalog/prestador/servicios`.
* **Sin conexión**, confirmar, rechazar y editar el calendario se deshabilitan. La Guía §2 prevé editar el calendario sin conexión con la cola de envíos pendientes: **no está hecho**.
* En modo simulado un prestador atiende todos los servicios de demostración; ve solicitudes de ejemplo y lo que piden los turistas. Lo que hace se refleja en lo que ve el turista (estado de su reserva y cupos y tarifas del día).
