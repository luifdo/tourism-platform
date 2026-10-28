# review-service

**Módulo 4: Reseñas & Moderación** · Responsable: Luis Fernando Barraza Sanchez (@luifdo)

Calificaciones y reseñas de turistas con reserva finalizada, respuestas públicas de prestadores, reporte de reseñas inapropiadas (UC39) y moderación manual del Administrador (UC29).

| Aspecto | Valor |
|---|---|
| Casos de uso | UC15, UC21, UC29, UC39 |
| Requerimientos funcionales | RF-14 |
| Requerimientos no funcionales | RNF-01, RNF-10 |
| Escenarios de calidad | ESC-01 |
| Persistencia | PostgreSQL con JSONB — base lógica `review_db` |
| Lenguaje / framework | Python 3.12 + FastAPI (orientado a objetos, arquitectura hexagonal) |
| Puerto interno | `8004` |
| Prefijo en el Gateway (Traefik) | `/api/reviews` |
| Réplicas en k3s | 1 (HPA hasta 3) |
| Contrato REST | [`contracts/openapi/review.yaml`](../../contracts/openapi/review.yaml) |

## Eventos

**Publica** (con outbox, como catalog-service):
* `resena.publicada.v1`: al crear o editar una reseña, y al volver a publicar una oculta.
* `resena.ocultada.v1`: cuando el Administrador la oculta (catalog la quita del promedio).
* `auditoria.registrada.v1`: decisiones de moderación (MODERACION) y accesos denegados (ACCESS_DENIED).

**Consume:**
* `reserva.finalizada.v1` en `review.elegibilidad`: habilita la reseña del turista para ese servicio.
* `servicio.publicado.v1` en `review.servicios`: qué prestador es dueño de cada servicio (responder y reportar).

## Reglas principales

* Una reseña por turista y servicio, solo con una reserva finalizada; editable por su autor.
* Autor anónimo: "Turista verificado" y el mes de la visita.
* Un reporte no oculta la reseña: entra en la cola del Administrador. Pasa a `EN_REVISION` (oculta) al tercer reporte o si la reporta el prestador dueño; su nota sigue contando hasta que el Administrador la publique u oculte.

Esquemas en [`contracts/events/`](../../contracts/events/).

## Estructura (arquitectura hexagonal)

Misma estructura que catalog-service (una clase por archivo; solo `app/` tiene `__init__.py`):

```
app/
├── main.py              # composición: crea la app FastAPI e inyecta los adaptadores
├── worker.py            # relay del outbox y consumidores (proceso aparte)
├── domain/              # entidades y reglas de negocio puras, sin dependencias de frameworks
├── application/         # casos de uso (una clase por caso de uso), DTO y puertos
├── infrastructure/      # adaptadores: persistencia (SQLAlchemy), mensajería (aio-pika), observabilidad
└── api/                 # routers FastAPI (implementan el contrato OpenAPI), esquemas, errores e i18n
migrations/              # Alembic
tests/
├── unit/
└── integration/
```

## Ejecución

Requiere [uv](https://docs.astral.sh/uv/) y Python 3.12 (`uv python install 3.12`).

```bash
docker compose -f docker-compose.dev.yml up -d   # PostgreSQL y RabbitMQ
uv sync                                          # instala dependencias (incluye dev)
cp .env.example .env
uv run alembic upgrade head                      # aplicar migraciones
uv run uvicorn app.main:app --reload --port 8004
uv run pytest                                    # unitarias + integración (PostgreSQL en testcontainers)
uv run ruff check . && uv run ruff format --check .
```

Los puertos de `docker-compose.dev.yml` (5435, 5674 y 15674) no chocan con los de iam-service ni catalog-service, así que los tres entornos pueden correr a la vez. Review no usa Valkey: la idempotencia (`Idempotency-Key`) y el límite de reportes por hora se guardan en PostgreSQL, porque las reseñas no necesitan esa latencia y así el servicio depende de una pieza menos. Las pruebas de integración levantan su propio PostgreSQL efímero y no tocan la base de desarrollo; sin Docker se omiten.

`/health` responde 503 solo si PostgreSQL no contesta: sin RabbitMQ el outbox acumula los eventos y la réplica sigue atendiendo (ESC-01). `/metrics` expone las métricas HTTP para Prometheus.

Toda respuesta que recibe una prueba se valida contra [`review.yaml`](../../contracts/openapi/review.yaml) (`tests/conftest.py`); una prueba que se sale del contrato a propósito lleva `@pytest.mark.sin_contrato`.
