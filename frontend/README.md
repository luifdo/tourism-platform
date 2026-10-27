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
* `src/lib/useCatalog.js`: catálogo en vivo, o última copia guardada con su fecha, o datos de ejemplo.
* Solicitar y confirmar reservas requieren conexión y se deshabilitan sin ella.

## Reservas (UC10–UC13)

* Rutas: `/servicios/:id` (ficha + reserva en 4 pasos) y `/mis-reservas`.
* `src/lib/api.js` implementa el cliente de `contracts/openapi/booking.yaml` (`Idempotency-Key` al solicitar, `If-Match` al modificar, errores con el formato `Error`).
* Mientras no exista el Gateway, `VITE_API_MOCK=true` (archivo `.env`, copiado de `.env.example`; si falta, por defecto es simulado) usa `src/lib/mockBookings.js`, un servicio simulado en el navegador que respeta las reglas del contrato y de la Guía Técnica del Módulo 3. Para usar el Gateway real: `VITE_API_MOCK=false`.
* Pendiente con el backend real: la ficha del servicio sale de `src/data/mock.js` (reemplazar por `GET /api/catalog/servicios/{id}`) y falta el login (UC2) para obtener el JWT.

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

### Pruebas

```bash
npm test          # dominio, casos de uso (con adaptadores falsos), adaptadores y regla de dependencias
npm run test:watch
```
