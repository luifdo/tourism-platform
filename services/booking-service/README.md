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

## Ejecución

Servicio en Python 3.12 + FastAPI. En el clúster corre como contenedor en Kubernetes (k3s) según el [Plan de Implementación](../../Documents/Pages/Plan_de_Implementacion.md) §7; el `Dockerfile` y los manifiestos llegan en el Sprint 5.

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
