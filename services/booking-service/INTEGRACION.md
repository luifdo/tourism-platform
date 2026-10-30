# Integración de booking-service (Módulo 3)

Guía para quien integre booking con su módulo. booking está **terminado y probado**: Postgres, outbox + RabbitMQ, consumidor de `servicio.publicado`, idempotencia en Valkey, CronJobs, observabilidad, Dockerfile y manifiestos de Kubernetes. Lo que falta es conectarlo con los demás módulos; cada sección dice qué le toca a quién.

* Contrato REST: [`contracts/openapi/booking.yaml`](../../contracts/openapi/booking.yaml)
* Eventos: [`contracts/events/`](../../contracts/events/)
* Reglas de negocio: [Guía Técnica del Módulo 3](../../Documents/Pages/Guia_Tecnica_Modulo_Reservas.md)
* Cómo correrlo: [README](./README.md)

## 1. Levantarlo

```bash
# Desde infra/ (la primera vez: cp .env.example .env)
docker compose up -d --build booking-service prometheus
```

Levanta Postgres, RabbitMQ y Valkey, aplica las migraciones (`booking-migraciones`) y arranca la API en <http://localhost:8003> (Swagger en `/docs`). Sin Traefik, la identidad se envía a mano: `X-Usuario-Id: <uuid>` y `X-Usuario-Rol: Turista | Prestador`.

**Con la base vacía no hay servicios que reservar:** booking los conoce por el evento `servicio.publicado` de catalog. Con catalog levantado en el mismo compose, crear un servicio en catalog basta. Para probar booking solo, use el modo memoria (`MODO_PERSISTENCIA=memoria`, ver README), que trae un servicio de ejemplo y las rutas `/dev`.

| Dato | Valor |
|---|---|
| Service de Kubernetes | `booking-service:8003` (ClusterIP), namespace `turismo-app` |
| Prefijo en Traefik | `/api/bookings` |
| Sondas | `GET /health` → `{"status": "ok" \| "degraded", "checks": {"postgres": "up" \| "down"}}`, 503 si Postgres no responde |
| Métricas | `GET /metrics`: `http_requests_total`, `http_request_duration_seconds`, `booking_eventos_consumidos_total` |
| Logs | JSON por stdout con `correlation_id` (mismos campos que catalog) |
| Variables | `DATABASE_URL`, `RABBITMQ_URL`, `VALKEY_URL`, `MODO_PERSISTENCIA=postgres` (ver `.env.example`) |

## 2. Frontend (PWA) · @JuanFranG

`src/infrastructure/booking/httpBookingGateway.js` ya llama bien a disponibilidad, solicitar, mis reservas, modificar y cancelar. Falta:

1. **Panel del prestador (UC19, UC20).** No hay métodos todavía para:
   * `GET /prestador/solicitudes?estado&servicio_id&desde&hasta&pagina&tamano` (por defecto, las `SOLICITADA` ordenadas por `expira_en`);
   * `POST /{id}/confirmar`, `POST /{id}/rechazar` (cuerpo `{"motivo"}` obligatorio);
   * `GET /prestador/calendario/{servicio_id}?desde&hasta`;
   * `POST /prestador/calendario/{servicio_id}/rango` y `PUT /prestador/calendario/{servicio_id}/{fecha}` (formularios sin conexión: `Idempotency-Key` y, para editar, `If-Match`).
2. **Conflicto de versión.** El 409 `VERSION_DISTINTA` trae en el cuerpo `version_actual` y `actual` (el día o la reserva con el mismo formato de su GET), además del `ETag`. Hoy `BookingError` solo guarda `error`, `message` y `correlation_id`; hay que pasarle también `data` para mostrar "tu cambio / lo que hay ahora" sin otro GET. Si el usuario insiste, se reenvía con `If-Match: "<version_actual>"`.
3. **Códigos nuevos al reintentar con `Idempotency-Key`:**
   * 409 `PETICION_EN_PROCESO`: la primera petición con esa clave sigue corriendo. Reintentar **con la misma clave** a los pocos segundos.
   * 503 `IDEMPOTENCIA_NO_DISPONIBLE`: no se ejecutó nada. Reintentar con la misma clave más tarde (la cola de la PWA ya lo hace).
   * Una misma clave devuelve siempre la misma respuesta durante 48 h: generar una clave nueva por cada intento del usuario, no por cada reintento.
4. **Plazo de respuesta.** Mostrar `expira_en` al turista y al prestador. Una solicitud sin respuesta pasa sola a `RECHAZADA` con motivo "Plazo de respuesta vencido" (CronJob cada 15 min).
5. **Sin conexión:** solicitar, modificar, cancelar, confirmar y rechazar se deshabilitan; solo el calendario del prestador se puede editar sin conexión (Guía §2).
6. **Nombre del servicio.** La reserva solo trae `servicio_id`. Decisión pendiente del equipo:
   * **a) (recomendada)** la PWA lo resuelve en catalog con los `servicio_id` de la página; no cambia ningún contrato;
   * b) catalog agrega `nombre` opcional a `servicio.publicado` y booking lo devuelve como `servicio_nombre` (requiere cambio en catalog y en booking).

