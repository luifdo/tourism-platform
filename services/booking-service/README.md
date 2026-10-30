# booking-service

**Módulo 3: Reservas & Cupos** · Responsable: Andres Felipe Gamero Sanchez (@AFGamero)

Disponibilidad de cupos en tiempo real con bloqueo transaccional, máquina de estados de la reserva (Solicitada, Confirmada, Rechazada, Cancelada, Finalizada), expiración de solicitudes sin respuesta (48 h) y paneles de turista y prestador.

| Aspecto | Valor |
|---|---|
| Casos de uso | UC10, UC11, UC12, UC13, UC19, UC20 |
| Requerimientos funcionales | RF-03, RF-04, RF-05 |
| Requerimientos no funcionales | RNF-02, RNF-06, RNF-09, RNF-11, RNF-13 |
| Escenarios de calidad | ESC-02, ESC-06, ESC-07, ESC-08, ESC-09 |
| Persistencia | PostgreSQL — base lógica `booking_db` |
| Lenguaje / framework | Python 3.12 + FastAPI (orientado a objetos, arquitectura hexagonal) |
| Puerto interno | `8003` |
| Prefijo en el Gateway (Traefik) | `/api/bookings` |
| Réplicas en k3s | 2 (HPA hasta 6) |
| Contrato REST | [`contracts/openapi/booking.yaml`](../../contracts/openapi/) |

**¿Vas a integrar tu módulo con booking?** Empieza por [`INTEGRACION.md`](./INTEGRACION.md): qué le toca a cada módulo, códigos de error para la PWA y despliegue.

## Eventos

**Publica:**
* `reserva.solicitada.v1`
* `reserva.modificada.v1`
* `reserva.confirmada.v1`
* `reserva.rechazada.v1`
* `reserva.cancelada.v1`
* `reserva.finalizada.v1`
* `disponibilidad.actualizada.v1` (estado completo del día cada vez que cambian sus cupos; lo consume catalog para buscar)
* `auditoria.registrada.v1`

**Consume:**
* `servicio.publicado.v1` (proyección `servicio_ref`: dueño, aforo, tarifa base y estado del servicio)

Esquemas en [`contracts/events/`](../../contracts/events/).

## Estructura (arquitectura hexagonal)

```
src/
├── main.py              # composición: crea la app FastAPI e inyecta los adaptadores
├── domain/              # entidades y reglas de negocio puras, sin dependencias de frameworks
├── application/         # casos de uso del servicio (una clase por caso de uso)
│   └── ports/           # interfaces que el dominio necesita (repositorios, publicador de eventos)
└── infrastructure/      # adaptadores que implementan los puertos
    ├── http/            # routers FastAPI (implementan el contrato OpenAPI)
    ├── persistence/     # repositorios SQLAlchemy sobre la base de datos propia del servicio
    └── messaging/       # publicación y consumo de eventos en RabbitMQ (aio-pika)
tests/
├── unit/
└── integration/
```

### Regla de capas

* `domain/` y `application/` son **Python puro**: solo importan la librería estándar (y `application/` importa `domain/`). Ahí vive toda la lógica de negocio.
* Los frameworks y drivers (FastAPI, SQLAlchemy, asyncpg, aio-pika, redis) y `config.py` **solo** se usan en `infrastructure/`, `main.py` y `cron.py`. El núcleo habla con ellos a través de los puertos de `application/ports/`.
* `tests/unit/test_arquitectura.py` hace cumplir la regla: falla si el núcleo importa una librería externa, `infrastructure` o `config`.

## Ejecución

