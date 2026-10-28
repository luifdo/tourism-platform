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
uv run python -m app.worker                      # worker: relay del outbox, consumidores y limpieza diaria (métricas en :9104)
uv run pytest                                    # unitarias + integración (PostgreSQL en testcontainers)
uv run ruff check . && uv run ruff format --check .
```

Los puertos de `docker-compose.dev.yml` (5435, 5674 y 15674) no chocan con los de iam-service ni catalog-service, así que los tres entornos pueden correr a la vez. Review no usa Valkey: la idempotencia (`Idempotency-Key`) y el límite de reportes por hora se guardan en PostgreSQL, porque las reseñas no necesitan esa latencia y así el servicio depende de una pieza menos. Las pruebas de integración levantan su propio PostgreSQL efímero y no tocan la base de desarrollo; sin Docker se omiten.

`/health` responde 503 solo si PostgreSQL no contesta: sin RabbitMQ el outbox acumula los eventos y la réplica sigue atendiendo (ESC-01). `/metrics` expone las métricas HTTP para Prometheus.

Toda respuesta que recibe una prueba se valida contra [`review.yaml`](../../contracts/openapi/review.yaml) (`tests/conftest.py`); una prueba que se sale del contrato a propósito lleva `@pytest.mark.sin_contrato`.

## Endpoints implementados

Bajo `/api/reviews` sin StripPrefix (Traefik reenvía la ruta completa). Identidad por `X-Usuario-Id` y `X-Usuario-Rol`, que pone Traefik tras validar el JWT; sin ellas, 401 `NO_AUTENTICADO`.

| Ruta | Quién | Qué hace |
|---|---|---|
| `POST /resenas` | `Turista` | Escribe la reseña (UC15). 201 con `ResenaPropia` y `ETag`. 403 `NO_ELEGIBLE` sin reserva finalizada; 409 `YA_RESENADO` si ya reseñó el servicio. Admite `Idempotency-Key` |
| `PUT /resenas/{id}` | Su autor | Edita la reseña con `If-Match`. 409 `VERSION_DISTINTA` (con el `ETag` actual) o `RESENA_EN_MODERACION`; 403 `NO_ES_DUENO`; 428 sin `If-Match` |

* **Anónima:** la respuesta dice "Turista verificado" (o "Verified tourist") y el mes de la visita; nunca el nombre ni el id del turista.
* **El comentario se guarda tal cual**, sin quitar etiquetas: la PWA debe mostrarlo como texto, nunca como HTML. Así se evita el XSS sin cambiar lo que escribió el turista ("precio < 50 mil").
* **Evento:** crear y editar guardan `resena.publicada` en el outbox en la misma transacción.
* **Auditoría (ESC-04):** `ROL_NO_PERMITIDO` y `NO_ELEGIBLE` se publican como `auditoria.registrada` (`ACCESS_DENIED`) con el usuario, el rol, el motivo, los roles permitidos o el servicio, el método, la ruta y la IP de `X-Forwarded-For`. Si no se puede guardar, queda en el log y el 403 sale igual.
* **Idempotencia:** la clave se guarda por usuario, método y ruta en PostgreSQL. Un reenvío devuelve la misma respuesta con `Idempotent-Replayed: true`; si el primero sigue en curso, 409 `SOLICITUD_EN_PROCESO`.

## Worker y mensajería (RabbitMQ)

La API no publica en RabbitMQ ni consume eventos: todo el trabajo en segundo plano lo hace el **worker** ([`app/worker.py`](app/worker.py)), un proceso aparte que usa la misma imagen con otro comando (`python -m app.worker`) y tendrá su propio Deployment.

**Por qué un proceso aparte:** la API no depende de él. Si el worker o RabbitMQ se caen, las reseñas se siguen escribiendo y sus eventos esperan en el outbox (ESC-01: nadie llama a review en el camino crítico y review tampoco llama a nadie).

El worker corre a la vez, en un mismo bucle asyncio (`asyncio.gather`), estos componentes:

| Componente | Objetivo | Código |
|---|---|---|
| Relay del outbox | Llevar a RabbitMQ los eventos que la API guarda en la tabla `outbox` (`resena.publicada`, `resena.ocultada`; más adelante `auditoria.registrada`) | `RelayOutbox`, `PublicarEventosPendientes`, `SqlOutboxPendiente`, `PublicadorRabbitMQ` |
| `review.elegibilidad` | Quién puede reseñar cada servicio y el mes de su visita (`reserva.finalizada` de booking) | `ManejadorElegibilidad`, `RegistrarVisita` |
| `review.servicios` | Qué prestador es dueño de cada servicio (`servicio.publicado` de catalog) | `ManejadorServicios`, `RegistrarDuenoServicio` |
| Limpieza diaria | Borrar la idempotencia vencida y `evento_procesado` viejo | `TareaPeriodica`, `LimpiarRegistrosVencidos`, `SqlRegistrosVencidos` |
| Métricas | `/metrics` para Prometheus y sonda de vida en k8s | `start_http_server(WORKER_METRICS_PORT)` |

Todo está copiado de catalog-service (no importado: los servicios no comparten librerías). La explicación detallada de cada pieza está en su [README](../catalog-service/README.md#worker-y-mensajería-rabbitmq); aquí va lo propio de review.

### Topología común

[`topologia_rabbitmq.py`](app/infrastructure/messaging/topologia_rabbitmq.py): exchange `turismo.eventos` (*topic*, la clave es el `event_type`), `turismo.dlx` y la DLQ común `turismo.dead-letter`. Declararla otra vez no cambia nada. Las colas `review.*` las declaran sus consumidores.

### Relay del outbox

* Cada 1 s toma hasta 100 eventos pendientes con `FOR UPDATE SKIP LOCKED` (dos workers nunca toman el mismo) y los publica con *publisher confirms*; solo marca `publicado_en` cuando el broker confirma.
* Si RabbitMQ o PostgreSQL fallan, espera el doble cada vez hasta 30 s; nada se descarta.
* Entrega "al menos una vez": catalog descarta duplicados por `event_id` y aplica cada reseña por `resena_id` según `occurred_at`, el momento real del cambio.
* **Sin cola enlazada, el broker descarta el mensaje** (`mandatory=False`): catalog declara `catalog.calificaciones` y iam debe declarar `iam.auditoria` antes de necesitar los eventos.
* Una vez al día borra los eventos **publicados** con más de `OUTBOX_RETENCION_DIAS` (7). Los pendientes nunca se borran.

### Consumidores: base común

`ConsumidorRabbitMQ` ([`consumidor_rabbitmq.py`](app/infrastructure/messaging/consumidor_rabbitmq.py)): cola durable `review.<propósito>`, prefetch `CONSUMIDOR_PREFETCH` (10), solo `version` 1 del sobre, reintentos a 1 s, 5 s y 25 s y luego la DLQ con `x-cola`, `x-intentos` y `x-error`. Un error permanente (sobre o payload fuera de contrato, `EventoInvalido`, `DatoInvalido`) va directo a la DLQ. El original se reconoce solo después de copiarlo al reintento o a la DLQ: no se pierde nada. La idempotencia por `event_id` la hace cada caso de uso en la misma transacción de su efecto.

### `review.elegibilidad` (booking → quién puede reseñar)

**Objetivo:** saber, sin llamar a booking, qué turista tiene una reserva finalizada de qué servicio (RF-14). Con esa fila el servicio aparece en `/turista/pendientes` y `POST /resenas` lo admite; sin ella, 403 `NO_ELEGIBLE`.

* Clave `reserva.finalizada`. Del payload usa `turista_id`, `servicio_id` y `fecha_reserva`; ignora lo demás.
* Guarda una fila por turista y servicio con la **visita más reciente** (`GREATEST` en la base: dos eventos a la vez no la hacen retroceder). Una visita más vieja o igual queda registrada como procesada y no cambia nada (`ignorado`).
* El mes de la reseña se toma de aquí al escribirla o editarla. Una visita posterior no cambia el mes de una reseña ya escrita hasta que el turista la edite: el texto habla de la visita sobre la que escribió.

### `review.servicios` (catalog → dueño de cada servicio)

**Objetivo:** saber, sin llamar a catalog, qué prestador es dueño de cada servicio: solo él responde sus reseñas (UC21) y su reporte las pasa a revisión (UC39).

* Clave `servicio.publicado`. Usa `servicio_id`, `prestador_usuario_id` y `version`.
* Descarta las versiones iguales o menores a la guardada (`WHERE version <` en la base), así el orden de llegada no importa.
* `activo` se ignora a propósito: un servicio desactivado conserva sus reseñas y su dueño puede seguir respondiéndolas. Un prestador suspendido ya no inicia sesión (lo controla iam).

### Orden de despliegue

RabbitMQ descarta un mensaje si ninguna cola está enlazada a su clave. Por eso **el worker de review se despliega antes o junto con catalog y booking**: si catalog publicara servicios antes de que exista `review.servicios`, review no sabría sus dueños y esos prestadores no podrían responder (403 `NO_ES_DUENO`); lo mismo con las reservas finalizadas antes de `review.elegibilidad`. Una vez declaradas, las colas son durables y guardan los mensajes aunque el worker esté caído: el riesgo existe solo en el primer despliegue. En una plataforma nueva no hay datos previos, así que no pasa nada.

### Limpieza diaria

`TareaPeriodica` corre `LimpiarRegistrosVencidos` al arrancar y luego cada 24 h. Si falla, queda en el log y se intenta en la siguiente vuelta. Son `DELETE` por condición: con dos workers corre en los dos sin daño.

| Tabla | Qué borra | Por qué se puede |
|---|---|---|
| `idempotencia` | `expira_en < now()` | Una clave vencida ya no evita ningún reenvío (`reservar` la retoma); solo ocupa espacio |
| `evento_procesado` | Más de `EVENTO_PROCESADO_RETENCION_DIAS` (30) | Los duplicados llegan en minutos (o días, si alguien reprocesa la DLQ a mano). Además, los consumidores de review ya son idempotentes por sí mismos: la elegibilidad se queda con la visita más reciente y el dueño con la versión mayor |
| `outbox` | Lo hace el relay (arriba) | |

**Nunca se borran** reseñas (una `OCULTA` es historia de la moderación), reportes (el Administrador ve quién reportó y un usuario no reporta dos veces) ni las proyecciones de elegibilidad y dueño.

### Configuración del worker

| Variable | Por defecto | Para qué |
|---|---|---|
| `DATABASE_URL` | base de desarrollo (`:5435`) | Outbox, proyecciones, `evento_procesado` e idempotencia |
| `RABBITMQ_URL` / `RABBITMQ_TIMEOUT_SECONDS` | `:5674` / 5 s | Conexión, confirmación del broker y copias a reintento o DLQ |
| `EVENTS_EXCHANGE` | `turismo.eventos` | Exchange donde publica y del que consume |
| `OUTBOX_LOTE` / `OUTBOX_INTERVALO_SEGUNDOS` | 100 / 1 s | Eventos por vuelta y pausa entre vueltas |
| `OUTBOX_ESPERA_MAXIMA_SEGUNDOS` | 30 | Tope de la espera tras fallos (relay y conexión de los consumidores) |
| `OUTBOX_RETENCION_DIAS` | 7 | Días que se guardan los eventos ya publicados |
| `EVENTO_PROCESADO_RETENCION_DIAS` | 30 | Días que se recuerda un evento ya aplicado |
| `CONSUMIDOR_PREFETCH` | 10 | Mensajes en proceso a la vez por cola |
| `WORKER_METRICS_PORT` | 9104 | `/metrics` (Prometheus y sondas) |
| `LOG_LEVEL` | `INFO` | Logs JSON con el nombre `review-service-worker` |

### Dependencias: qué pasa si fallan

| Si falla... | Relay del outbox | Consumidores | API |
|---|---|---|---|
| **PostgreSQL** | Espera creciente; los eventos siguen pendientes | Reintentos y luego DLQ | `/health` 503: la réplica sale del enrutamiento |
| **RabbitMQ** | Espera creciente; nada se pierde | Reintentan la conexión (1 s a 30 s); luego `connect_robust` reconecta solo | Sigue atendiendo: los eventos esperan en el outbox |
| **El worker** | — | — | Sigue atendiendo; al volver, el relay publica lo acumulado |

### Operación del worker

* **Apagado ordenado:** con SIGTERM o SIGINT (en Windows, Ctrl+C) termina las vueltas en curso y cierra consumidores, publicador y base de datos.
* **Métricas:** `review_outbox_pendientes`, `review_outbox_antiguedad_segundos` (alertar si crece), `review_eventos_publicados_total{event_type}`, `review_eventos_fallos_publicacion_total` y `review_eventos_consumidos_total{cola,event_type,resultado}`.
* **Logs:** en JSON, con el `correlation_id` de cada evento consumido.