## 3. Gateway (Traefik) · @JuanFranG

* `GET /api/bookings/disponibilidad` es **pública**; todo lo demás bajo `/api/bookings` pasa por ForwardAuth (`GET /api/iam/auth/verificar`), como dice `gateway/README.md`.
* **Importante para la seguridad:** Traefik debe **borrar** los encabezados `X-Usuario-Id` y `X-Usuario-Rol` que mande el cliente y poner solo los que devuelve ForwardAuth (`authResponseHeaders`). booking confía en ellos para saber quién es el turista o el prestador.
* `/health` y `/metrics` no se publican hacia afuera.
* `POST /api/bookings` y `POST /api/bookings/` funcionan igual (la PWA usa la segunda).

## 4. IAM · @nievesita

* `X-Usuario-Rol` debe llegar exactamente como `Turista` o `Prestador` (también se aceptan `Entidad` y `Admin`, pero booking no les da permisos). Un rol desconocido responde 403 y publica `auditoria.registrada` con `accion = ACCESS_DENIED`.
* `X-Usuario-Id` es el UUID del usuario en iam; es el mismo `prestador_usuario_id` que catalog manda en `servicio.publicado`.
* Consumir `auditoria.registrada` de booking (`RESERVA_*`, `ACCESS_DENIED`) en la bitácora (UC33).

## 5. Catalog · @luifdo

Ya consume `reserva.*` y `disponibilidad.actualizada`, y publica `servicio.publicado`; no hace falta nada más para funcionar. Para revisar:

* booking declara su cola `booking.servicios` (con reintentos 1/5/25 s y DLQ `turismo.dead-letter`, la misma convención de catalog) al conectarse. Lo que catalog publique **antes** de que booking haya arrancado alguna vez se pierde: en un entorno nuevo, arrancar booking antes de crear servicios, o volver a publicar los servicios existentes.
* `disponibilidad.actualizada` lleva el estado completo del día; confirmar y finalizar no lo emiten porque no mueven cupos.

## 6. Recommendation · @alvaroospino

* Tools: `GET /api/bookings/disponibilidad` (pública) y `GET /api/bookings/mis-reservas` (del turista).
* Si llama a booking **por dentro del clúster** (`http://booking-service:8003`, sin pasar por Traefik), debe reenviar `X-Usuario-Id` y `X-Usuario-Rol: Turista` del usuario del chat; si no, `mis-reservas` responde 401. La NetworkPolicy de booking ya deja entrar a los pods `app.kubernetes.io/name: recommendation-service`.
* En `.env`, `BOOKING_URL` apunta hoy a un mock; cambiarlo a `http://booking-service:8003/api/bookings` (clúster) o `http://localhost:8003/api/bookings` (compose).

## 7. Infraestructura y despliegue · @luifdo

Este PR toca `infra/` (revisar):

* `docker-compose.yml`: `booking-migraciones` y `booking-service` (modo postgres), con `VALKEY_URL` en la **base 1** para no mezclarse con la caché de catalog (base 0).
* `prometheus/prometheus.yml`: job `booking-service` (`booking-service:8003`).

En el clúster (k3s):

```bash
kubectl apply -k services/booking-service/k8s/overlays/local   # local; para k3s, un overlay propio con el Secret real
```

* El Secret `booking-service-secretos` necesita `DATABASE_URL` (usuario propio de `booking_db` en CloudNativePG), `RABBITMQ_URL` y `VALKEY_URL`.
* El Deployment corre las migraciones en un initContainer (con candado, seguro con varias réplicas); 2 réplicas, HPA hasta 6.
* CronJobs `booking-expirar-solicitudes` y `booking-finalizar-reservas`, cada 15 min en hora de Bogotá. Sin ellos las solicitudes no vencen y las reservas no pasan a `FINALIZADA` (review no habilitaría reseñas).
* Los manifiestos se renderizaron con `kubectl kustomize` pero **no se han aplicado a un clúster real**: es lo primero que conviene probar.

## 8. Pruebas de la Fase 5

| Escenario | Qué probar en booking |
|---|---|
| ESC-08 (carga) | k6 con muchas solicitudes sobre pocos servicios y fechas; debe haber 0 sobreventas (`tests/integration/test_concurrencia.py` ya lo prueba con 50 peticiones simultáneas). |
| ESC-06 (recuperación) | Restaurar `booking_db` desde el respaldo de CloudNativePG en ≤ 30 min. |
| ESC-09 (sin conexión) | Editar el calendario sin conexión y sincronizar: 0 duplicados (`Idempotency-Key`) y conflicto visible (`VERSION_DISTINTA` con `actual`). |

Para correr las pruebas de booking: ver README, sección "Postgres local y migraciones" (274 pruebas, unitarias e integración con Postgres, RabbitMQ y Valkey reales).
