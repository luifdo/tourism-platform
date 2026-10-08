# booking-service

**Módulo 3: Reservas & Cupos** · Responsable: Andres Felipe Gamero Sanchez (@AFGamero)

Disponibilidad de cupos en tiempo real, ciclo de vida de las solicitudes de reserva y paneles de turista y prestador.

| Aspecto | Valor |
|---|---|
| Casos de uso | UC10, UC11, UC12, UC13, UC19, UC20 |
| Requerimientos funcionales | RF-03, RF-04, RF-05 |
| Requerimientos no funcionales | RNF-02, RNF-06, RNF-11 |
| Escenarios de calidad | ESC-02, ESC-06, ESC-07, ESC-08 |
| Persistencia | PostgreSQL — base lógica `booking_db` |
| Lenguaje / framework | Por definir (Spring Boot o NestJS) |
| Puerto interno | `8003` |
| Contrato REST | [`contracts/openapi/booking.yaml`](../../contracts/openapi/) |

## Eventos

**Publica:**
* `reserva.solicitada.v1`
* `reserva.confirmada.v1`
* `reserva.rechazada.v1`
* `reserva.cancelada.v1`
* `auditoria.registrada.v1`

**Consume:**
* —

Esquemas en [`contracts/events/`](../../contracts/events/).

## Estructura (arquitectura hexagonal)

```
src/
├── domain/              # entidades y reglas de negocio puras, sin dependencias de frameworks
├── application/         # casos de uso del servicio
│   └── ports/           # interfaces que el dominio necesita (repositorios, publicador de eventos)
└── infrastructure/      # adaptadores que implementan los puertos
    ├── http/            # controladores REST (implementan el contrato OpenAPI)
    ├── persistence/     # acceso a la base de datos propia del servicio
    └── messaging/       # publicación y consumo de eventos en RabbitMQ
tests/
├── unit/
└── integration/
```

## Ejecución

Pendiente de la elección del lenguaje: agregar `Dockerfile`, dependencias y comandos de ejecución y pruebas.

```bash
# Desde infra/, una vez agregado el servicio al docker-compose:
docker compose up booking-service
```
