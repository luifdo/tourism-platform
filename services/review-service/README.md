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
| Contrato REST | [`contracts/openapi/review.yaml`](../../contracts/openapi/) |

## Eventos

**Publica:**
* `resena.publicada.v1`
* `auditoria.registrada.v1`

**Consume:**
* `reserva.finalizada.v1` (habilita la reseña)

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
