# catalog-service

**Módulo 2: Catálogo & GIS** · Responsable: Valentina Sarait Nieves Hernandez (@nievesita)

Catálogo de atractivos, actividades y servicios; búsqueda multicriterio y consultas geoespaciales sobre OpenStreetMap.

| Aspecto | Valor |
|---|---|
| Casos de uso | UC7, UC8, UC9, UC16, UC17, UC18 |
| Requerimientos funcionales | RF-01, RF-02, RF-05 |
| Requerimientos no funcionales | RNF-02, RNF-03, RNF-06 |
| Escenarios de calidad | ESC-02, ESC-03, ESC-08 |
| Persistencia | PostgreSQL + PostGIS — base lógica `catalog_db`; caché en Valkey |
| Lenguaje / framework | Por definir (Spring Boot o NestJS) |
| Puerto interno | `8002` |
| Contrato REST | [`contracts/openapi/catalog.yaml`](../../contracts/openapi/) |

## Eventos

**Publica:**
* `auditoria.registrada.v1`

**Consume:**
* `prestador.aprobado.v1` (habilita la publicación de ofertas)

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
docker compose up catalog-service
```
