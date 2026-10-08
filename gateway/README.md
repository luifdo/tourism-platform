# API Gateway

**Capa transversal** · Responsable: Juan Francisco Gonzalez Pacheco (@JuanFranG)

Punto de entrada único: terminación TLS, validación de JWT, *rate limiting*, CORS y enrutamiento a cada servicio según el prefijo de ruta (ver [`contracts/openapi/`](../contracts/openapi/)).

| Prefijo | Servicio destino |
|---|---|
| `/api/iam/` | iam-service:8001 |
| `/api/catalog/` | catalog-service:8002 |
| `/api/bookings/` | booking-service:8003 |
| `/api/reviews/` | review-service:8004 |
| `/api/recommendations/` | recommendation-service:8005 |
| `/api/analytics/` | analytics-service:8006 |

**Pendiente:** elegir Nginx o Traefik (SRS §3.6.4) y agregar aquí su configuración (`config/`).
