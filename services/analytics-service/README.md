# analytics-service

**Módulo 6: Analítica & Destino** · Responsable: Luis Fernando Barraza Sanchez (@luifdo)

Indicadores de demanda y capacidad de carga, tableros y reportes para la Entidad de Gestión, alertas oficiales y envío de correos transaccionales.

| Aspecto | Valor |
|---|---|
| Casos de uso | UC22, UC23, UC24, UC25, UC26, UC36, UC38 |
| Requerimientos funcionales | RF-07, RF-11, RF-13 |
| Requerimientos no funcionales | RNF-01, RNF-03 |
| Escenarios de calidad | ESC-03 |
| Persistencia | Pendiente: el SRS no asigna almacén a este módulo |
| Lenguaje / framework | Por definir (Spring Boot o NestJS) |
| Puerto interno | `8006` |
| Contrato REST | [`contracts/openapi/analytics.yaml`](../../contracts/openapi/) |

## Eventos

**Publica:**
* —

**Consume:**
* `reserva.solicitada.v1`
* `reserva.confirmada.v1`
* `reserva.rechazada.v1`
* `reserva.cancelada.v1`

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
docker compose up analytics-service
```
