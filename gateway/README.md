# API Gateway

**Capa transversal** · Responsable: Juan Francisco Gonzalez Pacheco (@JuanFranG)

Punto de entrada único implementado con **Traefik**, el controlador de Ingress incluido en k3s (ADR-007): terminación TLS, validación de JWT mediante ForwardAuth contra iam-service, *rate limiting*, CORS y enrutamiento por prefijo (ver [`contracts/openapi/`](../contracts/openapi/)).

| Prefijo | Servicio destino | Autenticación |
|---|---|---|
| `/api/iam/` | iam-service:8001 | Pública en login, registro y recuperación; ForwardAuth en el resto |
| `/api/catalog/` | catalog-service:8002 | Pública en consultas del catálogo (RF-01); ForwardAuth en el resto |
| `/api/bookings/` | booking-service:8003 | Pública en disponibilidad; ForwardAuth en el resto |
| `/api/reviews/` | review-service:8004 | Pública en lectura; ForwardAuth en escritura |
| `/api/recommendations/` | recommendation-service:8005 | ForwardAuth |
| `/` | frontend (PWA) | Pública |

ForwardAuth consulta `GET /api/iam/auth/verificar`; si el token es válido, Traefik reenvía la petición con `X-Usuario-Id` y `X-Usuario-Rol`. Detalle en el [Plan de Implementación](../Documents/Pages/Plan_de_Implementacion.md) §4.1 y §6.1.

**Pendiente (Fase 4):** recursos `IngressRoute` y middlewares (ForwardAuth, RateLimit, CORS) en `config/`.
