# review-service

**Módulo 4: Reseñas & Moderación** · Responsable: Alvaro David Ospino Sanchez (@alvaroospino)

Calificaciones y reseñas, respuestas de prestadores, pre-moderación heurística de lenguaje ofensivo y cola de moderación.

| Aspecto | Valor |
|---|---|
| Casos de uso | UC15, UC21, UC29 |
| Requerimientos funcionales | Pendiente: el SRS no tiene un RF propio para reseñas |
| Requerimientos no funcionales | RNF-01, RNF-05 |
| Escenarios de calidad | ESC-01 |
| Persistencia | Documental — MongoDB Community o FerretDB (decisión abierta, SRS §3.6.4) |
| Lenguaje / framework | Por definir (Spring Boot o NestJS) |
| Puerto interno | `8004` |
| Contrato REST | [`contracts/openapi/review.yaml`](../../contracts/openapi/) |

## Eventos

**Publica:**
* `resena.publicada.v1`
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
docker compose up review-service
```
