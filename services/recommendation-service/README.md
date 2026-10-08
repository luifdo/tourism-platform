# recommendation-service

**Módulo 5: IA & Recomendación** · Responsable: Luis Fernando Barraza Sanchez (@luifdo)

Recomendaciones personalizadas y explicables (filtrado híbrido sobre datos sintéticos), procesadas de forma asíncrona.

| Aspecto | Valor |
|---|---|
| Casos de uso | UC14 |
| Requerimientos funcionales | RF-06 |
| Requerimientos no funcionales | RNF-05, RNF-08 |
| Escenarios de calidad | ESC-05 |
| Persistencia | Pendiente: el SRS define `RECOMENDACION_LOG` pero no asigna almacén |
| Lenguaje / framework | Python (FastAPI + Scikit-Learn + Pandas) |
| Puerto interno | `8005` |
| Contrato REST | [`contracts/openapi/recommendation.yaml`](../../contracts/openapi/) |

## Eventos

**Publica:**
* —

**Consume:**
* `reserva.confirmada.v1`
* `resena.publicada.v1`

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
docker compose up recommendation-service
```
