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
* `reserva.confirmada.v1`
* `reserva.rechazada.v1`
* `reserva.cancelada.v1`
* `reserva.finalizada.v1`
* `auditoria.registrada.v1`

**Consume:**
* —

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

Servicio en Python 3.12 + FastAPI, empaquetado como contenedor y desplegado en Kubernetes (k3s) según el [Plan de Implementación](../../Documents/Pages/Plan_de_Implementacion.md) §7. El código, el `Dockerfile` y los manifiestos se agregan en la Fase 4.
