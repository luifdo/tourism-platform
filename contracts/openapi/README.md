# Contratos REST (OpenAPI 3.0)

Un archivo por servicio, escrito por su responsable **antes** de implementar los endpoints:

| Archivo | Servicio | Responsable |
|---|---|---|
| `iam.yaml` | iam-service | @JuanFranG |
| `catalog.yaml` | catalog-service | @nievesita |
| `booking.yaml` | booking-service | @AFGamero |
| `review.yaml` | review-service | @alvaroospino |
| `recommendation.yaml` | recommendation-service | @luifdo |
| `analytics.yaml` | analytics-service | @luifdo |

Convenciones:

* Rutas públicas bajo el prefijo del servicio, que el Gateway usa para enrutar: `/api/iam/...`, `/api/catalog/...`, `/api/bookings/...`, `/api/reviews/...`, `/api/recommendations/...`, `/api/analytics/...`.
* Autenticación con `Authorization: Bearer <JWT>` emitido por iam-service.
* Errores con un formato común: `{ "error": "<CODIGO>", "message": "<texto>", "correlation_id": "<id>" }`.
* Todo servicio expone `GET /health` para las sondas de disponibilidad (RNF-01).