Servicio en Python 3.12 + FastAPI. En el clúster corre como contenedor en Kubernetes (k3s) según el [Plan de Implementación](../../Documents/Pages/Plan_de_Implementacion.md) §7 (ver [Docker Compose](#docker-compose) y [Kubernetes](#kubernetes-k8s) más abajo).

### Local, en modo memoria (sin Postgres ni RabbitMQ)

```bash
# Desde services/booking-service/
python -m venv .venv
.venv/Scripts/activate            # Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"

pytest                            # pruebas unitarias, de casos de uso y de la API
uvicorn main:app --app-dir src --port 8003 --reload
```

Swagger queda en <http://localhost:8003/docs>. En modo memoria se carga un servicio de ejemplo con 30 días abiertos y aparecen las rutas `/dev` (simular `servicio.publicado`, ejecutar los CronJobs, adelantar el reloj y ver los eventos publicados). Los ids de ejemplo están en la portada de Swagger. Como no hay Traefik, `X-Usuario-Id` y `X-Usuario-Rol` se escriben a mano.

### Postgres local y migraciones

Las pruebas de integración (`tests/integration/`) usan un Postgres real en Docker, en el **puerto 5433** para no chocar con un Postgres instalado en el PC ni con el `docker-compose` del equipo. Si no está corriendo, esas pruebas se saltan con un aviso.

```bash
python scripts/postgres_pruebas.py subir     # crea o arranca el contenedor (postgres:16-alpine) y espera a que responda
python scripts/rabbitmq_pruebas.py subir     # RabbitMQ en el puerto 5673 (outbox, relay y consumidor)
python scripts/valkey_pruebas.py subir       # Valkey en el puerto 6380 (idempotencia compartida entre réplicas)
pytest                                       # unitarias + integración
python scripts/postgres_pruebas.py bajar     # lo borra (es desechable)
```

El esquema de `booking_db` se crea con **Alembic** (`migrations/`). La URL sale de `DATABASE_URL`; nunca se escribe en `alembic.ini`.

```bash
alembic upgrade head          # aplica las migraciones pendientes
alembic downgrade -1          # deshace la última
alembic current               # versión actual de la base
alembic upgrade head --sql    # muestra el SQL sin ejecutarlo
```

Para cambiar el esquema: editar `src/infrastructure/persistence/tablas.py`, generar la migración con `alembic revision --autogenerate -m "..."` y **revisarla a mano** antes de subirla. La prueba `test_la_base_migrada_coincide_con_tablas_py` falla si `tablas.py` y las migraciones no coinciden.

### Docker Compose

```bash
# Desde infra/ (cp .env.example .env la primera vez)
docker compose up -d --build booking-service prometheus
```

`booking-migraciones` aplica `alembic upgrade head` sobre `booking_db` y termina; después arranca `booking-service` en modo postgres, con el relay del outbox y el consumidor de `servicio.publicado` dentro. Swagger en <http://localhost:8003/docs>; Prometheus ya tiene el job `booking-service` (`booking-service:8003`).

### Kubernetes (k8s)

`k8s/` sale de la [plantilla](../../templates/service-template/k8s/): Deployment con initContainer de migraciones (el candado `pg_advisory_xact_lock` de `migrations/env.py` evita que dos pods migren a la vez), Service `booking-service:8003` (ClusterIP), HPA 2-6 al 70 % (Plan §7.3), PodDisruptionBudget, NetworkPolicy (entran Traefik, Prometheus y recommendation-service), ConfigMap y los CronJobs `booking-expirar-solicitudes` y `booking-finalizar-reservas` (cada 15 min, hora de Bogotá, `concurrencyPolicy: Forbid`). Pasos en el [README de catalog-service](../catalog-service/README.md#kubernetes-k8s):

```bash
cd k8s/overlays/local
cp secretos.env.example secretos.env
docker build -t booking-service:local ../../..
kubectl apply -k .
```

### Tareas programadas (CronJobs)

`src/cron.py` ejecuta las tareas de la Guía §6.4 contra `booking_db` y termina (0 = bien, 1 = falló, 2 = no está en modo postgres). Los eventos quedan en el outbox y los publica el relay de la API.

```bash
# Local, contra el Postgres de pruebas (puerto 5433)
$env:PYTHONPATH="src"; $env:MODO_PERSISTENCIA="postgres"; python -m cron expirar-solicitudes
# Con docker compose (desde infra/)
docker compose run --rm booking-service python -m cron expirar-solicitudes
docker compose run --rm booking-service python -m cron finalizar-reservas
```

En modo memoria se usan las rutas `/dev/tareas/expirar` y `/dev/tareas/finalizar` de Swagger.

### Observabilidad

| Qué | Cómo |
|---|---|
| `GET /health` | `{"status": "ok" \| "degraded", "checks": {"postgres": "up" \| "down"}}`; 503 si Postgres no responde (readiness). RabbitMQ no cuenta: sin él los eventos esperan en el outbox. En modo memoria el check es `almacen_memoria`. |
| `GET /metrics` | prometheus-fastapi-instrumentator: `http_requests_total`, `http_request_duration_seconds` (como catalog, iam y recommendation), más `booking_eventos_consumidos_total`. |
| Logs | JSON por stdout, una línea por registro: `ts`, `nivel`, `servicio`, `logger`, `mensaje`, `correlation_id`, `excepcion`. Nivel con `LOG_LEVEL`. |
| `X-Correlation-ID` | Se toma de Traefik (o se genera `corr-<uuid>`), se devuelve en la respuesta y viaja en los errores y en los eventos. |
