# Contratos REST (OpenAPI 3.0)

Un archivo por servicio, escrito por su responsable **antes** de implementar los endpoints. FastAPI genera el contrato desde el código (`/openapi.json`); el archivo de esta carpeta es la versión acordada y revisada por los consumidores.

| Archivo | Servicio | Responsable |
|---|---|---|
| `iam.yaml` | iam-service | @nievesita |
| `catalog.yaml` | catalog-service (incluye analítica, alertas y reportes) | @luifdo |
| `booking.yaml` | booking-service | @AFGamero |
| `review.yaml` | review-service | @luifdo |
| `recommendation.yaml` | recommendation-service | @alvaroospino |

Convenciones:

* Rutas públicas bajo el prefijo del servicio, que Traefik usa para enrutar: `/api/iam/...`, `/api/catalog/...` (incluye `/api/catalog/analitica/...` y `/api/catalog/alertas`), `/api/bookings/...`, `/api/reviews/...` y `/api/recommendations/...`.
* Autenticación con `Authorization: Bearer <JWT>` emitido por iam-service. En las rutas protegidas, Traefik valida el token con ForwardAuth (`GET /api/iam/auth/verificar`) y reenvía la identidad en `X-Usuario-Id` y `X-Usuario-Rol`; cada servicio verifica el rol que exige su endpoint.
* Errores con un formato común: `{ "error": "<CODIGO>", "message": "<texto>", "correlation_id": "<id>" }`.
* Los `POST`/`PUT` que la PWA puede reenviar sin conexión aceptan `Idempotency-Key`, y las ediciones usan `If-Match` con la versión del registro (respuesta 409 ante conflicto).
* Todo servicio expone `GET /health` (sondas de Kubernetes, RNF-01) y `GET /metrics` (Prometheus).
