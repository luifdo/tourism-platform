# iam-service

**Módulo 1: Seguridad & IAM** · Responsable: Juan Francisco Gonzalez Pacheco (@JuanFranG)

Autenticación (JWT), control de acceso por roles (RBAC), verificación de prestadores (RNT, RUT), consentimiento de datos personales (Ley 1581) y bitácora de auditoría inmutable.

| Aspecto | Valor |
|---|---|
| Casos de uso | UC1, UC2, UC3, UC4, UC6, UC27, UC28, UC32, UC33, UC37 |
| Requerimientos funcionales | RF-08, RF-09, RF-12 |
| Requerimientos no funcionales | RNF-04, RNF-10 |
| Escenarios de calidad | ESC-04 |
| Persistencia | PostgreSQL — base lógica `iam_db` |
| Lenguaje / framework | Por definir (Spring Boot o NestJS) |
| Puerto interno | `8001` |
| Contrato REST | [`contracts/openapi/iam.yaml`](../../contracts/openapi/) |

## Eventos

**Publica:**
* `prestador.aprobado.v1`

**Consume:**
* `auditoria.registrada.v1` (de todos los servicios)

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
docker compose up iam-service
```
